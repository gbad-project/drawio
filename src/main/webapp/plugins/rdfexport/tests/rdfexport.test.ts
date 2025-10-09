import { test, expect } from "bun:test";
import { createHash } from "crypto";
import { fileURLToPath } from "url";
import { DOMParser } from "@xmldom/xmldom";
import { readFileSync, readdirSync, existsSync } from "fs";
import { join, extname, basename, normalize } from "path";
import { patchDrawioWithMetadata } from "./utils/patchDrawioWithMetadata";

const rdfexportUrl = fileURLToPath(
  new URL("../src/rdfexport.ts", import.meta.url),
);
const compiledPluginUrl = fileURLToPath(
  new URL("../../rdfexport.js", import.meta.url),
);
const fixturesDir = fileURLToPath(new URL("./fixtures", import.meta.url));

const pyodideIndexPath = fileURLToPath(
  new URL("../node_modules/pyodide/", import.meta.url),
);
const pyodideIndexURL = normalize(pyodideIndexPath);
(globalThis as any).__rdfexportPyodideIndexURL = pyodideIndexURL.endsWith("/")
  ? pyodideIndexURL
  : `${pyodideIndexURL}/`;

const pluginCallbacks: Array<(ui: any) => void> = [];

type RdfExportModule = typeof import("../src/rdfexport");

let loadedPluginModule: RdfExportModule | null = null;

