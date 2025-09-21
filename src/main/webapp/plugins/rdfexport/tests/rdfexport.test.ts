import { test, expect } from "bun:test";
import { createHash } from "crypto";
import { fileURLToPath } from "url";
import { DOMParser } from "@xmldom/xmldom";
import { readFileSync, readdirSync, existsSync } from "fs";
import { join, extname, basename } from "path";

const rdfexportUrl = fileURLToPath(
  new URL("../src/rdfexport.ts", import.meta.url),
);
const compiledPluginUrl = fileURLToPath(
  new URL("../../rdfexport.js", import.meta.url),
);
const fixturesDir = fileURLToPath(new URL("./fixtures", import.meta.url));

const pluginCallbacks: Array<(ui: any) => void> = [];

type EventHandler = (event: any) => void;

class ElementStub {
  tagName: string;
  style: Record<string, string> = {};
  children: any[] = [];
  attributes: Record<string, string> = {};
  value = "";
  textContent = "";
  className = "";
  id = "";
  private listeners: Record<string, EventHandler[]> = {};

  constructor(tagName: string) {
    this.tagName = tagName.toUpperCase();
  }

  appendChild<T>(child: T): T {
    this.children.push(child);
    return child;
  }

  removeChild<T>(child: T): T | null {
    const index = this.children.indexOf(child);

    if (index >= 0) {
      this.children.splice(index, 1);
      return child;
    }

    return null;
  }

  setAttribute(name: string, value: string): void {
    this.attributes[name] = value;

    if (name === "id") {
      this.id = value;
    }

    if (name === "for") {
      (this as any).htmlFor = value;
    }

    if (name === "type") {
      (this as any).type = value;
    }
  }

  getAttribute(name: string): string | undefined {
    return this.attributes[name];
  }

  addEventListener(event: string, handler: EventHandler): void {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }

    this.listeners[event].push(handler);
  }

  dispatchEvent(evt: { type: string; key?: string }): void {
    const handlers = this.listeners[evt.type];

    if (handlers) {
      for (const handler of handlers) {
        handler(evt);
      }
    }
  }
}

class DocumentStub {
  createElement(tag: string): ElementStub {
    return new ElementStub(tag);
  }
}

const documentStub = new DocumentStub();
(globalThis as any).document = documentStub as unknown as Document;

class DiagramFormatPanelStub {
  listeners: Array<{ destroy(): void }> = [];
  editorUi: any;

  constructor(_format?: any, editorUi?: any, _container?: any) {
    this.editorUi = editorUi;
  }

  createTitle(title: string): ElementStub {
    const div = document.createElement("div");
    div.style.padding = "0px 0px 6px 0px";
    div.style.whiteSpace = "nowrap";
    div.style.overflow = "hidden";
    div.style.width = "200px";
    div.style.fontWeight = "bold";
    div.textContent = title;
    return div;
  }

  createOption(
    label: string,
    isCheckedFn: () => boolean,
    setCheckedFn: (checked: boolean) => void,
  ): ElementStub {
    const div = document.createElement("div");
    div.style.display = "flex";
    div.style.alignItems = "center";
    div.style.padding = "3px 0px 3px 0px";
    div.style.height = "18px";

    const checkbox = document.createElement("input");
    checkbox.setAttribute("type", "checkbox");
    checkbox.style.margin = "1px 6px 0px 0px";
    checkbox.style.verticalAlign = "top";
    div.appendChild(checkbox);

    const labelDiv = document.createElement("div");
    labelDiv.setAttribute("title", label);
    labelDiv.style.display = "inline-block";
    labelDiv.style.whiteSpace = "nowrap";
    labelDiv.style.textOverflow = "ellipsis";
    labelDiv.style.overflow = "hidden";
    labelDiv.style.maxWidth = "160px";
    labelDiv.style.userSelect = "none";
    labelDiv.textContent = label;
    div.appendChild(labelDiv);

    const apply = (newValue: boolean) => {
      checkbox.checked = newValue;
      checkbox.defaultChecked = newValue;

      if (isCheckedFn() !== newValue) {
        setCheckedFn(newValue);
      }
    };

    apply(isCheckedFn());

    div.addEventListener("click", () => {
      if (checkbox.getAttribute("disabled") === "disabled") {
        return;
      }

      apply(!checkbox.checked);
    });

    return div;
  }
}

