import { test, expect } from "bun:test";
import { fileURLToPath } from "url";
import { DOMParser } from "@xmldom/xmldom";
import { readFileSync, readdirSync, existsSync } from "fs";
import type { BunPlugin } from "bun";
import { join, extname, basename, normalize, dirname, resolve } from "path";
import { patchDrawioWithMetadata } from "./utils/patchDrawioWithMetadata";
import { LOG_PREFIX, logInfo } from "../src/logging";

const rdfexportUrl = fileURLToPath(
  new URL("../src/rdfexport.ts", import.meta.url),
);
const fixturesDir = fileURLToPath(new URL("./fixtures", import.meta.url));
const baselinesDir = fileURLToPath(new URL("./baselines", import.meta.url));

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

const rawLoaderPlugin: BunPlugin = {
  name: "test-raw-loader",
  setup(build) {
    build.onResolve({ filter: /\?raw$/ }, (args) => {
      const pathWithoutQuery = args.path.replace(/\?raw$/, "");
      const absolutePath = resolve(dirname(args.importer), pathWithoutQuery);

      return {
        path: absolutePath,
        namespace: "test-raw-loader",
      };
    });

    build.onLoad(
      { filter: /.*/, namespace: "test-raw-loader" },
      async (args) => {
        const file = Bun.file(args.path);
        const contents = await file.text();

        return {
          contents: `export default ${JSON.stringify(contents)}`,
          loader: "js",
        };
      },
    );
  },
};

async function bundleRdfExportPlugin(): Promise<string> {
  const buildResult = await Bun.build({
    entrypoints: [rdfexportUrl],
    target: "browser",
    format: "esm",
    splitting: false,
    write: false,
    plugins: [rawLoaderPlugin],
  });

  const [output] = buildResult.outputs ?? [];

  if (!output) {
    throw new Error("Failed to compile rdfexport plugin for inspection");
  }

  return await output.text();
}

import {
  debugPyodide,
  runDrawioPipeline,
  runMockBlackBox,
  type DrawioParserConfigPayload,
  type DrawioParserResult,
} from "../src/mockBlackBox";

const DEFAULT_PARSER_CONFIG: DrawioParserConfigPayload = {
  infer_type_of_literals: true,
  include_preamble: true,
  ontology_iri: null,
  prefix: null,
  prefix_iri: null,
  indentation: 2,
  include_label: true,
  max_gap: 10,
  strict_mode: false,
  strip_html: true,
  metacharacter_substitute: ["url"],
  capitalisation_scheme: "upper-camel",
  rml_enabled: false,
  literal_definitions: [{ attrKey: "style", attrVal: "rounded=1" }],
};

function createParserConfig(
  overrides: Partial<DrawioParserConfigPayload> = {},
): DrawioParserConfigPayload {
  return {
    ...DEFAULT_PARSER_CONFIG,
    ...overrides,
    metacharacter_substitute: [
      ...(overrides.metacharacter_substitute ??
        DEFAULT_PARSER_CONFIG.metacharacter_substitute),
    ],
  };
}

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
const PARSER_SETTINGS_CELL_ATTRIBUTE = "rdfParserSettings";
const PARSER_SETTINGS_BUTTON_ATTRIBUTE =
  "data-rdfexport-parser-settings-button";
const PARSER_SETTINGS_DIALOG_ATTRIBUTE =
  "data-rdfexport-parser-settings-dialog";
const PARSER_SETTINGS_INCLUDE_PREAMBLE_ATTRIBUTE =
  "data-rdfexport-parser-include-preamble";
const PARSER_SETTINGS_INCLUDE_LABEL_ATTRIBUTE =
  "data-rdfexport-parser-include-label";
const PARSER_SETTINGS_INFER_TYPES_ATTRIBUTE =
  "data-rdfexport-parser-infer-types";
const PARSER_SETTINGS_STRICT_MODE_ATTRIBUTE =
  "data-rdfexport-parser-strict-mode";
const PARSER_SETTINGS_STRIP_HTML_ATTRIBUTE = "data-rdfexport-parser-strip-html";
const PARSER_SETTINGS_PREFIX_ATTRIBUTE = "data-rdfexport-parser-prefix";
const PARSER_SETTINGS_PREFIX_IRI_ATTRIBUTE = "data-rdfexport-parser-prefix-iri";
const PARSER_SETTINGS_ONTOLOGY_IRI_ATTRIBUTE =
  "data-rdfexport-parser-ontology-iri";
