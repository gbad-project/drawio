import { readFile } from "fs/promises";
import { fileURLToPath } from "url";
import { DOMParser } from "@xmldom/xmldom";
import { basename, normalize } from "path";
import type { DrawioParserConfigPayload } from "../../../typescript_plugin/src/mockBlackBox";
import type { LiteralParserSettingsEntry } from "../../../../typescript_plugin/src/literalsKnob";

interface ScenarioConfig {
  xmlPath: string;
  slug?: string;
  baseFilename?: string;
  csvPath?: string;
  baseUri?: string;
  prefixes?: Array<{ prefix: string; iri: string }>;
  metadataAttributes?: Record<string, unknown>;
  preamble?: Array<{ prefix: string; iri: string }>;
  parserConfig?: Record<string, unknown>;
}

const rdfexportUrl = fileURLToPath(
  new URL("../../../typescript_plugin/src/rdfexport.ts", import.meta.url),
);

const pyodideIndexPath = fileURLToPath(
  new URL("../../../../node_modules/pyodide/", import.meta.url),
);
const pyodideIndexURL = normalize(pyodideIndexPath);
(globalThis as any).__rdfexportPyodideIndexURL = pyodideIndexURL.endsWith("/")
  ? pyodideIndexURL
  : `${pyodideIndexURL}/`;

const pluginCallbacks: Array<(ui: any) => void> = [];
const PARSER_SETTINGS_ATTRIBUTE_NAME = "rdfParserSettings";
const PARSER_SETTINGS_STORAGE_VERSION = 1;

function toCamelFromSnake(value: string): string {
  return value.replace(/_([a-z])/g, (_match, group: string) =>
    group.toUpperCase(),
  );
}

function formatMetadataValue(value: unknown): string {
  if (value == null) {
    return "";
  }

  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  if (typeof value === "number" || typeof value === "bigint") {
    return value.toString();
  }

  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch (_error) {
      return String(value);
    }
  }

  return String(value);
}

function deriveMetacharacterSettings(value: unknown): {
  strategy?: string;
  entries?: Array<{ character: string; replacement: string }>;
} {
  if (!Array.isArray(value)) {
    return {};
  }

  const entries: Array<{ character: string; replacement: string }> = [];
  let strategy: string | undefined;

  for (const raw of value) {
    if (typeof raw !== "string") {
      continue;
    }

    if ((raw === "url" || raw === "remove") && strategy == null) {
      strategy = raw;
      continue;
    }

    const separatorIndex = raw.indexOf("=");
    if (separatorIndex >= 0) {
      const character = raw.slice(0, separatorIndex);
      const replacement = raw.slice(separatorIndex + 1);
      if (character.length > 0) {
        entries.push({ character, replacement });
      }
    }
  }

  if (!strategy && entries.length > 0) {
    strategy = "custom";
  } else if (strategy && entries.length > 0 && strategy !== "custom") {
    strategy = "custom";
  }

  return { strategy, entries };
}

function deriveStoredParserSettings(
  parserConfig: Record<string, unknown> | null | undefined,
  metadataAttributes: Record<string, unknown>,
): string | null {
  if (!parserConfig) {
    return null;
  }

  if (
    Object.prototype.hasOwnProperty.call(
      metadataAttributes,
      PARSER_SETTINGS_ATTRIBUTE_NAME,
    )
  ) {
    return null;
  }

  const settings: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(parserConfig)) {
    if (
      key === "metacharacter_substitute" ||
      key === "rml_enabled" ||
      key === "literal_definitions"
    ) {
      continue;
    }
    settings[toCamelFromSnake(key)] = value;
  }

  const metachar = deriveMetacharacterSettings(
    parserConfig["metacharacter_substitute"],
  );
  if (metachar.strategy) {
    settings.metacharacterStrategy = metachar.strategy;
  }
  if (metachar.entries && metachar.entries.length > 0) {
    settings.metacharacterEntries = metachar.entries;
  }

  const literalDefs: LiteralParserSettingsEntry[] = [];
  if (Array.isArray(parserConfig["literal_definitions"])) {
    for (const def of parserConfig["literal_definitions"]) {
      if (typeof def === "object") {
        literalDefs.push({
          attrKey: def.attr_key,
          attrVal: def.attr_value,
        });
      }
    }
  }
  if (literalDefs && literalDefs.length > 0) {
    settings.literalDefinitions = literalDefs;
  }

  if (Object.keys(settings).length === 0) {
    return null;
  }

  return JSON.stringify({
    version: PARSER_SETTINGS_STORAGE_VERSION,
    settings,
  });
}