(DiagramFormatPanelStub as any).prototype.addOptions = function (div: any) {
  return div;
};

(globalThis as any).DiagramFormatPanel = DiagramFormatPanelStub;

type AttributeMap = Record<string, string>;

interface CellStub {
  value: {
    attributes: AttributeMap;
  };
}

class GraphModelStub {
  private listeners = new Set<(sender: any, evt: any) => void>();
  private updateDepth = 0;
  private dirty = false;

  constructor(private readonly root: CellStub) {}

  getRoot(): CellStub {
    return this.root;
  }

  beginUpdate(): void {
    this.updateDepth += 1;
  }

  endUpdate(): void {
    if (this.updateDepth > 0) {
      this.updateDepth -= 1;

      if (this.updateDepth === 0 && this.dirty) {
        this.fireChange();
      }
    }
  }

  addListener(name: string, listener: (sender: any, evt: any) => void): void {
    if (name === "change") {
      this.listeners.add(listener);
    }
  }

  removeListener(listener: (sender: any, evt: any) => void): void {
    this.listeners.delete(listener);
  }

  markDirty(): void {
    if (this.updateDepth > 0) {
      this.dirty = true;
    } else {
      this.fireChange();
    }
  }

  listenerCount(): number {
    return this.listeners.size;
  }

  private fireChange(): void {
    this.dirty = false;

    for (const listener of [...this.listeners]) {
      listener(this, {});
    }
  }
}

class GraphStub {
  constructor(private readonly model: GraphModelStub) {}

  getModel(): GraphModelStub {
    return this.model;
  }

  getAttributeForCell(
    cell: CellStub,
    attributeName: string,
    defaultValue: string | null,
  ): string | null {
    const attrs = this.ensureAttributes(cell);
    const value = attrs[attributeName];
    return value != null ? value : defaultValue;
  }

  setAttributeForCell(
    cell: CellStub,
    attributeName: string,
    attributeValue: string | null,
  ): void {
    const attrs = this.ensureAttributes(cell);
    const current = attrs[attributeName];

    if (attributeValue != null) {
      if (current !== attributeValue) {
        attrs[attributeName] = attributeValue;
        this.model.markDirty();
      }
    } else if (current !== undefined) {
      delete attrs[attributeName];
      this.model.markDirty();
    }
  }

  private ensureAttributes(cell: CellStub): AttributeMap {
    if (!cell.value || typeof cell.value !== "object") {
      cell.value = { attributes: {} };
    }

    if (cell.value.attributes == null) {
      cell.value.attributes = {};
    }

    return cell.value.attributes;
  }
}

function createGraphEnvironment(initialCsvPath?: string): {
  rootCell: CellStub;
  model: GraphModelStub;
  graph: GraphStub;
} {
  const rootCell: CellStub = {
    value: {
      attributes: {},
    },
  };

  if (initialCsvPath != null) {
    rootCell.value.attributes.csvPath = initialCsvPath;
  }

  const model = new GraphModelStub(rootCell);
  const graph = new GraphStub(model);

  return { rootCell, model, graph };
}

function findChildByTag(
  node: any,
  tagName: string,
  predicate?: (element: ElementStub) => boolean,
): ElementStub | null {
  if (!node) {
    return null;
  }

  if (node instanceof ElementStub && node.tagName === tagName.toUpperCase()) {
    if (!predicate || predicate(node)) {
      return node;
    }
  }

  const children = (node as ElementStub).children;

  if (Array.isArray(children)) {
    for (const child of children) {
      const match = findChildByTag(child, tagName, predicate);

      if (match) {
        return match;
      }
    }
  }

  return null;
}

(globalThis as any).mxConstants = {
  NODETYPE_ELEMENT: 1,
  NODETYPE_TEXT: 3,
  NODETYPE_CDATA: 4,
  NODETYPE_COMMENT: 8,
  NODETYPE_DOCUMENT: 9,
  NODETYPE_DOCUMENT_FRAGMENT: 11,
};