const PARSER_SETTINGS_INDENTATION_ATTRIBUTE =
  "data-rdfexport-parser-indentation";
const PARSER_SETTINGS_MAX_GAP_ATTRIBUTE = "data-rdfexport-parser-max-gap";
const PARSER_SETTINGS_CAPITALISATION_ATTRIBUTE =
  "data-rdfexport-parser-capitalisation";
const PARSER_SETTINGS_STRATEGY_ATTRIBUTE =
  "data-rdfexport-parser-metachar-strategy";
const PARSER_SETTINGS_METACHAR_LIST_ATTRIBUTE =
  "data-rdfexport-parser-metachar-list";
const PARSER_SETTINGS_METACHAR_ENTRY_ATTRIBUTE =
  "data-rdfexport-parser-metachar-entry";
const PARSER_SETTINGS_METACHAR_CHAR_ATTRIBUTE =
  "data-rdfexport-parser-metachar-char";
const PARSER_SETTINGS_METACHAR_REPLACEMENT_ATTRIBUTE =
  "data-rdfexport-parser-metachar-replacement";
const PARSER_SETTINGS_METACHAR_ADD_ATTRIBUTE =
  "data-rdfexport-parser-metachar-add";
const PARSER_SETTINGS_APPLY_ATTRIBUTE = "data-rdfexport-parser-apply";

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
  const scriptContents = await bundleRdfExportPlugin();

  expect(scriptContents).toContain("DiagramFormatPanel.prototype.addOptions");
  expect(scriptContents).toContain("CSV Path");
  expect(scriptContents).toContain("data-rdfexport-csv-field");
  expect(scriptContents).toContain("data-rdfexport-preamble-section");
  expect(scriptContents).toContain("__rdfexportPreambleAttached");
});