function normaliseMetadataAttributes(
  config: ScenarioConfig,
): Record<string, unknown> {
  const attributes: Record<string, unknown> = {};

  if (
    config.metadataAttributes &&
    typeof config.metadataAttributes === "object"
  ) {
    for (const [key, value] of Object.entries(config.metadataAttributes)) {
      attributes[key] = value;
    }
  }

  if (config.csvPath != null && attributes.csvPath == null) {
    attributes.csvPath = config.csvPath;
  }

  if (config.baseUri != null && attributes.baseUri == null) {
    attributes.baseUri = config.baseUri;
  }

  return attributes;
}

function normalisePreamble(
  config: ScenarioConfig,
): Array<{ prefix: string; iri: string }> {
  const source =
    Array.isArray(config.preamble) && config.preamble.length > 0
      ? config.preamble
      : config.prefixes;

  if (!source) {
    return [];
  }

  const result: Array<{ prefix: string; iri: string }> = [];
  for (const entry of source) {
    if (!entry) {
      continue;
    }

    if (Array.isArray(entry) && entry.length === 2) {
      const [prefix, iri] = entry;
      if (prefix != null && iri != null) {
        result.push({ prefix: String(prefix), iri: String(iri) });
      }
      continue;
    }

    if (typeof entry === "object") {
      const prefix = (entry as { prefix?: unknown }).prefix;
      const iri = (entry as { iri?: unknown }).iri;
      if (prefix != null && iri != null) {
        result.push({ prefix: String(prefix), iri: String(iri) });
      }
    }
  }

  return result;
}

type RdfExportModule =
  typeof import("../../../typescript_plugin/src/rdfexport");
let loadedPluginModule: RdfExportModule | null = null;

async function loadPluginModule(): Promise<RdfExportModule> {
  if (loadedPluginModule) {
    return loadedPluginModule;
  }

  setupGlobalEnvironment();
  loadedPluginModule = (await import(rdfexportUrl)) as RdfExportModule;
  return loadedPluginModule;
}

//---------------------------------------------------------------------
// Global environment stubs (ported from rdfexport.test.ts)
//---------------------------------------------------------------------

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
  private listeners: Record<string, Array<(evt: any) => void>> = {};

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

  addEventListener(event: string, handler: (evt: any) => void): void {
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
const document = documentStub as unknown as Document;

//---------------------------------------------------------------------
// Graph/model stubs
//---------------------------------------------------------------------

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
const PREAMBLE_PREFIX_ATTRIBUTE = "rdfPrefix";
const PREAMBLE_IRI_ATTRIBUTE = "rdfIRI";

interface GraphEnvironmentOptions {
  csvPath?: string;
  baseUri?: string;
  preamble?: Array<{ prefix: string; iri: string }>;
  attributes?: Record<string, unknown>;
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

  const attributes: Record<string, unknown> = {
    ...(options.attributes ?? {}),
  };

  if (options.csvPath != null && attributes.csvPath == null) {
    attributes.csvPath = options.csvPath;
  }

  if (options.baseUri != null && attributes.baseUri == null) {
    attributes.baseUri = options.baseUri;
  }

  for (const [attributeName, attributeValue] of Object.entries(attributes)) {
    if (attributeValue == null) {
      if (rootElement.hasAttribute(attributeName)) {
        rootElement.removeAttribute(attributeName);
      }
      continue;
    }

    rootElement.setAttribute(
      attributeName,
      formatMetadataValue(attributeValue),
    );
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

//---------------------------------------------------------------------
// Helper search utilities
//---------------------------------------------------------------------

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

//---------------------------------------------------------------------
// mxGraph utilities
//---------------------------------------------------------------------

function setupGlobalEnvironment(): void {
  if ((globalThis as any).__rdfexportHarnessInitialized) {
    return;
  }

  (globalThis as any).__rdfexportHarnessInitialized = true;
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
        (checkbox as any).checked = newValue;
        (checkbox as any).defaultChecked = newValue;

        if (isCheckedFn() !== newValue) {
          setCheckedFn(newValue);
        }
      };

      apply(isCheckedFn());

      div.addEventListener("click", () => {
        if (checkbox.getAttribute("disabled") === "disabled") {
          return;
        }

        apply(!(checkbox as any).checked);
      });

      return div;
    }
  }

  (DiagramFormatPanelStub as any).prototype.addOptions = function (div: any) {
    return div;
  };

  (globalThis as any).DiagramFormatPanel = DiagramFormatPanelStub;

  (globalThis as any).mxConstants = {
    NODETYPE_ELEMENT: 1,
    NODETYPE_TEXT: 3,
    NODETYPE_CDATA: 4,
    NODETYPE_COMMENT: 8,
    NODETYPE_DOCUMENT: 9,
    NODETYPE_DOCUMENT_FRAGMENT: 11,
  };

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
                  actualIndent + actualTab,
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
}