async function loadPluginModule(): Promise<RdfExportModule> {
  if (loadedPluginModule) {
    return loadedPluginModule;
  }

  loadedPluginModule = (await import(rdfexportUrl)) as RdfExportModule;
  return loadedPluginModule;
}
import {
  debugPyodide,
  runMockBlackBox,
  type DrawioParserResult,
} from "../src/mockBlackBox";

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
  parentNode: ElementStub | null = null;
  private listeners: Record<string, EventHandler[]> = {};

  constructor(tagName: string) {
    this.tagName = tagName.toUpperCase();
  }

  appendChild<T>(child: T): T {
    if (
      child instanceof ElementStub &&
      child.parentNode &&
      child.parentNode !== this
    ) {
      child.parentNode.removeChild(child);
    }

    this.children.push(child);

    if (child instanceof ElementStub) {
      child.parentNode = this;
    }
    return child;
  }

  insertBefore<T>(child: T, reference: any): T {
    if (
      child instanceof ElementStub &&
      child.parentNode &&
      child.parentNode !== this
    ) {
      child.parentNode.removeChild(child);
    }

    let index = -1;

    if (reference != null) {
      index = this.children.indexOf(reference);
    }

    if (index >= 0) {
      this.children.splice(index, 0, child);
    } else {
      this.children.push(child);
    }

    if (child instanceof ElementStub) {
      child.parentNode = this;
    }

    return child;
  }

  get firstChild(): any {
    return this.children.length > 0 ? this.children[0] : null;
  }

  removeChild<T>(child: T): T | null {
    const index = this.children.indexOf(child);

    if (index >= 0) {
      this.children.splice(index, 1);
      if (child instanceof ElementStub) {
        child.parentNode = null;
      }
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

  removeAttribute(name: string): void {
    delete this.attributes[name];
    if (name === "id") {
      this.id = "";
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

  click(): void {
    this.dispatchEvent({ type: "click" });
  }

  remove(): void {
    if (this.parentNode) {
      this.parentNode.removeChild(this);
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

interface CellStub {
  value: Element;
}

class GraphModelStub {
  private listeners = new Set<(sender: any, evt: any) => void>();
  private updateDepth = 0;
  private dirty = false;

  constructor(private readonly root: CellStub) {}

  getRoot(): CellStub {
    return this.root;
  }

  getValue(cell: CellStub): Element {
    return cell.value;
  }

  setValue(cell: CellStub, value: Element): void {
    cell.value = value;
    this.markDirty();
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

  private ensureElement(cell: CellStub): Element {
    return this.model.getValue(cell);
  }

  getAttributeForCell(
    cell: CellStub,
    attributeName: string,
    defaultValue: string | null,
  ): string | null {
    const element = this.ensureElement(cell);
    const hasAttribute =
      typeof (element as any).hasAttribute === "function"
        ? (element as any).hasAttribute(attributeName)
        : element.getAttribute(attributeName) != null;

    if (!hasAttribute) {
      return defaultValue;
    }

    const value = element.getAttribute(attributeName);
    return value != null ? value : defaultValue;
  }

  setAttributeForCell(
    cell: CellStub,
    attributeName: string,
    attributeValue: string | null,
  ): void {
    const element = this.ensureElement(cell);
    const current = element.getAttribute(attributeName);

    if (attributeValue != null) {
      if (current !== attributeValue) {
        element.setAttribute(attributeName, attributeValue);
        this.model.markDirty();
      }
    } else if (current != null) {
      element.removeAttribute(attributeName);
      this.model.markDirty();
    }
  }
}

const PREAMBLE_ENTRY_TAG = "userObjectPreambleElement";
const PREAMBLE_SECTION_ATTRIBUTE = "data-rdfexport-preamble-section";
const PREAMBLE_PREFIX_ATTRIBUTE = "rdfPrefix";
const PREAMBLE_IRI_ATTRIBUTE = "rdfIRI";

interface GraphEnvironmentOptions {
  csvPath?: string;
  baseUri?: string;
  preamble?: Array<{ prefix: string; iri: string }>;
}

function createGraphEnvironment(
  optionsOrCsvPath?: string | GraphEnvironmentOptions,
): {
  rootCell: CellStub;
  model: GraphModelStub;
  graph: GraphStub;
} {
  const options: GraphEnvironmentOptions =
    typeof optionsOrCsvPath === "string"
      ? { csvPath: optionsOrCsvPath }
      : (optionsOrCsvPath ?? {});

  const doc = new DOMParser().parseFromString(
    '<object id="root" label=""><mxCell/></object>',
    "application/xml",
  );
  const rootElement = doc.documentElement;

  if (!rootElement) {
    throw new Error("Failed to initialize root element for graph environment");
  }

  if (options.csvPath != null) {
    rootElement.setAttribute("csvPath", options.csvPath);
  }

  if (options.baseUri != null) {
    rootElement.setAttribute("baseUri", options.baseUri);
  }

  if (Array.isArray(options.preamble)) {
    for (const entry of options.preamble) {
      const preambleElement = doc.createElement(PREAMBLE_ENTRY_TAG);
      preambleElement.setAttribute(
        PREAMBLE_PREFIX_ATTRIBUTE,
        entry.prefix ?? "",
      );
      preambleElement.setAttribute(PREAMBLE_IRI_ATTRIBUTE, entry.iri ?? "");
      rootElement.appendChild(preambleElement);
    }
  }

  const rootCell: CellStub = { value: rootElement };
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

function findChildrenByAttribute(
  node: any,
  attributeName: string,
  attributeValue: string,
  results: ElementStub[] = [],
): ElementStub[] {
  if (!node) {
    return results;
  }

  if (
    node instanceof ElementStub &&
    node.getAttribute(attributeName) === attributeValue
  ) {
    results.push(node);
  }

  const children = (node as { children?: any }).children;
  if (Array.isArray(children)) {
    for (const child of children) {
      findChildrenByAttribute(child, attributeName, attributeValue, results);
    }
  }

  return results;
}

function findChildByAttribute(
  node: any,
  attributeName: string,
  attributeValue: string,
): ElementStub | null {
  const matches = findChildrenByAttribute(node, attributeName, attributeValue);
  return matches.length > 0 ? matches[0]! : null;
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
  button(label: string, handler: (evt?: any) => void) {
    const button = document.createElement("button") as unknown as ElementStub;
    button.textContent = label;
    button.className = "geButton";
    button.addEventListener("click", () => {
      handler();
    });
    return button as unknown as HTMLButtonElement;
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

test(
  "runMockBlackBox returns DrawIO parser summary",
  async () => {
    await loadPluginModule();
    const fixturePath = join(fixturesDir, "AA37 Department of Health.drawio");
    const sampleXml = await Bun.file(fixturePath).text();
    const output = await runMockBlackBox(sampleXml);

    expect(output.startsWith("[BLACKBOX] len=")).toBe(true);
    expect(output.trim().endsWith("[/BLACKBOX]")).toBe(true);

    const summaryJson = output
      .replace(/^[^\n]*\n/, "")
      .replace(/\n\[\/BLACKBOX\]\s*$/, "");
    const summary = JSON.parse(summaryJson) as DrawioParserResult;

    expect(summary.graphId).toMatch(/^graph-\d+$/);
    expect(summary.tripleCount).toBeGreaterThan(0);
    expect(summary.namespaces.some((entry) => entry.prefix === "rico")).toBe(
      true,
    );
  },
  { timeout: 60000 },
);

test("debugPyodide evaluates Python expressions", async () => {
  const result = await debugPyodide("1 + 2 + 3");
  expect(result).toBe(6);
});

test("compiled rdfexport plugin bundle includes CSV property hook", async () => {
  const scriptContents = await Bun.file(compiledPluginUrl).text();

  expect(scriptContents).toContain("DiagramFormatPanel.prototype.addOptions");
  expect(scriptContents).toContain("CSV Path");
  expect(scriptContents).toContain("data-rdfexport-csv-field");
  expect(scriptContents).toContain("data-rdfexport-preamble-section");
  expect(scriptContents).toContain("__rdfexportPreambleAttached");
});

function runRdfExportTest(fixtureFile: string, _baselineFile: string) {
  test(`${fixtureFile}: rdfexport plugin exports RDF with expected checksum`, async () => {
    const pluginModule = await loadPluginModule();

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

    const actions: Record<string, () => void | Promise<void>> = {};
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

    const exportAction = actions.exportRdfXml;
    expect(exportAction).toBeDefined();

    if (!exportAction) {
      throw new Error("exportRdfXml action was not registered by the plugin");
    }
    await exportAction();

    expect(savedExports).toHaveLength(1);
    const exportData = savedExports[0]!;
    const { filename, format, data, mimeType } = exportData;

    expect(filename).toBe(`${baseFilename}.rdf`);
    expect(format).toBe("rdf");
    expect(mimeType).toBe("application/rdf+xml");
    expect(exportMenuItems).toContainEqual(["-", "exportRdfXml"]);

    const referenceXml = mxUtils.getPrettyXml(graphModel);
    const expected = await runMockBlackBox(referenceXml);

    const md5 = createHash("md5").update(data).digest("hex");
    const refMd5 = createHash("md5").update(expected).digest("hex");

    expect(md5).toBe(refMd5);
    expect(data).toBe(expected);
    expect(data.startsWith("[BLACKBOX]")).toBe(true);
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

test("rdfexport plugin exposes preamble controls and diagram properties", async () => {
  const pluginModule = await loadPluginModule();

  const { graph, model, rootCell } = createGraphEnvironment({
    csvPath: "initial.csv",
    baseUri: "https://initial.example/base",
    preamble: [
      {
        prefix: "rdf",
        iri: "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      },
    ],
  });

  let lastDialogContainer: ElementStub | null = null;
  let hideDialogCalls = 0;

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
    showDialog(container: ElementStub) {
      lastDialogContainer = container;
    },
    hideDialog() {
      hideDialogCalls += 1;
    },
  };

  for (const callback of pluginCallbacks) {
    callback(editorUi);
  }

  const panelRoot = document.createElement("div");
  const existingViewSection = document.createElement("div");
  existingViewSection.className = "geFormatSection";
  panelRoot.appendChild(existingViewSection);

  const panelContext = {
    editorUi,
    listeners: [] as Array<{ destroy(): void }>,
    container: panelRoot,
  };

  const container = document.createElement("div");
  const addOptions = (DiagramFormatPanel as any).prototype.addOptions;

  const returned = addOptions.call(panelContext, container);
  panelRoot.appendChild(returned ?? container);

  const preambleSection = findChildByAttribute(
    panelRoot,
    PREAMBLE_SECTION_ATTRIBUTE,
    "true",
  );

  expect(preambleSection).toBeDefined();

  if (!preambleSection) {
    throw new Error("Preamble section was not created");
  }

  expect(panelRoot.children[0]).toBe(preambleSection);
  expect(panelRoot.children[1]).toBe(existingViewSection);
  expect(panelRoot.children[2]).toBe(container);
  expect(
    findChildByAttribute(container, PREAMBLE_SECTION_ATTRIBUTE, "true"),
  ).toBeNull();
  expect(preambleSection.className).toBe("geFormatSection");
  expect(preambleSection.style.padding).toBe("12px 0px 8px 14px");
  expect(preambleSection.style.whiteSpace).toBe("nowrap");

  const title = findChildByTag(preambleSection, "div", (element) => {
    return element.textContent === "Preamble";
  });
  expect(title).toBeDefined();

  const csvOption = findChildByTag(preambleSection, "div", (element) => {
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
  expect(label?.textContent).toBe("CSV Path");
  expect(label?.getAttribute("for")).toBeDefined();
  expect(label?.getAttribute("title")).toBe("CSV Path");
  expect(input).toBeDefined();
  expect(input?.value).toBe("initial.csv");
  expect(input?.getAttribute("placeholder")).toBe("CSV Path");
  expect(input?.getAttribute("autocomplete")).toBe("off");
  expect((input as ElementStub).style.marginRight).toBe("6px");

  if (!input) {
    throw new Error("CSV path input field was not created");
  }

  input.value = "  updated.csv  ";
  input.dispatchEvent({ type: "change" });
  expect(graph.getAttributeForCell(rootCell, "csvPath", null)).toBe(
    "updated.csv",
  );
  expect(input.value).toBe("updated.csv");

  input.value = "   ";
  input.dispatchEvent({ type: "blur" });
  expect(graph.getAttributeForCell(rootCell, "csvPath", null)).toBeNull();
  expect(input.value).toBe("");

  graph.setAttributeForCell(rootCell, "csvPath", "external.csv");
  expect(input.value).toBe("external.csv");

  const baseOption = findChildByAttribute(
    preambleSection,
    "data-rdfexport-base-uri-field",
    "true",
  );
  expect(baseOption).toBeDefined();

  if (!baseOption) {
    throw new Error("Base URI option container was not created");
  }

  const baseLabel = findChildByTag(baseOption, "label");
  const baseInput = findChildByTag(baseOption, "input", (element) => {
    return (element as any).type === "text";
  });

  expect(baseLabel?.textContent).toBe("Base URI");
  expect(baseInput?.value).toBe("https://initial.example/base");
  expect(baseInput?.getAttribute("placeholder")).toBe("Base URI");
  expect((baseInput as ElementStub).style.marginRight).toBe("6px");

  if (!baseInput) {
    throw new Error("Base URI input field was not created");
  }

  baseInput.value = " https://updated.example/base ";
  baseInput.dispatchEvent({ type: "change" });
  expect(graph.getAttributeForCell(rootCell, "baseUri", null)).toBe(
    "https://updated.example/base",
  );
  expect(baseInput.value).toBe("https://updated.example/base");

  baseInput.value = "   ";
  baseInput.dispatchEvent({ type: "blur" });
  expect(graph.getAttributeForCell(rootCell, "baseUri", null)).toBeNull();
  expect(baseInput.value).toBe("");

  graph.setAttributeForCell(
    rootCell,
    "baseUri",
    "https://override.example/base",
  );
  expect(baseInput.value).toBe("https://override.example/base");

  const preambleButton = findChildByAttribute(
    preambleSection,
    "data-rdfexport-preamble-button",
    "true",
  );
  expect(preambleButton).toBeDefined();

  lastDialogContainer = null;
  preambleButton?.click();

  expect(lastDialogContainer).toBeDefined();

  const dialogContainer = lastDialogContainer;

  if (!dialogContainer) {
    throw new Error("Preamble dialog did not open");
  }

  const existingEntries = findChildrenByAttribute(
    dialogContainer,
    "data-rdfexport-preamble-entry",
    "true",
  );
  expect(existingEntries).toHaveLength(1);

  const existingEntry = existingEntries[0]!;
  const existingPrefixInput = findChildByTag(
    existingEntry,
    "input",
    (element) => {
      return (
        element.getAttribute("data-rdfexport-preamble-entry-prefix") === "true"
      );
    },
  );
  const existingIriInput = findChildByTag(existingEntry, "input", (element) => {
    return element.getAttribute("data-rdfexport-preamble-entry-iri") === "true";
  });

  expect(existingPrefixInput?.value).toBe("rdf");
  expect(existingIriInput?.value).toBe(
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
  );

  if (!existingPrefixInput || !existingIriInput) {
    throw new Error("Existing preamble inputs were not rendered");
  }

  existingIriInput.value = " http://example.com/custom-rdf# ";
  existingIriInput.dispatchEvent({ type: "change" });

  const newPrefixInput = findChildByAttribute(
    dialogContainer,
    "data-rdfexport-preamble-prefix-input",
    "true",
  );
  const newIriInput = findChildByAttribute(
    dialogContainer,
    "data-rdfexport-preamble-iri-input",
    "true",
  );
  const addButton = findChildByAttribute(
    dialogContainer,
    "data-rdfexport-preamble-add-button",
    "true",
  );

  expect(addButton?.getAttribute("disabled")).toBe("disabled");

  if (!newPrefixInput || !newIriInput || !addButton) {
    throw new Error("New preamble controls were not rendered");
  }

  newPrefixInput.value = "ex";
  newPrefixInput.dispatchEvent({ type: "input" });
  newIriInput.value = "http://example.com/ns#";
  newIriInput.dispatchEvent({ type: "input" });

  expect(addButton.getAttribute("disabled")).toBeUndefined();
  addButton.click();

  const allEntries = findChildrenByAttribute(
    dialogContainer,
    "data-rdfexport-preamble-entry",
    "true",
  );
  expect(allEntries).toHaveLength(2);

  const applyButton = findChildByAttribute(
    dialogContainer,
    "data-rdfexport-preamble-apply",
    "true",
  );
  expect(applyButton).toBeDefined();

  applyButton?.click();

  expect(hideDialogCalls).toBe(1);

  const updatedValue = model.getValue(rootCell);
  const preambleNodes = Array.from(
    updatedValue.getElementsByTagName(PREAMBLE_ENTRY_TAG),
  );
  expect(preambleNodes).toHaveLength(2);

  expect(preambleNodes[0]?.getAttribute(PREAMBLE_PREFIX_ATTRIBUTE)).toBe("rdf");
  expect(preambleNodes[0]?.getAttribute(PREAMBLE_IRI_ATTRIBUTE)).toBe(
    "http://example.com/custom-rdf#",
  );
  expect(preambleNodes[1]?.getAttribute(PREAMBLE_PREFIX_ATTRIBUTE)).toBe("ex");
  expect(preambleNodes[1]?.getAttribute(PREAMBLE_IRI_ATTRIBUTE)).toBe(
    "http://example.com/ns#",
  );

  expect(updatedValue.getAttribute("baseUri")).toBe(
    "https://override.example/base",
  );
  expect(graph.getAttributeForCell(rootCell, "csvPath", null)).toBe(
    "external.csv",
  );
  expect(input.value).toBe("external.csv");
  expect(baseInput.value).toBe("https://override.example/base");

  const listenersBeforeDestroy = model.listenerCount();
  expect(listenersBeforeDestroy).toBeGreaterThan(0);
  for (const listener of panelContext.listeners) {
    listener.destroy();
  }
  expect(model.listenerCount()).toBe(0);

  const previewFixturePath = join(
    fixturesDir,
    "AA37 Department of Health.drawio",
  );
  const previewXml = await Bun.file(previewFixturePath).text();
  const preview = await runMockBlackBox(previewXml);
  expect(preview.startsWith("[BLACKBOX]")).toBe(true);
});

test("patchDrawioWithMetadata reproduces AA37 metadata artifact", () => {
  const baseFixturePath = join(fixturesDir, "AA37 Department of Health.drawio");
  const expectedFixturePath = join(
    fixturesDir,
    "AA37 Department of Health-with-metadata.drawio",
  );

  const baseContent = readFileSync(baseFixturePath, "utf8");
  const expectedContent = readFileSync(expectedFixturePath, "utf8");

  const patchedContent = patchDrawioWithMetadata(baseContent, {
    label: "",
    csvPath: "/mock/path/to/file.csv",
    baseUri: "http://mock-base-uri.com",
    preamble: [
      {
        rdfPrefix: "mock1",
        rdfIRI: "http://mock-iri-ns.org",
      },
    ],
  });

  const parser = new DOMParser({
    errorHandler: {
      error(message: string) {
        throw new Error(message);
      },
    },
  });

  const parseXml = (xml: string): Document => {
    const doc = parser.parseFromString(xml, "application/xml");
    if (doc.getElementsByTagName("parsererror").length > 0) {
      throw new Error("Failed to parse DrawIO XML");
    }
    return doc;
  };

  const selectAttributes = (
    element: Element,
    names: string[],
  ): Record<string, string> => {
    const snapshot: Record<string, string> = {};
    for (const name of names) {
      const value = element.getAttribute(name);
      if (value != null) {
        snapshot[name] = value;
      }
    }
    return snapshot;
  };

  const snapshotDocument = (xml: string) => {
    const doc = parseXml(xml);

    const mxfile = doc.getElementsByTagName("mxfile").item(0);
    if (!mxfile) {
      throw new Error("DrawIO document missing <mxfile>");
    }

    const graphModel = doc.getElementsByTagName("mxGraphModel").item(0);
    if (!graphModel) {
      throw new Error("DrawIO document missing <mxGraphModel>");
    }

    const root = doc.getElementsByTagName("root").item(0);
    if (!root) {
      throw new Error("DrawIO document missing <root>");
    }

    const metadata = Array.from(root.childNodes).find((node) => {
      return (
        node.nodeType === node.ELEMENT_NODE && node.nodeName === "UserObject"
      );
    });

    const metadataSnapshot = metadata
      ? (() => {
          const element = metadata as Element;
          const entries = Array.from(element.childNodes).filter((node) => {
            return (
              node.nodeType === node.ELEMENT_NODE &&
              node.nodeName === "userObjectPreambleElement"
            );
          });

          return {
            attributes: selectAttributes(element, [
              "label",
              "csvPath",
              "baseUri",
            ]),
            preamble: entries.map((entry) => {
              const child = entry as Element;
              return selectAttributes(child, ["rdfPrefix", "rdfIRI"]);
            }),
          };
        })()
      : null;

    return {
      mxfile: selectAttributes(mxfile as Element, [
        "host",
        "agent",
        "version",
        "etag",
        "modified",
        "type",
      ]),
      graphModel: selectAttributes(graphModel as Element, ["dx", "dy"]),
      metadata: metadataSnapshot,
    };
  };

  const baseSnapshot = snapshotDocument(baseContent);
  const expectedSnapshot = snapshotDocument(expectedContent);
  const patchedSnapshot = snapshotDocument(patchedContent);

  expect(baseSnapshot.metadata).toBeNull();
  expect(patchedSnapshot.metadata).toEqual(expectedSnapshot.metadata);
  expect(patchedSnapshot.mxfile).toEqual(baseSnapshot.mxfile);
  expect(patchedSnapshot.graphModel).toEqual(baseSnapshot.graphModel);
});