function runRdfExportTest(fixtureFile: string, baselineFile: string) {
  test(`${fixtureFile}: no regression`, async () => {
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

    // ===== Patch base URI in metadata to ensure isomorphism =====
    const rootEl = graphModel.getElementsByTagName("root").item(0);
    if (!rootEl) throw new Error("Failed to locate root element in fixture");
    let metadataNode: Element | null = null;
    // Find existing <gbadMetadata id="0"> (fall back to legacy tags)
    for (const node of Array.from(
      rootEl.getElementsByTagName("gbadMetadata"),
    )) {
      if (node.getAttribute("id") === "0") {
        metadataNode = node;
        break;
      }
    }
    if (!metadataNode) {
      for (const legacyTag of ["UserObject", "object"]) {
        for (const node of Array.from(rootEl.getElementsByTagName(legacyTag))) {
          if (node.getAttribute("id") === "0") {
            metadataNode = node;
            break;
          }
        }
        if (metadataNode) {
          break;
        }
      }
    }
    // Create if missing
    if (!metadataNode) {
      metadataNode = xmlDoc.createElement("gbadMetadata");
      metadataNode.setAttribute("id", "0");
      const mxCellElement = xmlDoc.createElement("mxCell");
      metadataNode.appendChild(mxCellElement);
      rootEl.insertBefore(metadataNode, rootEl.firstChild);
    }
    // Read or patch attributes
    const baseUriRaw = metadataNode.getAttribute("baseUri") || "";
    const mockBaseUri = "ontology://generated-from-draw-io/mock#";
    metadataNode.setAttribute("baseUri", baseUriRaw || mockBaseUri);
    logInfo(
      LOG_PREFIX.TEST,
      `Patched ontology IRI in fixture, set to: ${mockBaseUri}`,
    );

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
    const exportRmlAction = actions.exportRml;
    expect(exportAction).toBeDefined();
    expect(exportRmlAction).toBeDefined();

    if (!exportAction) {
      throw new Error("exportRdfXml action was not registered by the plugin");
    }
    await exportAction();

    expect(savedExports).toHaveLength(1);
    const exportData = savedExports[0]!;
    const { filename, format, data, mimeType } = exportData;

    expect(filename).toBe(`${baseFilename}.ttl`);
    expect(format).toBe("turtle");
    expect(mimeType).toBe("text/turtle");
    expect(exportMenuItems).toContainEqual(["-", "exportRdfXml", "exportRml"]);

    const referenceXml = mxUtils.getPrettyXml(graphModel);
    const expectedTurtle = await runDrawioPipeline(referenceXml);

    expect(expectedTurtle.length).toBeGreaterThan(0);
    expect(expectedTurtle.startsWith("[BLACKBOX]")).toBe(false);
    expect(
      /@prefix\s+/i.test(expectedTurtle) || expectedTurtle.includes(":"),
    ).toBe(true);

    const actualGraphInfo = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph

graph = Graph()
graph.parse(data=${JSON.stringify(data)}, format="turtle")

json.dumps({
    "triple_count": len(graph),
    "namespaces": sorted(prefix or "" for prefix, _ in graph.namespace_manager.namespaces()),
})
      `)) as string,
    ) as { triple_count: number; namespaces: string[] };

    const expectedGraphInfo = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph

graph = Graph()
graph.parse(data=${JSON.stringify(expectedTurtle)}, format="turtle")

json.dumps({
    "triple_count": len(graph),
    "namespaces": sorted(prefix or "" for prefix, _ in graph.namespace_manager.namespaces()),
})
      `)) as string,
    ) as { triple_count: number; namespaces: string[] };

    expect(actualGraphInfo.triple_count).toBe(expectedGraphInfo.triple_count);
    expect(actualGraphInfo.triple_count).toBeGreaterThan(0);
    expect(actualGraphInfo.namespaces).toEqual(expectedGraphInfo.namespaces);

    const dataVsExpectedResult = JSON.parse(
      (await debugPyodide(`
    import json
    from rdflib import Graph
    from rdflib.compare import to_isomorphic
    from rdflib.namespace import RDF, OWL

    actual_data = ${JSON.stringify(data)}
    expected_data = ${JSON.stringify(expectedTurtle)}

    g_actual = Graph()
    g_expected = Graph()

    g_actual.parse(data=actual_data, format="turtle")
    g_expected.parse(data=expected_data, format="turtle")

    def normalise(source: Graph) -> Graph:
        filtered = Graph()
        for s, p, o in source:
            if p == RDF.type and o in {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.Ontology}:
                continue
            if p == OWL.imports:
                continue
            filtered.add((s, p, o))
        return filtered

    iso_actual = to_isomorphic(normalise(g_actual))
    iso_expected = to_isomorphic(normalise(g_expected))

    json.dumps({
        "isomorphic": iso_actual == iso_expected,
        "actual_triples": len(g_actual),
        "expected_triples": len(g_expected),
    })
      `)) as string,
    ) as {
      isomorphic: boolean;
      actual_triples: number;
      expected_triples: number;
    };

    expect(dataVsExpectedResult.actual_triples).toBeGreaterThan(0);
    expect(dataVsExpectedResult.expected_triples).toBeGreaterThan(0);
    logInfo(
      LOG_PREFIX.TEST,
      `Number of triples in actual Turtle (plugin) vs expected Turtle (pipeline): ${dataVsExpectedResult.actual_triples} vs ${dataVsExpectedResult.expected_triples}`,
    );
    expect(dataVsExpectedResult.isomorphic).toBe(true);
    logInfo(
      LOG_PREFIX.TEST,
      `Also, Actual Turtle (plugin) is isomorphic to expected Turtle (pipeline): ${dataVsExpectedResult.isomorphic}`,
    );

    const baselinePath = join(baselinesDir, baselineFile);
    const baselineContents = await Bun.file(baselinePath).text();

    const isomorphismResult = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph
from rdflib.compare import to_isomorphic
from rdflib.namespace import RDF, OWL

baseline_data = ${JSON.stringify(baselineContents)}
actual_turtle = ${JSON.stringify(data)}

baseline_graph = Graph()
baseline_graph.parse(data=baseline_data, format="nt")

actual_graph = Graph()
actual_graph.parse(data=actual_turtle, format="turtle")

def normalise(source: Graph) -> Graph:
    filtered = Graph()
    for s, p, o in source:
        if p == RDF.type and o in {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.Ontology}:
            continue
        if p == OWL.imports:
            continue
        filtered.add((s, p, o))
    return filtered

baseline_filtered = normalise(baseline_graph)
actual_filtered = normalise(actual_graph)

baseline_iso = to_isomorphic(baseline_filtered)
actual_iso = to_isomorphic(actual_filtered)