//---------------------------------------------------------------------
// Scenario execution
//---------------------------------------------------------------------

async function runPluginExport(
  xml: string,
  options: {
    baseFilename: string;
    metadataAttributes?: Record<string, unknown>;
    preamble?: Array<{
      prefix: string;
      iri: string;
    }>;
    parserConfig?: Record<string, unknown>;
  },
): Promise<string> {
  await loadPluginModule();

  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(xml, "application/xml");
  const graphModel = xmlDoc.getElementsByTagName("mxGraphModel").item(0);
  const diagramElement = xmlDoc.getElementsByTagName("diagram").item(0);

  if (!graphModel) {
    throw new Error("Failed to locate mxGraphModel element in XML");
  }

  if (!diagramElement) {
    throw new Error("Failed to locate diagram element in XML");
  }

  const pageId = diagramElement.getAttribute("id") ?? "diagram";

  const actions: Record<string, () => void | Promise<void>> = {};
  const savedExports: Array<{
    filename: string;
    format: string;
    data: string;
    mimeType: string;
  }> = [];
  const menuStub: any = { funct: () => {} };

  const metadataAttributes = {
    ...(options.metadataAttributes ?? {}),
  };

  const derivedSettings = deriveStoredParserSettings(
    options.parserConfig ?? null,
    metadataAttributes,
  );

  if (
    derivedSettings != null &&
    metadataAttributes[PARSER_SETTINGS_ATTRIBUTE_NAME] == null
  ) {
    metadataAttributes[PARSER_SETTINGS_ATTRIBUTE_NAME] = derivedSettings;
  }

  const { graph } = createGraphEnvironment({
    attributes: metadataAttributes,
    preamble: options.preamble,
  });

  const editorUi = {
    editor: {
      getGraphXml: () => graphModel,
      graph,
    },
    currentPage: {
      getId: () => pageId,
    },
    actions: {
      addAction(name: string, fn: () => void | Promise<void>) {
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
      addMenuItems() {
        // no-op for harness
      },
    },
    getBaseFilename() {
      return options.baseFilename;
    },
    saveData(filename: string, format: string, data: string, mimeType: string) {
      savedExports.push({ filename, format, data, mimeType });
    },
    handleError(error: Error) {
      throw error;
    },
  };

  for (const callback of pluginCallbacks) {
    callback(editorUi);
  }

  menuStub.funct([], null);

  const exportAction =
    options.parserConfig?.rml_enabled === true
      ? actions.exportRml
      : actions.exportRdfXml;

  if (!exportAction) {
    const missing = options.parserConfig?.rml_enabled
      ? "exportRml"
      : "exportRdfXml";
    throw new Error(`${missing} action was not registered by plugin`);
  }

  await exportAction();

  if (savedExports.length === 0) {
    throw new Error("Plugin did not save any export payload");
  }

  const [exportData] = savedExports;
  return exportData.data;
}

async function runScenario(config: ScenarioConfig) {
  const xml = await readFile(config.xmlPath, "utf-8");
  const baseFilename =
    config.baseFilename ?? basename(config.xmlPath).replace(/\.[^.]+$/, "");

  const mockBlackBoxModule = await import(
    "../../../typescript_plugin/src/mockBlackBox"
  );
  //console.error(xml);
  const parserConfig = (config.parserConfig ??
    null) as DrawioParserConfigPayload | null;
  const pipeline = await mockBlackBoxModule.runDrawioPipeline(
    xml,
    parserConfig,
  );
  Reflect.set(mockBlackBoxModule, "runDrawioPipeline", async () => pipeline);
  const plugin = await runPluginExport(xml, {
    baseFilename,
    metadataAttributes: normaliseMetadataAttributes(config),
    preamble: normalisePreamble(config),
    parserConfig: config.parserConfig ?? null,
  });

  return { pipeline, plugin };
}

async function main(): Promise<void> {
  const [configPath] = process.argv.slice(2);
  if (!configPath) {
    throw new Error("Usage: bun run run_scenario.ts <config.json>");
  }

  const config: ScenarioConfig = JSON.parse(
    await readFile(configPath, "utf-8"),
  );
  const results = await runScenario(config);
  process.stdout.write(JSON.stringify(results));
}

if (import.meta.main) {
  await main();
}