// Add this line
const mxConstants = (globalThis as any).mxConstants;

const mxUtils = {
  createXmlDocument(): Document {
    const parser = new DOMParser();
    const doc = parser.parseFromString("<root />", "application/xml");
    const root = doc.documentElement;
    if (root) {
      doc.removeChild(root);
    }
    return doc;
  },
  getPrettyXml(
    node: Node | null,
    tab?: string,
    indent?: string,
    newline?: string,
    ns?: string,
  ): string {
    const result: string[] = [];

    if (node != null) {
      const actualTab = tab ?? "  ";
      const actualIndent = indent ?? "";
      const actualNewline = newline ?? "\n";

      const element = node as Element;
      const namespace = element.namespaceURI;
      if (namespace != null && namespace !== ns) {
        ns = namespace;
      }

      switch (node.nodeType) {
        case mxConstants.NODETYPE_DOCUMENT:
          result.push(
            mxUtils.getPrettyXml(
              (node as Document).documentElement,
              actualTab,
              actualIndent,
              actualNewline,
              ns,
            ),
          );
          break;
        case mxConstants.NODETYPE_DOCUMENT_FRAGMENT: {
          let child: ChildNode | null = (node as DocumentFragment).firstChild;
          while (child != null) {
            result.push(
              mxUtils.getPrettyXml(
                child,
                actualTab,
                actualIndent,
                actualNewline,
                ns,
              ),
            );
            child = child.nextSibling;
          }
          break;
        }
        case mxConstants.NODETYPE_COMMENT: {
          const value = mxUtils.getTextContent(node);
          if (value.length > 0) {
            result.push(`${actualIndent}<!--${value}-->${actualNewline}`);
          }
          break;
        }
        case mxConstants.NODETYPE_TEXT: {
          const value = mxUtils.trim(mxUtils.getTextContent(node));
          if (value.length > 0) {
            result.push(
              `${actualIndent}${mxUtils.htmlEntities(value, false, false)}${actualNewline}`,
            );
          }
          break;
        }
        case mxConstants.NODETYPE_CDATA: {
          const value = mxUtils.getTextContent(node);
          if (value.length > 0) {
            result.push(`${actualIndent}<![CDATA[${value}]]${actualNewline}`);
          }
          break;
        }
        default: {
          result.push(`${actualIndent}<${element.nodeName}`);

          const attrs = element.attributes;
          if (attrs != null) {
            for (let i = 0; i < attrs.length; i += 1) {
              const attr = attrs.item(i);
              if (attr != null) {
                const value = mxUtils.htmlEntities(attr.nodeValue ?? "");
                result.push(` ${attr.nodeName}="${value}"`);
              }
            }
          }

          let child: ChildNode | null = element.firstChild;
          if (child != null) {
            result.push(`>${actualNewline}`);
            while (child != null) {
              result.push(
                mxUtils.getPrettyXml(
                  child,
                  actualTab,
                  actualIndent + actualTab,
                  actualNewline,
                  ns,
                ),
              );
              child = child.nextSibling;
            }
            result.push(
              `${actualIndent}</${element.nodeName}>${actualNewline}`,
            );
          } else {
            result.push(` />${actualNewline}`);
          }
          break;
        }
      }
    }

    return result.join("");
  },
  getTextContent(node: Node): string {
    return node.textContent ?? "";
  },
  ltrim(value: string, chars?: string): string {
    const pattern = chars ?? "\\s|\\0";
    return value != null
      ? value.replace(new RegExp(`^[${pattern}]+`, "g"), "")
      : "";
  },
  rtrim(value: string, chars?: string): string {
    const pattern = chars ?? "\\s|\\0";
    return value != null
      ? value.replace(new RegExp(`[${pattern}]+$`, "g"), "")
      : "";
  },
  trim(value: string, chars?: string): string {
    return mxUtils.ltrim(mxUtils.rtrim(value, chars), chars);
  },
  htmlEntities(
    value: string,
    newline: boolean | null = true,
    quotes: boolean | null = true,
    tab: boolean | null = true,
  ): string {
    let result = String(value ?? "");
    result = result.replace(/&/g, "&amp;");
    result = result.replace(/</g, "&lt;");
    result = result.replace(/>/g, "&gt;");

    if (quotes == null || quotes) {
      result = result.replace(/"/g, "&quot;");
      result = result.replace(/'/g, "&#39;");
    }

    if (newline == null || newline) {
      result = result.replace(/\n/g, "&#xa;");
    }

    if (tab == null || tab) {
      result = result.replace(/\t/g, "&#x9;");
    }

    return result;
  },
};

(globalThis as any).mxUtils = mxUtils;
const resourceBundle: Record<string, string> = {};

(globalThis as any).mxResources = {
  parse(definition: string) {
    if (typeof definition !== "string") {
      return;
    }

    const entries = definition.split(";");
    for (const entry of entries) {
      const trimmed = entry.trim();
      if (!trimmed) {
        continue;
      }

      const separatorIndex = trimmed.indexOf("=");
      if (separatorIndex === -1) {
        continue;
      }

      const key = trimmed.substring(0, separatorIndex).trim();
      const value = trimmed.substring(separatorIndex + 1).trim();

      if (key.length > 0) {
        resourceBundle[key] = value;
      }
    }
  },
  get(key: string) {
    if (key in resourceBundle) {
      return resourceBundle[key];
    }

    return key;
  },
};
(globalThis as any).Draw = {
  loadPlugin(callback: (ui: any) => void) {
    pluginCallbacks.push(callback);
  },
};

test("compiled rdfexport plugin bundle includes CSV property hook", async () => {
  const scriptContents = await Bun.file(compiledPluginUrl).text();

  expect(scriptContents).toContain(
    "DiagramFormatPanel.prototype.addOptions",
  );
  expect(scriptContents).toContain("CSV path");
  expect(scriptContents).toContain("data-rdfexport-csv-field");
  expect(scriptContents).toContain("__rdfexportCsvFieldAttached");
});

function runRdfExportTest(fixtureFile: string, sampleFile: string) {
  test(`${fixtureFile}: rdfexport plugin exports RDF with expected checksum`, async () => {
    if (pluginCallbacks.length === 0) {
      await import(rdfexportUrl);
    }

    const fixturePath = join(fixturesDir, fixtureFile);
    const xml = await Bun.file(fixturePath).text();

    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xml, "application/xml");
    const graphModel = xmlDoc.getElementsByTagName("mxGraphModel").item(0);
    const diagramElement = xmlDoc.getElementsByTagName("diagram").item(0);

    if (!graphModel) {
      throw new Error("Failed to locate mxGraphModel element in fixture");
    }

    if (!diagramElement) {
      throw new Error("Failed to locate diagram element in fixture");
    }

    const pageId = diagramElement.getAttribute("id") ?? "diagram";
    const baseFilename = fixtureFile.replace(/\.drawio$/, "");

    const actions: Record<string, () => void> = {};
    const savedExports: Array<{
      filename: string;
      format: string;
      data: string;
      mimeType: string;
    }> = [];
    const exportMenuItems: string[][] = [];
    const menuStub: any = { funct: () => {} };

    const { graph } = createGraphEnvironment();

    const editorUi = {
      editor: {
        getGraphXml: () => graphModel,
        graph,
      },
      currentPage: {
        getId: () => pageId,
      },
      actions: {
        addAction(name: string, fn: () => void) {
          actions[name] = fn;
        },
      },
      menus: {
        get(name: string) {
          if (name === "exportAs") {
            return menuStub;
          }
          return null;
        },
        addMenuItems(menu: any, items: string[], parent: any) {
          exportMenuItems.push(items);
        },
      },
      getBaseFilename() {
        return baseFilename;
      },
      saveData(
        filename: string,
        format: string,
        data: string,
        mimeType: string,
      ) {
        savedExports.push({ filename, format, data, mimeType });
      },
      handleError(err: Error) {
        throw err;
      },
    };

    for (const callback of pluginCallbacks) {
      callback(editorUi);
    }

    menuStub.funct([], null);

    expect(actions.exportRdfXml).toBeDefined();

    if (!actions.exportRdfXml) {
      throw new Error("exportRdfXml action was not registered by the plugin");
    }
    actions.exportRdfXml();

    expect(savedExports).toHaveLength(1);
    const exportData = savedExports[0]!;
    const { filename, format, data, mimeType } = exportData;

    expect(filename).toBe(`${baseFilename}.rdf`);
    expect(format).toBe("rdf");
    expect(mimeType).toBe("application/rdf+xml");
    expect(exportMenuItems).toContainEqual(["-", "exportRdfXml"]);

    const md5 = createHash("md5").update(data).digest("hex");
    const refMd5 = createHash("md5")
      .update(
        readFileSync(new URL(`./fixtures/${sampleFile}`, import.meta.url)),
      )
      .digest("hex");
    expect(md5).toBe(refMd5);
  });
}

for (const file of readdirSync(fixturesDir)) {
  if (extname(file) === ".drawio") {
    const base = basename(file, ".drawio");
    const rdfFile = base + ".rdf";

    if (!existsSync(join(fixturesDir, rdfFile))) {
      test.skip(`${file}: skipped (no matching ${rdfFile})`, () => {});
      continue;
    }

    runRdfExportTest(file, rdfFile);
  }
}

test("rdfexport plugin exposes a CSV path diagram property", async () => {
  if (pluginCallbacks.length === 0) {
    await import(rdfexportUrl);
  }

  const { graph, model, rootCell } = createGraphEnvironment("initial.csv");

  const editorUi = {
    editor: {
      getGraphXml: () => ({}) as Element,
      graph,
    },
    currentPage: null,
    actions: { addAction: () => {} },
    menus: {
      get: () => null,
      addMenuItems: () => {},
    },
    getBaseFilename: () => "diagram",
    saveData: () => {},
    handleError: () => {},
  };

  for (const callback of pluginCallbacks) {
    callback(editorUi);
  }

  const panelContext = {
    editorUi,
    listeners: [] as Array<{ destroy(): void }>,
  };

  const container = document.createElement("div");
  const addOptions = (DiagramFormatPanel as any).prototype.addOptions;

  addOptions.call(panelContext, container);

  const title = findChildByTag(container, "div", (element) => {
    return element.textContent === "Preamble";
  });
  expect(title).toBeDefined();

  const csvOption = findChildByTag(container, "div", (element) => {
    return element.getAttribute("data-rdfexport-csv-field") === "true";
  });

  expect(csvOption).toBeDefined();

  if (!csvOption) {
    throw new Error("CSV path option container was not created");
  }

  const checkbox = findChildByTag(csvOption, "input", (element) => {
    return (element as any).type === "checkbox";
  });
  expect(checkbox).toBeDefined();
  expect(checkbox?.getAttribute("disabled")).toBe("disabled");
  expect(checkbox?.style.visibility).toBe("hidden");

  const label = findChildByTag(csvOption, "label");
  const input = findChildByTag(csvOption, "input", (element) => {
    return (element as any).type === "text";
  });

  expect(label).toBeDefined();
  expect(label?.textContent).toBe("CSV path");
  expect(label?.getAttribute("for")).toBeDefined();
  expect(label?.getAttribute("title")).toBe("CSV path");
  expect(input).toBeDefined();
  expect(input?.value).toBe("initial.csv");
  expect(input?.getAttribute("placeholder")).toBe("CSV path");
  expect(input?.getAttribute("autocomplete")).toBe("off");

  if (!input) {
    throw new Error("CSV path input field was not created");
  }

  input.value = "  updated.csv  ";
  input.dispatchEvent({ type: "change" });
  expect(graph.getAttributeForCell(rootCell, "csvPath", null)).toBe("updated.csv");
  expect(input.value).toBe("updated.csv");

  input.value = "   ";
  input.dispatchEvent({ type: "blur" });
  expect(graph.getAttributeForCell(rootCell, "csvPath", null)).toBeNull();
  expect(input.value).toBe("");

  graph.setAttributeForCell(rootCell, "csvPath", "external.csv");
  expect(input.value).toBe("external.csv");

  const listenersBeforeDestroy = model.listenerCount();
  expect(listenersBeforeDestroy).toBeGreaterThan(0);
  for (const listener of panelContext.listeners) {
    listener.destroy();
  }
  expect(model.listenerCount()).toBe(0);
});