json.dumps({
    "isomorphic": baseline_iso == actual_iso,
    "baseline_triples": len(baseline_graph),
    "actual_triples": len(actual_graph),
    "baseline_filtered_triples": len(baseline_filtered),
    "actual_filtered_triples": len(actual_filtered),
})
      `)) as string,
    ) as {
      isomorphic: boolean;
      baseline_triples: number;
      actual_triples: number;
      baseline_filtered_triples: number;
      actual_filtered_triples: number;
    };

    expect(isomorphismResult.actual_filtered_triples).toBe(
      isomorphismResult.baseline_filtered_triples,
    );
    expect(isomorphismResult.actual_filtered_triples).toBeGreaterThan(0);
    logInfo(
      LOG_PREFIX.TEST,
      `Number of filtered triples in Turtle vs baseline N-Triples: ${isomorphismResult.actual_filtered_triples} vs ${isomorphismResult.baseline_filtered_triples}`,
    );
    expect(isomorphismResult.isomorphic).toBe(true);
    if (isomorphismResult.isomorphic) {
      logInfo(
        LOG_PREFIX.TEST,
        `Also, Turtle is isomorphic to baseline N-Triples`,
      );
    }

    if (!exportRmlAction) {
      throw new Error("exportRml action was not registered by the plugin");
    }

    savedExports.splice(0, savedExports.length);
    await exportRmlAction();

    expect(savedExports).toHaveLength(1);
    const rmlExport = savedExports[0]!;
    expect(rmlExport.filename).toBe(`${baseFilename}.rml.ttl`);
    expect(rmlExport.format).toBe("turtle");
    expect(rmlExport.mimeType).toBe("text/turtle");
    expect(rmlExport.data.length).toBeGreaterThan(0);

    const rmlTripleCheck = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

graph = Graph()
graph.parse(data=${JSON.stringify(rmlExport.data)}, format="turtle")
rr = Namespace("http://www.w3.org/ns/r2rml#")
triples = list(graph.triples((None, RDF.type, rr.TriplesMap)))
json.dumps({
    "triples_map_count": len(triples),
    "total_triples": len(graph),
    "namespaces": sorted(prefix or "" for prefix, _ in graph.namespace_manager.namespaces()),
})
      `)) as string,
    ) as {
      triples_map_count: number;
      total_triples: number;
      namespaces: string[];
    };

    expect(rmlTripleCheck.triples_map_count).toBeGreaterThan(0);
    expect(rmlTripleCheck.namespaces).toEqual(
      expect.arrayContaining(["rr", "rml"]),
    );
    // This is where we will implement isomorphism checks
    // using outputs from rmlmapper_workflows!
  });
}

for (const file of readdirSync(fixturesDir)) {
  if (extname(file) === ".drawio") {
    const base = basename(file, ".drawio");
    const baselineFile = base + ".nt";
    const baselinePath = join(baselinesDir, baselineFile);

    if (!existsSync(baselinePath)) {
      test.skip(`${file}: skipped (no matching baseline ${baselineFile})`, () => {});
      continue;
    }

    runRdfExportTest(file, baselineFile);
  }
}

test(
  "runDrawioPipeline emits rr:TriplesMap triple when RML metadata enabled",
  async () => {
    await loadPluginModule();

    const fixturePath = join(
      fixturesDir,
      "AA37 Department of Health-with-metadata-rml.drawio",
    );
    const xml = await Bun.file(fixturePath).text();

    const rmlConfig: DrawioParserConfigPayload = {
      infer_type_of_literals: true,
      include_preamble: true,
      ontology_iri: null,
      prefix: null,
      prefix_iri: null,
      indentation: 2,
      include_label: true,
      max_gap: 10,
      strict_mode: false,
      strip_html: true,
      metacharacter_substitute: ["url"],
      capitalisation_scheme: "upper-camel",
      rml_enabled: true,
    };

    const turtle = await runDrawioPipeline(xml, rmlConfig);

    expect(turtle.length).toBeGreaterThan(0);
    expect(turtle.includes("rr:TriplesMap")).toBe(true);

    const rmlSummary = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

graph = Graph()
graph.parse(data=${JSON.stringify(turtle)}, format="turtle")
rr = Namespace("http://www.w3.org/ns/r2rml#")
triples = list(graph.triples((None, RDF.type, rr.TriplesMap)))
json.dumps({
    "triples_map_count": len(triples),
    "namespaces": sorted(prefix or "" for prefix, _ in graph.namespace_manager.namespaces()),
})
      `)) as string,
    ) as { triples_map_count: number; namespaces: string[] };

    expect(rmlSummary.triples_map_count).toBeGreaterThan(0);
    expect(rmlSummary.namespaces).toContain("rr");
  },
  { timeout: 60000 },
);

test(
  "runDrawioPipeline strips literal HTML when stripHtml enabled",
  async () => {
    await loadPluginModule();

    const fixturePath = join(
      fixturesDir,
      "AA37 Department of Health-with-metadata-preserve-html.drawio",
    );
    const xml = await Bun.file(fixturePath).text();

    const baseConfig: DrawioParserConfigPayload = {
      infer_type_of_literals: true,
      include_preamble: true,
      ontology_iri: null,
      prefix: null,
      prefix_iri: null,
      indentation: 2,
      include_label: true,
      max_gap: 10,
      strict_mode: false,
      strip_html: true,
      metacharacter_substitute: ["url"],
      capitalisation_scheme: "upper-camel",
      rml_enabled: true,
    };

    const sanitizedTurtle = await runDrawioPipeline(xml, baseConfig);
    expect(sanitizedTurtle.length).toBeGreaterThan(0);

    const sanitizedSummary = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph, Literal

graph = Graph()
graph.parse(data=${JSON.stringify(sanitizedTurtle)}, format="turtle")
values = [
    str(obj)
    for _, _, obj in graph
    if isinstance(obj, Literal) and "Function Note:" in str(obj)
]
json.dumps({
    "values": values,
    "has_html": any("<blockquote" in value for value in values),
})
      `)) as string,
    ) as { values: string[]; has_html: boolean };

    expect(sanitizedSummary.values.length).toBeGreaterThan(0);
    expect(sanitizedSummary.has_html).toBe(false);
  },
  { timeout: 60000 },
);

test(
  "runDrawioPipeline preserves literal HTML when stripHtml disabled",
  async () => {
    await loadPluginModule();

    const fixturePath = join(
      fixturesDir,
      "AA37 Department of Health-with-metadata-preserve-html.drawio",
    );
    const xml = await Bun.file(fixturePath).text();

    const preservedConfig: DrawioParserConfigPayload = {
      infer_type_of_literals: true,
      include_preamble: true,
      ontology_iri: null,
      prefix: null,
      prefix_iri: null,
      indentation: 2,
      include_label: true,
      max_gap: 10,
      strict_mode: false,
      strip_html: false,
      metacharacter_substitute: ["url"],
      capitalisation_scheme: "upper-camel",
      rml_enabled: true,
    };

    const preservedTurtle = await runDrawioPipeline(xml, preservedConfig);
    expect(preservedTurtle.length).toBeGreaterThan(0);

    const preservedSummary = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph, Literal

graph = Graph()
graph.parse(data=${JSON.stringify(preservedTurtle)}, format="turtle")
values = [
    str(obj)
    for _, _, obj in graph
    if isinstance(obj, Literal) and "Function Note:" in str(obj)
]
json.dumps({
    "values": values,
    "has_html": any("<blockquote" in value for value in values),
})
      `)) as string,
    ) as { values: string[]; has_html: boolean };

    expect(preservedSummary.values.length).toBeGreaterThan(0);
    expect(preservedSummary.has_html).toBe(true);
  },
  { timeout: 60000 },
);

test(
  "runDrawioPipeline omits rdfs:label triples when includeLabel disabled",
  async () => {
    await loadPluginModule();

    const xml = await Bun.file(
      join(fixturesDir, "AA37 Department of Health.drawio"),
    ).text();

    const config = createParserConfig({ include_label: false });
    const turtle = await runDrawioPipeline(xml, config);

    const summary = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph
from rdflib.namespace import RDFS

graph = Graph()
graph.parse(data=${JSON.stringify(turtle)}, format="turtle")
label_count = sum(1 for _ in graph.triples((None, RDFS.label, None)))
json.dumps({"label_count": label_count})
      `)) as string,
    ) as { label_count: number };

    expect(summary.label_count).toBe(0);
  },
  { timeout: 60000 },
);

test(
  "runDrawioPipeline omits ontology declaration when includePreamble disabled",
  async () => {
    await loadPluginModule();

    const xml = await Bun.file(
      join(fixturesDir, "AA37 Department of Health.drawio"),
    ).text();

    const config = createParserConfig({ include_preamble: false });
    const turtle = await runDrawioPipeline(xml, config);

    const summary = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph
from rdflib.namespace import OWL

graph = Graph()
graph.parse(data=${JSON.stringify(turtle)}, format="turtle")
ontology_triples = sum(1 for _ in graph.triples((None, OWL.Ontology, None)))
json.dumps({"ontology_triples": ontology_triples})
      `)) as string,
    ) as { ontology_triples: number };

    expect(summary.ontology_triples).toBe(0);
  },
  { timeout: 60000 },
);

test(
  "runDrawioPipeline keeps literals untyped when inference disabled",
  async () => {
    await loadPluginModule();

    const xml = await Bun.file(
      join(fixturesDir, "AA37 Department of Health.drawio"),
    ).text();

    const config = createParserConfig({ infer_type_of_literals: false });
    const turtle = await runDrawioPipeline(xml, config);

    const summary = JSON.parse(
      (await debugPyodide(`
import json
from rdflib import Graph
from rdflib.namespace import XSD

graph = Graph()
graph.parse(data=${JSON.stringify(turtle)}, format="turtle")
typed_literals = sum(
    1
    for _, _, obj in graph
    if getattr(obj, "datatype", None) in {XSD.integer, XSD.float, XSD.date}
)
json.dumps({"typed_literals": typed_literals})
      `)) as string,
    ) as { typed_literals: number };

    expect(summary.typed_literals).toBe(0);
  },
  { timeout: 60000 },
);

test(
  "runDrawioPipeline forwards strictMode flag to parser configuration",
  async () => {
    await loadPluginModule();

    const xml = await Bun.file(
      join(fixturesDir, "AA37 Department of Health.drawio"),
    ).text();

    await runDrawioPipeline(xml, createParserConfig({ strict_mode: true }));
    const strictSummary = JSON.parse(
      (await debugPyodide(`
import json
from pyodide_pipeline.drawio_pipeline import get_last_parser_config

json.dumps(get_last_parser_config())
      `)) as string,
    ) as { strict_mode: boolean | null };

    expect(strictSummary.strict_mode).toBe(true);

    await runDrawioPipeline(xml, createParserConfig({ strict_mode: false }));
    const relaxedSummary = JSON.parse(
      (await debugPyodide(`
import json
from pyodide_pipeline.drawio_pipeline import get_last_parser_config

json.dumps(get_last_parser_config())
      `)) as string,
    ) as { strict_mode: boolean | null };

    expect(relaxedSummary.strict_mode).toBe(false);
  },
  { timeout: 60000 },
);

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

test("parser settings dialog updates stored configuration and pipeline", async () => {
  await loadPluginModule();

  const fixturePath = join(fixturesDir, "AA37 Department of Health.drawio");
  const sampleXml = await Bun.file(fixturePath).text();
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(sampleXml, "application/xml");
  const graphXmlElement = xmlDoc.documentElement;

  const { graph, model, rootCell } = createGraphEnvironment();

  const actions: Record<string, () => void | Promise<void>> = {};
  const savedExports: Array<{ filename: string; data: string }> = [];
  let lastDialogContainer: ElementStub | null = null;
  let hideDialogCalls = 0;

  const editorUi = {
    editor: {
      getGraphXml: () => graphXmlElement,
      graph,
    },
    currentPage: null,
    actions: {
      addAction(name: string, fn: () => void | Promise<void>) {
        actions[name] = fn;
      },
    },
    menus: {
      get: () => null,
      addMenuItems: () => {},
    },
    getBaseFilename: () => "diagram",
    saveData(filename: string, _format: string, data: string) {
      savedExports.push({ filename, data });
    },
    handleError(err: Error) {
      throw err;
    },
    showDialog(container: ElementStub) {
      lastDialogContainer = container;
    },
    hideDialog() {
      hideDialogCalls += 1;
      lastDialogContainer = null;
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
    throw new Error("Preamble section missing");
  }

  const preambleButton = findChildByAttribute(
    preambleSection,
    "data-rdfexport-preamble-button",
    "true",
  );
  const parserSettingsButton = findChildByAttribute(
    preambleSection,
    PARSER_SETTINGS_BUTTON_ATTRIBUTE,
    "true",
  );

  expect(parserSettingsButton).toBeDefined();
  if (!parserSettingsButton) {
    throw new Error("Parser settings button was not rendered");
  }

  const preambleIndex = preambleSection.children.indexOf(preambleButton);
  const settingsIndex = preambleSection.children.indexOf(parserSettingsButton);
  expect(settingsIndex).toBeGreaterThan(preambleIndex);

  parserSettingsButton.click();
  expect(lastDialogContainer).toBeDefined();
  const dialogContainer = lastDialogContainer;
  if (!dialogContainer) {
    throw new Error("Parser settings dialog did not open");
  }
  expect(dialogContainer.getAttribute(PARSER_SETTINGS_DIALOG_ATTRIBUTE)).toBe(
    "true",
  );

  const includePreambleInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_INCLUDE_PREAMBLE_ATTRIBUTE,
    "true",
  ) as ElementStub & { checked: boolean };
  const includeLabelInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_INCLUDE_LABEL_ATTRIBUTE,
    "true",
  ) as ElementStub & { checked: boolean };
  const inferTypesInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_INFER_TYPES_ATTRIBUTE,
    "true",
  ) as ElementStub & { checked: boolean };
  const strictModeInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_STRICT_MODE_ATTRIBUTE,
    "true",
  ) as ElementStub & { checked: boolean };
  const stripHtmlInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_STRIP_HTML_ATTRIBUTE,
    "true",
  ) as ElementStub & { checked: boolean };

  expect(includePreambleInput.checked).toBe(true);
  expect(includeLabelInput.checked).toBe(true);
  expect(inferTypesInput.checked).toBe(true);
  expect(strictModeInput.checked).toBe(false);
  expect(stripHtmlInput.checked).toBe(true);

  includePreambleInput.checked = false;
  includeLabelInput.checked = false;
  inferTypesInput.checked = false;
  strictModeInput.checked = true;
  stripHtmlInput.checked = false;

  const prefixInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_PREFIX_ATTRIBUTE,
    "true",
  ) as ElementStub;
  const prefixIriInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_PREFIX_IRI_ATTRIBUTE,
    "true",
  ) as ElementStub;
  const ontologyIriInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_ONTOLOGY_IRI_ATTRIBUTE,
    "true",
  ) as ElementStub;
  const indentationInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_INDENTATION_ATTRIBUTE,
    "true",
  ) as ElementStub;
  const maxGapInput = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_MAX_GAP_ATTRIBUTE,
    "true",
  ) as ElementStub;
  const capitalisationSelect = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_CAPITALISATION_ATTRIBUTE,
    "true",
  ) as ElementStub;
  const strategySelect = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_STRATEGY_ATTRIBUTE,
    "true",
  ) as ElementStub;

  prefixInput.value = "ex";
  prefixIriInput.value = "http://example.com/ns#";
  ontologyIriInput.value = "http://example.com/ontology";
  indentationInput.value = "4";
  maxGapInput.value = "42.5";
  capitalisationSelect.value = "flat";
  strategySelect.value = "remove";

  const addButton = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_METACHAR_ADD_ATTRIBUTE,
    "true",
  );
  expect(addButton).toBeDefined();
  addButton?.click();

  const entryRow = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_METACHAR_ENTRY_ATTRIBUTE,
    "true",
  );
  expect(entryRow).toBeDefined();
  if (!entryRow) {
    throw new Error("Metacharacter entry row was not created");
  }

  const entryCharSelect = findChildByAttribute(
    entryRow,
    PARSER_SETTINGS_METACHAR_CHAR_ATTRIBUTE,
    "true",
  ) as ElementStub;
  const entryReplacementInput = findChildByAttribute(
    entryRow,
    PARSER_SETTINGS_METACHAR_REPLACEMENT_ATTRIBUTE,
    "true",
  ) as ElementStub;

  entryCharSelect.value = "(";
  entryReplacementInput.value = "square";

  const applyButton = findChildByAttribute(
    dialogContainer,
    PARSER_SETTINGS_APPLY_ATTRIBUTE,
    "true",
  );
  expect(applyButton).toBeDefined();
  applyButton?.click();

  expect(hideDialogCalls).toBe(1);

  const storedSettingsRaw = graph.getAttributeForCell(
    rootCell,
    PARSER_SETTINGS_CELL_ATTRIBUTE,
    null,
  );
  expect(typeof storedSettingsRaw).toBe("string");
  const storedSettings = JSON.parse(storedSettingsRaw as string) as {
    version: number;
    settings: any;
  };
  expect(storedSettings.version).toBe(1);
  const stored = storedSettings.settings;
  expect(stored.includePreamble).toBe(false);
  expect(stored.includeLabel).toBe(false);
  expect(stored.inferTypeOfLiterals).toBe(false);
  expect(stored.strictMode).toBe(true);
  expect(stored.stripHtml).toBe(false);
  expect(stored.indentation).toBe(4);
  expect(stored.maxGap).toBeCloseTo(42.5);
  expect(stored.prefix).toBe("ex");
  expect(stored.prefixIri).toBe("http://example.com/ns#");
  expect(stored.ontologyIri).toBe("http://example.com/ontology");
  expect(stored.capitalisationScheme).toBe("flat");
  expect(stored.metacharacterStrategy).toBe("remove");
  expect(stored.metacharacterEntries).toEqual([
    { character: "(", replacement: "square" },
  ]);

  const exportAction = actions.exportRdfXml;
  expect(exportAction).toBeDefined();
  await exportAction?.();

  expect(savedExports).toHaveLength(1);
  expect(savedExports[0]?.filename).toBe("diagram.ttl");

  const configJson = (await debugPyodide(
    "import json\nfrom pyodide_pipeline.drawio_pipeline import get_last_parser_config\njson.dumps(get_last_parser_config())",
  )) as string;
  const config = JSON.parse(configJson) as Record<string, any>;
  expect(config.include_preamble).toBe(false);
  expect(config.include_label).toBe(false);
  expect(config.infer_type_of_literals).toBe(false);
  expect(config.strict_mode).toBe(true);
  expect(config.strip_html).toBe(false);
  expect(config.indentation).toBe(4);
  expect(config.max_gap).toBeCloseTo(42.5);
  expect(config.prefix).toBe("ex");
  expect(config.prefix_iri).toBe("http://example.com/ns#");
  expect(config.ontology_iri).toBe("http://example.com/ontology");
  expect(config.capitalisation_scheme).toBe("flat");
  expect(config.metacharacter_substitute).toEqual(["remove", "(=square"]);
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
      if (node.nodeType !== node.ELEMENT_NODE) {
        return false;
      }
      const element = node as Element;
      const tagName = element.tagName?.toLowerCase() ?? "";
      return ["gbadmetadata", "userobject", "object"].includes(tagName);
    });

    const metadataSnapshot = metadata
      ? (() => {
          const element = metadata as Element;
          const entries = Array.from(element.childNodes).filter((node) => {
            return (
              node.nodeType === node.ELEMENT_NODE &&
              node.nodeName.toLowerCase() === "userobjectpreambleelement"
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

test("literal definitions with default config", async () => {
  const fixturePath = join(fixturesDir, "Class_Diagram_tweaked.drawio");
  const diagramXml = readFileSync(fixturePath, "utf-8");

  const config = createParserConfig({
    literal_definitions: null,
  });

  const result = await runDrawioPipeline(diagramXml, config);
  expect(result).toBeTruthy();
  expect(result.length).toBeGreaterThan(0);
});

test("literal definitions with empty array makes everything literal", async () => {
  const fixturePath = join(fixturesDir, "Class_Diagram_tweaked.drawio");
  const diagramXml = readFileSync(fixturePath, "utf-8");

  const config = createParserConfig({
    literal_definitions: [],
  });

  const result = await runDrawioPipeline(diagramXml, config);
  expect(result).toBeTruthy();
  expect(result.length).toBeGreaterThan(0);
});

test("literal definitions with custom attributes", async () => {
  const fixturePath = join(fixturesDir, "Class_Diagram_tweaked.drawio");
  const diagramXml = readFileSync(fixturePath, "utf-8");

  const config = createParserConfig({
    literal_definitions: [
      { attrKey: "rounded", attrVal: "1" },
      { attrKey: "ellipse", attrVal: "" },
    ],
  });

  const result = await runDrawioPipeline(diagramXml, config);
  expect(result).toBeTruthy();
  expect(result.length).toBeGreaterThan(0);
});
