// Originally generated with OpenAI Codex on 2025-09-15
// Ported to TypeScript with Claude Sonnet 4 on 2025-09-15
import * as yaml from 'js-yaml';

import defaultConfigYamlSource from "./pyodideRuntime";

/**
 * RDF/XML export plugin - TypeScript version
 */

// Type definitions for Draw.io/mxGraph APIs
interface MxConstants {
  NODETYPE_ELEMENT: number;
  NODETYPE_TEXT: number;
  NODETYPE_CDATA: number;
}

interface MxUtils {
  createXmlDocument(): Document;
  getPrettyXml(doc: Document): string;
  button?(label: string, handler: (evt?: any) => void): HTMLButtonElement;
  isNode?(value: any): boolean;
}

interface MxResources {
  parse(resources: string): void;
  get?(key: string): string | null | undefined;
}

interface MxEventSource {
  addListener(name: string, listener: (sender: any, event: any) => void): void;
  removeListener(listener: (sender: any, event: any) => void): void;
}

interface MxGraphModel extends MxEventSource {
  getRoot(): any;
  beginUpdate(): void;
  endUpdate(): void;
  getValue?(cell: any): any;
  setValue?(cell: any, value: any): void;
}

interface MxGraph {
  getModel(): MxGraphModel;
  getAttributeForCell(
    cell: any,
    attributeName: string,
    defaultValue: string | null,
  ): string | null;
  setAttributeForCell(
    cell: any,
    attributeName: string,
    value: string | null,
  ): void;
}

interface MxPage {
  getId(): string;
}

interface MxEditor {
  getGraphXml(): Element;
  graph: MxGraph;
}

interface MxAction {
  (): void | Promise<void>;
}

interface MxActions {
  addAction(name: string, action: MxAction): void;
}

interface MxMenu {
  funct: (menu: any, parent: any) => void;
}

interface MxMenus {
  get(name: string): MxMenu | null;
  addMenuItems(menu: any, items: string[], parent: any): void;
}

interface EditorUi {
  editor: MxEditor;
  currentPage: MxPage | null;
  actions: MxActions;
  menus: MxMenus;
  getBaseFilename(withoutExtension?: boolean): string;
  saveData(
    filename: string,
    format: string,
    data: string,
    mimeType: string,
  ): void;
  handleError(error: Error): void;
  showDialog?(
    container: HTMLElement,
    width: number,
    height: number,
    modal: boolean,
    closable: boolean,
    onClose?: (() => void) | null,
    closeOnEscape?: boolean,
  ): void;
  hideDialog?(): void;
}

interface Draw {
  loadPlugin(callback: (editorUi: EditorUi) => void): void;
}

// Global declarations
declare const Draw: Draw;
declare const mxConstants: MxConstants;
declare const mxUtils: MxUtils;
declare const mxResources: MxResources;
declare const DiagramFormatPanel: any;

const CSV_PATH_ATTRIBUTE = "csvPath";
const BASE_URI_ATTRIBUTE = "baseUri";
const CSV_PATH_RESOURCE_KEY = "csvPath";
const BASE_URI_RESOURCE_KEY = "baseUri";
const CSV_SECTION_RESOURCE_KEY = "csvPreamble";
const PREAMBLE_BUTTON_RESOURCE_KEY = "editPreamble";
const PREAMBLE_PREFIX_PLACEHOLDER_KEY = "enterPrefix";
const PREAMBLE_IRI_PLACEHOLDER_KEY = "enterIri";
const PREAMBLE_ADD_BUTTON_RESOURCE_KEY = "addPrefix";

const PREAMBLE_SECTION_FLAG = "__rdfexportPreambleAttached";
const PREAMBLE_SECTION_DATA_ATTRIBUTE = "data-rdfexport-preamble-section";

const DEFAULT_CSV_PATH_LABEL = "CSV Path";
const DEFAULT_BASE_URI_LABEL = "Base URI";
const DEFAULT_CSV_SECTION_LABEL = "Preamble";
const DEFAULT_PREAMBLE_BUTTON_LABEL = "Edit Preamble...";
const DEFAULT_PREFIX_PLACEHOLDER = "Enter Prefix";
const DEFAULT_IRI_PLACEHOLDER = "Enter IRI";
const DEFAULT_ADD_PREFIX_LABEL = "Add Prefix";

const PREAMBLE_ENTRY_TAG = "userObjectPreambleElement";
const PREAMBLE_ENTRY_TAG_LEGACY = "UserObjectPreambleElement";
const PREAMBLE_PREFIX_ATTRIBUTE = "rdfPrefix";
const PREAMBLE_IRI_ATTRIBUTE = "rdfIRI";

const PARSER_SETTINGS_ATTRIBUTE_NAME = "rdfParserSettings";
const PARSER_SETTINGS_STORAGE_VERSION = 1;
const PARSER_SETTINGS_BUTTON_RESOURCE_KEY = "parserSettings";
const DEFAULT_PARSER_SETTINGS_BUTTON_LABEL = "Parser Settings...";
const PARSER_SETTINGS_DIALOG_ATTRIBUTE =
  "data-rdfexport-parser-settings-dialog";
const PARSER_SETTINGS_BUTTON_ATTRIBUTE =
  "data-rdfexport-parser-settings-button";
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
const PARSER_SETTINGS_METACHAR_REMOVE_ATTRIBUTE =
  "data-rdfexport-parser-metachar-remove";
const PARSER_SETTINGS_METACHAR_ADD_ATTRIBUTE =
  "data-rdfexport-parser-metachar-add";
const PARSER_SETTINGS_APPLY_ATTRIBUTE = "data-rdfexport-parser-apply";
const PARSER_SETTINGS_CANCEL_ATTRIBUTE = "data-rdfexport-parser-cancel";

const RML_ENABLED_ATTRIBUTE = "rmlEnabled";
const STRIP_HTML_METADATA_ATTRIBUTE = "stripHtml";

const METADATA_TAG_NAME = "gbadMetadata";
const LEGACY_METADATA_TAG_NAMES = ["UserObject", "object"] as const;
const MXCELL_TAG_NAME = "mxCell";

type CapitalisationScheme = "upper-camel" | "lower-camel" | "flat" | "none";
type MetacharacterStrategy = "url" | "remove" | "custom";

const METACHARACTER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: " ", label: "Space ( )" },
  { value: "(", label: "(" },
  { value: ")", label: ")" },
  { value: "[", label: "[" },
  { value: "]", label: "]" },
  { value: "{", label: "{" },
  { value: "}", label: "}" },
  { value: "/", label: "/" },
  { value: ",", label: "," },
  { value: ":", label: ":" },
  { value: ".", label: "." },
  { value: "'", label: "'" },
  { value: '"', label: '"' },
  { value: "\u00a0", label: "Non-breaking space" },
  { value: "#", label: "#" },
];

const CAPITALISATION_SCHEME_OPTIONS: Array<{
  value: CapitalisationScheme;
  label: string;
}> = [
  { value: "upper-camel", label: "Upper camel case" },
  { value: "lower-camel", label: "Lower camel case" },
  { value: "flat", label: "Flat (lowercase)" },
  { value: "none", label: "Leave unchanged" },
];

const METACHARACTER_STRATEGY_OPTIONS: Array<{
  value: MetacharacterStrategy;
  label: string;
}> = [
  {
    value: "url",
    label: "Replace unspecified metacharacters with URL entities",
  },
  {
    value: "remove",
    label: "Remove unspecified metacharacters",
  },
  {
    value: "custom",
    label: "Use only custom substitutions",
  },
];

interface ParserSettingsEntry {
  character: string;
  replacement: string;
}

interface ParserSettings {
  includePreamble: boolean;
  inferTypeOfLiterals: boolean;
  includeLabel: boolean;
  strictMode: boolean;
  stripHtml: boolean;
  indentation: number;
  maxGap: number;
  ontologyIri: string | null;
  prefix: string | null;
  prefixIri: string | null;
  capitalisationScheme: CapitalisationScheme;
  metacharacterStrategy: MetacharacterStrategy;
  metacharacterEntries: ParserSettingsEntry[];
}

interface StoredParserSettings {
  version: number;
  settings: ParserSettings;
}

function createDefaultParserSettings(): ParserSettings {
  const defaultConfig = yaml.load(defaultConfigYamlSource) as any;
  const parserConfig = defaultConfig.parser_config;

  let metacharacterStrategy: MetacharacterStrategy = "custom";
  const metacharacterEntries: ParserSettingsEntry[] = [];

  if (parserConfig.metacharacter_substitute.includes("url")) {
    metacharacterStrategy = "url";
  } else if (parserConfig.metacharacter_substitute.includes("remove")) {
    metacharacterStrategy = "remove";
  }

  for (const substitute of parserConfig.metacharacter_substitute) {
    if (typeof substitute === "object") {
      metacharacterEntries.push({
        character: substitute.character,
        replacement: substitute.replacement,
      });
    }
  }

  return {
    includePreamble: parserConfig.include_preamble,
    inferTypeOfLiterals: parserConfig.infer_type_of_literals,
    includeLabel: parserConfig.include_label,
    strictMode: parserConfig.strict_mode,
    stripHtml: parserConfig.strip_html,
    indentation: parserConfig.indentation,
    maxGap: parserConfig.max_gap,
    ontologyIri: parserConfig.ontology_iri,
    prefix: parserConfig.prefix,
    prefixIri: parserConfig.prefix_iri,
    capitalisationScheme: parserConfig.capitalisation_scheme,
    metacharacterStrategy,
    metacharacterEntries,
  };
}

function normalizeBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "string") {
    const lowered = value.trim().toLowerCase();
    if (["true", "1", "yes", "on"].includes(lowered)) {
      return true;
    }
    if (["false", "0", "no", "off"].includes(lowered)) {
      return false;
    }
  }

  if (value == null) {
    return fallback;
  }

  return Boolean(value);
}

function normalizeNullableString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizeIndentation(value: unknown, fallback: number): number {
  if (typeof value === "string" && value.trim().length === 0) {
    return Math.max(0, Math.round(fallback));
  }
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return Math.max(0, Math.round(numeric));
  }
  return Math.max(0, Math.round(fallback));
}

function normalizeMaxGap(value: unknown, fallback: number): number {
  if (typeof value === "string" && value.trim().length === 0) {
    return Math.max(0, fallback);
  }
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return Math.max(0, numeric);
  }
  return Math.max(0, fallback);
}

function normalizeCapitalisationScheme(
  value: unknown,
  fallback: CapitalisationScheme,
): CapitalisationScheme {
  if (value === "lower-camel" || value === "flat" || value === "none") {
    return value;
  }
  if (value === "upper-camel") {
    return "upper-camel";
  }
  return fallback;
}

function normalizeMetacharacterStrategy(
  value: unknown,
  fallback: MetacharacterStrategy,
): MetacharacterStrategy {
  if (value === "remove" || value === "custom" || value === "url") {
    return value;
  }
  return fallback;
}

function normalizeMetacharacterEntries(
  entries: unknown,
): ParserSettingsEntry[] {
  if (!Array.isArray(entries)) {
    return [];
  }

  const normalized: ParserSettingsEntry[] = [];

  for (const entry of entries) {
    if (!entry || typeof entry !== "object") {
      continue;
    }

    const character =
      typeof (entry as ParserSettingsEntry).character === "string"
        ? (entry as ParserSettingsEntry).character
        : "";

    if (character.length === 0) {
      continue;
    }

    const replacement =
      typeof (entry as ParserSettingsEntry).replacement === "string"
        ? (entry as ParserSettingsEntry).replacement
        : "";

    normalized.push({ character, replacement });
  }

  return normalized;
}

function normaliseParserSettings(
  partial: Partial<ParserSettings> | null | undefined,
): ParserSettings {
  const defaults = createDefaultParserSettings();

  return {
    includePreamble: normalizeBoolean(
      partial?.includePreamble,
      defaults.includePreamble,
    ),
    inferTypeOfLiterals: normalizeBoolean(
      partial?.inferTypeOfLiterals,
      defaults.inferTypeOfLiterals,
    ),
    includeLabel: normalizeBoolean(
      partial?.includeLabel,
      defaults.includeLabel,
    ),
    strictMode: normalizeBoolean(partial?.strictMode, defaults.strictMode),
    stripHtml: normalizeBoolean(partial?.stripHtml, defaults.stripHtml),
    indentation: normalizeIndentation(
      partial?.indentation,
      defaults.indentation,
    ),
    maxGap: normalizeMaxGap(partial?.maxGap, defaults.maxGap),
    ontologyIri:
      partial?.ontologyIri != null
        ? normalizeNullableString(partial.ontologyIri)
        : null,
    prefix:
      partial?.prefix != null ? normalizeNullableString(partial.prefix) : null,
    prefixIri:
      partial?.prefixIri != null
        ? normalizeNullableString(partial.prefixIri)
        : null,
    capitalisationScheme: normalizeCapitalisationScheme(
      partial?.capitalisationScheme,
      defaults.capitalisationScheme,
    ),
    metacharacterStrategy: normalizeMetacharacterStrategy(
      partial?.metacharacterStrategy,
      defaults.metacharacterStrategy,
    ),
    metacharacterEntries: normalizeMetacharacterEntries(
      partial?.metacharacterEntries,
    ),
  };
}

function parseStoredParserSettings(raw: string | null): ParserSettings {
  if (!raw) {
    return createDefaultParserSettings();
  }

  try {
    const parsed = JSON.parse(raw) as StoredParserSettings | ParserSettings;
    if (parsed && typeof parsed === "object") {
      if (
        typeof (parsed as StoredParserSettings).settings === "object" &&
        (parsed as StoredParserSettings).settings !== null
      ) {
        return normaliseParserSettings(
          (parsed as StoredParserSettings).settings,
        );
      }

      return normaliseParserSettings(parsed as ParserSettings);
    }
  } catch (error) {
    // ignore malformed stored state and fall back to defaults
  }

  return createDefaultParserSettings();
}

function serializeParserSettings(settings: ParserSettings): string {
  const normalized = normaliseParserSettings(settings);
  const storage: StoredParserSettings = {
    version: PARSER_SETTINGS_STORAGE_VERSION,
    settings: normalized,
  };
  return JSON.stringify(storage);
}

const DEFAULT_SERIALIZED_PARSER_SETTINGS = serializeParserSettings(
  createDefaultParserSettings(),
);

function buildParserConfigPayloadFromSettings(
  settings: ParserSettings,
): DrawioParserConfigPayload {
  const normalized = normaliseParserSettings(settings);
  const substitutes: string[] = [];

  if (normalized.metacharacterStrategy === "url") {
    substitutes.push("url");
  } else if (normalized.metacharacterStrategy === "remove") {
    substitutes.push("remove");
  }

  for (const entry of normalized.metacharacterEntries) {
    substitutes.push(`${entry.character}=${entry.replacement ?? ""}`);
  }

  return {
    infer_type_of_literals: normalized.inferTypeOfLiterals,
    include_preamble: normalized.includePreamble,
    ontology_iri: normalizeNullableString(normalized.ontologyIri),
    prefix: normalizeNullableString(normalized.prefix),
    prefix_iri: normalizeNullableString(normalized.prefixIri),
    indentation: normalized.indentation,
    include_label: normalized.includeLabel,
    max_gap: normalized.maxGap,
    strict_mode: normalized.strictMode,
    strip_html: normalized.stripHtml,
    metacharacter_substitute: substitutes,
    capitalisation_scheme: normalized.capitalisationScheme,
    rml_enabled: false,
  };
}

function extractValueElement(
  model: MxGraphModel,
  rootCell: any,
): Element | null {
  if (typeof model.getValue === "function") {
    const value = model.getValue(rootCell);
    if (value && typeof (value as Element).getAttribute === "function") {
      return value as Element;
    }
  }

  const fallback = (rootCell as { value?: any }).value;
  if (fallback && typeof (fallback as Element).getAttribute === "function") {
    return fallback as Element;
  }

  return null;
}

function readParserSettingsFromGraphInstance(
  graph: MxGraph,
  model: MxGraphModel,
  rootCell: any,
): ParserSettings {
  let rawValue: string | null = null;

  if (typeof graph.getAttributeForCell === "function") {
    const attributeValue = graph.getAttributeForCell(
      rootCell,
      PARSER_SETTINGS_ATTRIBUTE_NAME,
      null,
    );
    rawValue = typeof attributeValue === "string" ? attributeValue : null;
  }

  if (!rawValue || rawValue.length === 0) {
    const valueElement = extractValueElement(model, rootCell);
    if (valueElement) {
      const attribute = valueElement.getAttribute(
        PARSER_SETTINGS_ATTRIBUTE_NAME,
      );
      rawValue = attribute != null && attribute.length > 0 ? attribute : null;
    }
  }

  return parseStoredParserSettings(rawValue);
}

function writeParserSettingsToGraphInstance(
  graph: MxGraph,
  model: MxGraphModel,
  rootCell: any,
  settings: ParserSettings,
): void {
  const serialized = serializeParserSettings(settings);
  const valueToStore =
    serialized === DEFAULT_SERIALIZED_PARSER_SETTINGS ? null : serialized;

  try {
    ensureRootCellMetadataElement(model, rootCell);
  } catch (error) {
    // ignore failures while normalising metadata storage before persisting settings
  }

  model.beginUpdate?.();
  try {
    if (typeof graph.setAttributeForCell === "function") {
      graph.setAttributeForCell(
        rootCell,
        PARSER_SETTINGS_ATTRIBUTE_NAME,
        valueToStore,
      );
    } else {
      const valueElement = extractValueElement(model, rootCell);
      if (valueElement) {
        if (valueToStore != null) {
          valueElement.setAttribute(
            PARSER_SETTINGS_ATTRIBUTE_NAME,
            valueToStore,
          );
        } else if (typeof valueElement.removeAttribute === "function") {
          valueElement.removeAttribute(PARSER_SETTINGS_ATTRIBUTE_NAME);
        }
        (model as { markDirty?: () => void }).markDirty?.();
      }
    }
  } finally {
    model.endUpdate?.();
  }
}

function buildParserConfigPayloadFromGraph(
  graph: MxGraph | undefined | null,
): DrawioParserConfigPayload {
  if (!graph || typeof graph.getModel !== "function") {
    return buildParserConfigPayloadFromSettings(createDefaultParserSettings());
  }

  const model = graph.getModel();
  if (!model || typeof model.getRoot !== "function") {
    return buildParserConfigPayloadFromSettings(createDefaultParserSettings());
  }

  const rootCell = model.getRoot();
  if (!rootCell) {
    return buildParserConfigPayloadFromSettings(createDefaultParserSettings());
  }

  const settings = readParserSettingsFromGraphInstance(graph, model, rootCell);
  return buildParserConfigPayloadFromSettings(settings);
}

import {
  runDrawioPipeline,
  type DrawioParserConfigPayload,
} from "./mockBlackBox";
import { LOG_PREFIX, logError, logInfo } from "./logging";

let csvPropertyPatched = false;
const registeredResourceKeys = new Set<string>();

function registerResource(key: string, fallback: string): void {
  if (registeredResourceKeys.has(key)) {
    return;
  }

  try {
    mxResources.parse?.(`${key}=${fallback}\n`);
  } catch (error) {
    // ignore resource registration errors
  }

  registeredResourceKeys.add(key);
}

function resolveLabel(key: string, fallback: string): string {
  registerResource(key, fallback);

  try {
    const label = mxResources.get?.(key);
    if (typeof label === "string" && label.length > 0) {
      return label;
    }
  } catch (error) {
    // ignore lookup errors and fall back to the default label
  }

  return fallback;
}

interface SerializeDiagramOptions {
  rmlEnabled?: boolean;
  stripHtml?: boolean;
}

function findRootMetadataNode(graphXml: Element): Element | null {
  return ensureGraphXmlMetadataNode(graphXml);
}

function applyRmlEnabledMetadata(graphXml: Element, enabled: boolean): void {
  const metadataNode = findRootMetadataNode(graphXml);

  if (!metadataNode) {
    return;
  }

  if (enabled) {
    metadataNode.setAttribute(RML_ENABLED_ATTRIBUTE, "true");
  } else {
    metadataNode.removeAttribute(RML_ENABLED_ATTRIBUTE);
  }
}

function applyStripHtmlMetadata(graphXml: Element, stripHtml: boolean): void {
  const metadataNode = findRootMetadataNode(graphXml);

  if (!metadataNode) {
    return;
  }

  metadataNode.setAttribute(
    STRIP_HTML_METADATA_ATTRIBUTE,
    stripHtml ? "true" : "false",
  );
}

function cloneGraphXml(graphXml: Element): Element {
  if (typeof graphXml.cloneNode === "function") {
    return graphXml.cloneNode(true) as Element;
  }

  return graphXml;
}

function installCsvPathProperty(): void {
  if (csvPropertyPatched) {
    return;
  }

  if (typeof DiagramFormatPanel === "undefined") {
    return;
  }

  const originalAddOptions = DiagramFormatPanel.prototype.addOptions;

  if (typeof originalAddOptions !== "function") {
    return;
  }

  DiagramFormatPanel.prototype.addOptions = function (
    div: HTMLElement,
  ): HTMLElement {
    const result = originalAddOptions.apply(this, arguments as any);
    const container: HTMLElement | undefined = (result ?? div) as
      | HTMLElement
      | undefined;

    if (!container || typeof document === "undefined") {
      return result;
    }

    const typedContainer = container as HTMLElement & {
      [PREAMBLE_SECTION_FLAG]?: boolean;
    };

    if (typedContainer[PREAMBLE_SECTION_FLAG]) {
      return result;
    }

    const ui = (this as { editorUi?: EditorUi }).editorUi;
    const graph: MxGraph | undefined = ui?.editor?.graph;
    const model: MxGraphModel | undefined = graph?.getModel?.();

    if (
      !graph ||
      !model ||
      typeof model.getRoot !== "function" ||
      typeof (graph as any).getAttributeForCell !== "function" ||
      typeof (graph as any).setAttributeForCell !== "function"
    ) {
      return result;
    }

    try {
      const rootCell = model.getRoot();
      if (rootCell) {
        ensureRootCellMetadataElement(model, rootCell);
      }
    } catch (error) {
      // ignore failures when normalising the metadata container
    }

    typedContainer[PREAMBLE_SECTION_FLAG] = true;

    const sectionLabel = resolveLabel(
      CSV_SECTION_RESOURCE_KEY,
      DEFAULT_CSV_SECTION_LABEL,
    );

    const createTitle =
      typeof (this as { createTitle?: (title: string) => HTMLElement })
        .createTitle === "function"
        ? ((this as any).createTitle as (title: string) => HTMLElement).bind(
            this,
          )
        : (title: string) => {
            const titleElement = document.createElement("div");
            titleElement.style.padding = "0px 0px 6px 0px";
            titleElement.style.whiteSpace = "nowrap";
            titleElement.style.overflow = "hidden";
            titleElement.style.width = "200px";
            titleElement.style.fontWeight = "bold";
            titleElement.textContent = title;
            return titleElement;
          };

    const preambleSection = document.createElement("div");
    preambleSection.className = "geFormatSection";
    preambleSection.setAttribute(PREAMBLE_SECTION_DATA_ATTRIBUTE, "true");
    preambleSection.style.padding = "12px 0px 8px 14px";
    preambleSection.style.whiteSpace = "nowrap";
    preambleSection.style.width = "100%";
    preambleSection.style.boxSizing = "border-box";

    preambleSection.appendChild(createTitle(sectionLabel));

    const createOption =
      typeof (this as { createOption?: (...args: any[]) => HTMLElement })
        .createOption === "function"
        ? (
            (this as any).createOption as (
              label: string,
              isCheckedFn: () => boolean,
              setCheckedFn: (checked: boolean) => void,
              listener?: unknown,
              fn?: unknown,
            ) => HTMLElement
          ).bind(this)
        : null;

    type TextFieldConfig = {
      attributeName: string;
      labelKey: string;
      fallbackLabel: string;
      dataAttribute: string;
    };

    interface FieldState {
      attributeName: string;
      input: HTMLInputElement;
    }

    const textFieldConfigs: TextFieldConfig[] = [
      {
        attributeName: CSV_PATH_ATTRIBUTE,
        labelKey: CSV_PATH_RESOURCE_KEY,
        fallbackLabel: DEFAULT_CSV_PATH_LABEL,
        dataAttribute: "data-rdfexport-csv-field",
      },
      {
        attributeName: BASE_URI_ATTRIBUTE,
        labelKey: BASE_URI_RESOURCE_KEY,
        fallbackLabel: DEFAULT_BASE_URI_LABEL,
        dataAttribute: "data-rdfexport-base-uri-field",
      },
    ];

    const fieldStates: FieldState[] = [];

    const buildTextOption = (
      label: string,
      dataAttribute: string,
      options?: { inputMarginRight?: string },
    ): { optionElement: HTMLElement; input: HTMLInputElement } => {
      const optionElement: HTMLElement =
        createOption != null
          ? createOption(
              label,
              () => true,
              () => undefined,
            )
          : (() => {
              const option = document.createElement("div");
              option.style.display = "flex";
              option.style.alignItems = "center";
              option.style.padding = "3px 0px";
              option.style.height = "18px";

              const checkbox = document.createElement("input");
              checkbox.type = "checkbox";
              checkbox.style.margin = "1px 6px 0px 0px";
              checkbox.style.verticalAlign = "top";
              option.appendChild(checkbox);

              const fallbackLabel = document.createElement("div");
              fallbackLabel.textContent = label;
              fallbackLabel.style.display = "inline-block";
              fallbackLabel.style.whiteSpace = "nowrap";
              fallbackLabel.style.textOverflow = "ellipsis";
              fallbackLabel.style.overflow = "hidden";
              fallbackLabel.style.maxWidth = "160px";
              fallbackLabel.style.userSelect = "none";
              option.appendChild(fallbackLabel);

              return option;
            })();

      optionElement.setAttribute(dataAttribute, "true");
      optionElement.style.position = "relative";
      optionElement.style.height = "auto";
      optionElement.style.minHeight = "18px";
      optionElement.style.alignItems = "center";
      optionElement.style.width = "100%";
      optionElement.style.flexWrap = "nowrap";

      if (!optionElement.style.display) {
        optionElement.style.display = "flex";
      }

      const collectChildren = (element: any): any[] => {
        if (!element) {
          return [];
        }

        const children = (element as { children?: any }).children;

        if (Array.isArray(children)) {
          return [...children];
        }

        if (
          children != null &&
          typeof (children as { length?: number }).length === "number"
        ) {
          return Array.from(children as ArrayLike<any>);
        }

        return [];
      };

      const isElementNode = (node: any): node is HTMLElement => {
        return (
          node != null &&
          typeof node === "object" &&
          typeof (node as any).tagName === "string"
        );
      };

      const getTagName = (node: any): string | null => {
        if (!isElementNode(node)) {
          return null;
        }

        const rawTag = (node as { tagName: string }).tagName;
        return typeof rawTag === "string" ? rawTag.toUpperCase() : null;
      };

      const optionChildren =
        collectChildren(optionElement).filter(isElementNode);

      const checkbox = optionChildren.find((child) => {
        if (getTagName(child) !== "INPUT") {
          return false;
        }

        const inputNode = child as HTMLInputElement & { type?: string };
        const explicitType =
          typeof inputNode.type === "string"
            ? inputNode.type
            : typeof (inputNode as any).getAttribute === "function"
              ? (inputNode as any).getAttribute("type")
              : undefined;

        return (explicitType ?? "").toLowerCase() === "checkbox";
      }) as (HTMLInputElement & { style: CSSStyleDeclaration }) | undefined;

      if (checkbox) {
        checkbox.setAttribute("disabled", "disabled");
        checkbox.disabled = true;
        checkbox.style.visibility = "hidden";
        checkbox.style.marginRight = "6px";
        checkbox.style.flex = "0 0 auto";
      }

      const existingLabel = optionChildren.find(
        (child) => getTagName(child) === "DIV",
      );

      if (
        existingLabel &&
        typeof (optionElement as any).removeChild === "function"
      ) {
        (optionElement as any).removeChild(existingLabel);
      }

      const labelElement = document.createElement("label");
      labelElement.textContent = label;
      labelElement.title = label;
      labelElement.setAttribute("title", label);
      labelElement.style.display = "inline-block";
      labelElement.style.whiteSpace = "nowrap";
      labelElement.style.textOverflow = "ellipsis";
      labelElement.style.overflow = "hidden";
      labelElement.style.maxWidth = "160px";
      labelElement.style.userSelect = "none";
      labelElement.style.marginRight = "6px";
      labelElement.style.cursor = "default";
      labelElement.style.flex = "0 0 auto";
      optionElement.appendChild(labelElement);

      const input = document.createElement("input");
      input.type = "text";
      input.setAttribute("type", "text");
      input.placeholder = label;
      input.setAttribute("placeholder", label);
      input.setAttribute("aria-label", label);
      input.setAttribute("autocomplete", "off");
      input.style.flex = "1 1 auto";
      input.style.minWidth = "0";
      input.style.height = "22px";
      input.style.boxSizing = "border-box";
      input.style.marginLeft = "6px";
      input.style.padding = "3px 6px";
      input.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
      input.style.borderRadius = "2px";
      input.style.background = "var(--geBackgroundColor, #ffffff)";
      input.style.color = "var(--geLabelColor, #000000)";
      input.style.fontSize = "12px";
      if (options?.inputMarginRight) {
        input.style.marginRight = options.inputMarginRight;
      }
      input.autocomplete = "off";

      const suffix = dataAttribute.replace(/[^a-z0-9]/gi, "");
      const inputId = `rdfexport-${suffix}-${Date.now().toString(36)}-${Math.floor(
        Math.random() * 1e6,
      )}`;
      input.id = inputId;
      input.setAttribute("id", inputId);
      labelElement.setAttribute("for", inputId);

      optionElement.appendChild(input);

      return { optionElement, input };
    };

    const getRootCell = (): any | null => {
      try {
        return model.getRoot();
      } catch (e) {
        return null;
      }
    };

    const readAttribute = (attributeName: string): string => {
      const rootCell = getRootCell();
      if (!rootCell) {
        return "";
      }

      const stored = graph.getAttributeForCell(rootCell, attributeName, "");
      return stored != null ? stored : "";
    };

    const updateInputsFromModel = (): void => {
      for (const field of fieldStates) {
        field.input.value = readAttribute(field.attributeName);
      }
    };

    const applyInputValue = (field: FieldState): void => {
      const rootCell = getRootCell();

      if (!rootCell) {
        return;
      }

      try {
        ensureRootCellMetadataElement(model, rootCell);
      } catch (error) {
        // ignore failures when normalising the metadata container before writes
      }

      const normalizedRaw = field.input.value.trim();
      const newValue = normalizedRaw.length > 0 ? normalizedRaw : null;
      const currentValue =
        graph.getAttributeForCell(rootCell, field.attributeName, "") || null;

      if (currentValue !== newValue) {
        model.beginUpdate?.();
        try {
          graph.setAttributeForCell(rootCell, field.attributeName, newValue);
        } finally {
          model.endUpdate?.();
        }
      }

      if (newValue === null && field.input.value !== "") {
        field.input.value = "";
      } else if (newValue !== null && field.input.value !== newValue) {
        field.input.value = newValue;
      }
    };

    for (const config of textFieldConfigs) {
      const label = resolveLabel(config.labelKey, config.fallbackLabel);
      const { optionElement, input } = buildTextOption(
        label,
        config.dataAttribute,
        {
          inputMarginRight: "6px",
        },
      );
      const fieldState: FieldState = {
        attributeName: config.attributeName,
        input,
      };

      fieldStates.push(fieldState);
      input.value = readAttribute(config.attributeName);

      input.addEventListener("change", () => {
        applyInputValue(fieldState);
      });
      input.addEventListener("blur", () => {
        applyInputValue(fieldState);
      });
      input.addEventListener("keydown", (evt) => {
        const keyboardEvent = evt as KeyboardEvent;
        if (keyboardEvent.key === "Enter") {
          applyInputValue(fieldState);
        }
      });

      preambleSection.appendChild(optionElement);
    }

    const openPreambleDialog = (): void => {
      if (!ui || typeof document === "undefined") {
        return;
      }

      const rootCell = getRootCell();
      if (!rootCell) {
        return;
      }

      const dialog = createPreambleDialog(ui, model, rootCell, {
        prefixPlaceholder: resolveLabel(
          PREAMBLE_PREFIX_PLACEHOLDER_KEY,
          DEFAULT_PREFIX_PLACEHOLDER,
        ),
        iriPlaceholder: resolveLabel(
          PREAMBLE_IRI_PLACEHOLDER_KEY,
          DEFAULT_IRI_PLACEHOLDER,
        ),
        addButtonLabel: resolveLabel(
          PREAMBLE_ADD_BUTTON_RESOURCE_KEY,
          DEFAULT_ADD_PREFIX_LABEL,
        ),
      });

      if (!dialog) {
        return;
      }

      ui.showDialog?.(dialog.container, 480, 420, true, true, null, false);
      dialog.init?.();
    };

    const preambleButtonLabel = resolveLabel(
      PREAMBLE_BUTTON_RESOURCE_KEY,
      DEFAULT_PREAMBLE_BUTTON_LABEL,
    );

    const preambleButton = ((): HTMLElement => {
      if (typeof mxUtils.button === "function") {
        return mxUtils.button(preambleButtonLabel, () => {
          openPreambleDialog();
        });
      }

      const button = document.createElement("button");
      button.textContent = preambleButtonLabel;
      button.addEventListener("click", () => {
        openPreambleDialog();
      });
      return button;
    })();

    preambleButton.setAttribute("data-rdfexport-preamble-button", "true");
    preambleButton.style.marginTop = "8px";
    preambleButton.style.width = "210px";
    preambleButton.style.display = "block";
    preambleButton.style.textAlign = "center";
    (preambleButton as HTMLElement).className =
      (preambleButton as HTMLElement).className || "geButton";
    preambleSection.appendChild(preambleButton);

    const openParserSettingsDialog = (): void => {
      if (!ui) {
        return;
      }

      const rootCell = getRootCell();
      if (!rootCell) {
        return;
      }

      const dialog = createParserSettingsDialog(ui, graph, model, rootCell);
      if (!dialog) {
        return;
      }

      ui.showDialog?.(dialog.container, 520, 520, true, true, null, false);
      dialog.init?.();
    };

    const parserSettingsLabel = resolveLabel(
      PARSER_SETTINGS_BUTTON_RESOURCE_KEY,
      DEFAULT_PARSER_SETTINGS_BUTTON_LABEL,
    );

    const parserSettingsButton = ((): HTMLElement => {
      if (typeof mxUtils.button === "function") {
        return mxUtils.button(parserSettingsLabel, () => {
          openParserSettingsDialog();
        });
      }

      const button = document.createElement("button");
      button.textContent = parserSettingsLabel;
      button.addEventListener("click", () => {
        openParserSettingsDialog();
      });
      return button;
    })();

    parserSettingsButton.setAttribute(PARSER_SETTINGS_BUTTON_ATTRIBUTE, "true");
    parserSettingsButton.style.marginTop = "6px";
    parserSettingsButton.style.width = "210px";
    parserSettingsButton.style.display = "block";
    parserSettingsButton.style.textAlign = "center";
    (parserSettingsButton as HTMLElement).className =
      (parserSettingsButton as HTMLElement).className || "geButton";
    preambleSection.appendChild(parserSettingsButton);

    const panelContainer:
      | (HTMLElement & {
          insertBefore?: (node: Node, child: Node | null) => Node;
        })
      | null = ((this as { container?: HTMLElement }).container ?? null) as
      | (HTMLElement & {
          insertBefore?: (node: Node, child: Node | null) => Node;
        })
      | null;

    const findFormatSectionAncestor = (
      node: Node | null,
    ):
      | (Node & {
          className?: string;
          parentNode: Node & {
            insertBefore?: (node: Node, child: Node | null) => Node;
            appendChild?: (node: Node) => Node;
          };
        })
      | null => {
      let current: Node | null = node;
      while (current) {
        const candidate: any = current;
        const className =
          typeof candidate?.className === "string" ? candidate.className : "";
        if (className.split(/\s+/).includes("geFormatSection")) {
          return candidate;
        }
        current = current.parentNode ?? null;
      }
      return null;
    };

    const optionsSection = findFormatSectionAncestor(container);
    const fallbackParent = (optionsSection?.parentNode ??
      container.parentNode ??
      null) as
      | (Node & {
          insertBefore?: (node: Node, child: Node | null) => Node;
          appendChild?: (node: Node) => Node;
        })
      | null;

    let inserted = false;

    if (panelContainer && typeof panelContainer.insertBefore === "function") {
      const firstChild = panelContainer.firstChild as ChildNode | null;
      const referenceChild =
        firstChild === preambleSection
          ? (preambleSection as ChildNode)
          : firstChild;
      panelContainer.insertBefore(preambleSection, referenceChild ?? null);
      inserted = preambleSection.parentNode === panelContainer;
    }

    if (!inserted) {
      const referenceNode: Node | null = optionsSection
        ? (optionsSection as unknown as Node)
        : fallbackParent && container.parentNode === fallbackParent
          ? (container as unknown as Node)
          : null;

      if (fallbackParent && typeof fallbackParent.insertBefore === "function") {
        fallbackParent.insertBefore(preambleSection, referenceNode);
        inserted = preambleSection.parentNode === fallbackParent;
      } else if (
        fallbackParent &&
        typeof fallbackParent.appendChild === "function"
      ) {
        fallbackParent.appendChild(preambleSection);
        inserted = preambleSection.parentNode === fallbackParent;
      }
    }

    const ensurePanelPlacement = () => {
      if (
        !panelContainer ||
        typeof panelContainer.insertBefore !== "function"
      ) {
        return;
      }

      const firstChild = panelContainer.firstChild as ChildNode | null;
      const referenceChild =
        firstChild === preambleSection
          ? (preambleSection as ChildNode)
          : firstChild;
      if (
        preambleSection.parentNode !== panelContainer ||
        referenceChild !== preambleSection
      ) {
        panelContainer.insertBefore(preambleSection, referenceChild ?? null);
      }
    };

    if (!inserted) {
      ensurePanelPlacement();

      if (
        preambleSection.parentNode !== panelContainer &&
        typeof window !== "undefined" &&
        typeof window.setTimeout === "function"
      ) {
        window.setTimeout(() => {
          ensurePanelPlacement();
        }, 0);
      }
    }

    updateInputsFromModel();

    if (
      typeof model.addListener === "function" &&
      typeof model.removeListener === "function"
    ) {
      const listenersArray: Array<{ destroy(): void }> | null = Array.isArray(
        (this as any).listeners,
      )
        ? ((this as any).listeners as Array<{ destroy(): void }>)
        : null;

      const changeHandler = () => {
        updateInputsFromModel();
      };

      model.addListener("change", changeHandler);

      listenersArray?.push({
        destroy: () => {
          model.removeListener(changeHandler);
        },
      });
    }

    return result;
  };

  csvPropertyPatched = true;
}

interface PreambleDialogLabels {
  prefixPlaceholder: string;
  iriPlaceholder: string;
  addButtonLabel: string;
}

interface PreambleEntry {
  prefix: string;
  iri: string;
}

function isElementNode(node: any): node is Element {
  return (
    node != null &&
    typeof node === "object" &&
    (node as Node).nodeType === mxConstants.NODETYPE_ELEMENT
  );
}

function normalizeNodeName(node: Element): string {
  const rawName = node.localName ?? node.nodeName ?? "";
  if (typeof rawName !== "string") {
    return "";
  }

  const separatorIndex = rawName.indexOf(":");
  if (separatorIndex >= 0) {
    return rawName.substring(separatorIndex + 1);
  }

  return rawName;
}

function nodeNameEquals(node: Element, expected: string): boolean {
  return normalizeNodeName(node).toLowerCase() === expected.toLowerCase();
}

function ensureCanonicalMetadataElementInPlace(element: Element): void {
  const existingId = element.getAttribute("id");
  if (!existingId || existingId.length === 0) {
    element.setAttribute("id", "0");
  }

  let hasMxCellChild = false;
  let child: ChildNode | null = element.firstChild;
  while (child != null) {
    if (
      child.nodeType === mxConstants.NODETYPE_ELEMENT &&
      nodeNameEquals(child as Element, MXCELL_TAG_NAME)
    ) {
      hasMxCellChild = true;
      break;
    }
    child = child.nextSibling;
  }

  if (!hasMxCellChild) {
    const ownerDoc = element.ownerDocument ?? mxUtils.createXmlDocument();
    element.appendChild(ownerDoc.createElement(MXCELL_TAG_NAME));
  }
}

function cloneAsCanonicalMetadataElement(
  source: Element | null,
  fallbackLabel: string | null,
): Element {
  const ownerDoc = source?.ownerDocument ?? mxUtils.createXmlDocument();
  const canonical = ownerDoc.createElement(METADATA_TAG_NAME);

  if (source) {
    if (source.attributes) {
      for (let index = 0; index < source.attributes.length; index += 1) {
        const attribute = source.attributes.item(index);
        if (attribute) {
          canonical.setAttribute(attribute.name, attribute.value);
        }
      }
    }

    let child: ChildNode | null = source.firstChild;
    while (child != null) {
      canonical.appendChild(child.cloneNode(true));
      child = child.nextSibling;
    }
  } else if (fallbackLabel && fallbackLabel.length > 0) {
    canonical.setAttribute("label", fallbackLabel);
  }

  ensureCanonicalMetadataElementInPlace(canonical);
  return canonical;
}

function ensureRootCellMetadataElement(
  model: MxGraphModel,
  rootCell: any,
): Element | null {
  const existing = extractValueElement(model, rootCell);
  if (existing && nodeNameEquals(existing, METADATA_TAG_NAME)) {
    ensureCanonicalMetadataElementInPlace(existing);
    return existing;
  }

  let fallbackLabel: string | null = null;
  if (typeof model.getValue === "function") {
    try {
      const rawValue = model.getValue(rootCell);
      if (typeof rawValue === "string" && rawValue.length > 0) {
        fallbackLabel = rawValue;
      }
    } catch (error) {
      // ignore failures to read the label and fall back to metadata defaults
    }
  }

  const canonical = cloneAsCanonicalMetadataElement(existing, fallbackLabel);

  model.beginUpdate?.();
  try {
    if (typeof model.setValue === "function") {
      model.setValue(rootCell, canonical);
    } else {
      (rootCell as { value?: any }).value = canonical;
      (model as { markDirty?: () => void }).markDirty?.();
    }
  } finally {
    model.endUpdate?.();
  }

  return canonical;
}

function metadataCandidateHasPayload(node: Element): boolean {
  const csvPath = node.getAttribute(CSV_PATH_ATTRIBUTE) ?? "";
  const baseUri = node.getAttribute(BASE_URI_ATTRIBUTE) ?? "";
  const parserSettings =
    node.getAttribute(PARSER_SETTINGS_ATTRIBUTE_NAME) ?? "";

  if (csvPath.length > 0 || baseUri.length > 0 || parserSettings.length > 0) {
    return true;
  }

  for (const tag of [PREAMBLE_ENTRY_TAG, PREAMBLE_ENTRY_TAG_LEGACY]) {
    if (node.getElementsByTagName(tag).length > 0) {
      return true;
    }
  }

  return false;
}

function ensureGraphXmlMetadataNode(graphXml: Element): Element | null {
  if (typeof graphXml.getElementsByTagName !== "function") {
    return null;
  }

  const canonicalNodes = graphXml.getElementsByTagName(METADATA_TAG_NAME);
  for (let index = 0; index < canonicalNodes.length; index += 1) {
    const node = canonicalNodes.item(index);
    if (!node || node.getAttribute("id") !== "0") {
      continue;
    }
    ensureCanonicalMetadataElementInPlace(node);
    return node;
  }

  const rootNodes = graphXml.getElementsByTagName("root");
  const graphRoot = rootNodes.item(0);

  if (!graphRoot) {
    return null;
  }

  let fallback: Element | null = null;
  for (let index = 0; index < graphRoot.childNodes.length; index += 1) {
    const child = graphRoot.childNodes.item(index);
    if (child?.nodeType !== mxConstants.NODETYPE_ELEMENT) {
      continue;
    }

    const element = child as Element;
    const normalized = normalizeNodeName(element).toLowerCase();

    if (normalized === METADATA_TAG_NAME.toLowerCase()) {
      ensureCanonicalMetadataElementInPlace(element);
      return element;
    }

    if (
      LEGACY_METADATA_TAG_NAMES.some(
        (name) => name.toLowerCase() === normalized,
      )
    ) {
      if (element.getAttribute("id") === "0") {
        fallback = element;
        break;
      }

      if (!fallback && metadataCandidateHasPayload(element)) {
        fallback = element;
      }
    }
  }

  if (!fallback) {
    return null;
  }

  const canonical = cloneAsCanonicalMetadataElement(fallback, null);
  const parent = fallback.parentNode;

  if (parent) {
    parent.replaceChild(canonical, fallback);
  }

  return canonical;
}

function extractPreambleEntries(value: any): PreambleEntry[] {
  const entries: PreambleEntry[] = [];

  if (!isElementNode(value)) {
    return entries;
  }

  let child: ChildNode | null = value.firstChild;

  while (child != null) {
    if (
      child.nodeType === mxConstants.NODETYPE_ELEMENT &&
      (nodeNameEquals(child as Element, PREAMBLE_ENTRY_TAG) ||
        nodeNameEquals(child as Element, PREAMBLE_ENTRY_TAG_LEGACY))
    ) {
      const element = child as Element;
      const prefix = element.getAttribute(PREAMBLE_PREFIX_ATTRIBUTE) ?? "";
      const iri = element.getAttribute(PREAMBLE_IRI_ATTRIBUTE) ?? "";
      entries.push({ prefix, iri });
    }

    child = child.nextSibling;
  }

  return entries;
}

function buildValueWithPreamble(
  baseValue: any,
  entries: PreambleEntry[],
): Element {
  const baseElement = isElementNode(baseValue) ? (baseValue as Element) : null;
  const fallbackLabel =
    !isElementNode(baseValue) &&
    typeof baseValue === "string" &&
    baseValue.length > 0
      ? baseValue
      : null;

  const valueElement = cloneAsCanonicalMetadataElement(
    baseElement,
    fallbackLabel,
  );

  const ownerDoc = valueElement.ownerDocument ?? mxUtils.createXmlDocument();

  if (valueElement.ownerDocument == null) {
    ownerDoc.appendChild(valueElement);
  }

  let child = valueElement.firstChild;
  while (child != null) {
    const next = child.nextSibling;
    if (
      child.nodeType === mxConstants.NODETYPE_ELEMENT &&
      (nodeNameEquals(child as Element, PREAMBLE_ENTRY_TAG) ||
        nodeNameEquals(child as Element, PREAMBLE_ENTRY_TAG_LEGACY))
    ) {
      valueElement.removeChild(child);
    }
    child = next;
  }

  for (const entry of entries) {
    const prefix = entry.prefix.trim();
    const iri = entry.iri.trim();

    if (!prefix || !iri) {
      continue;
    }

    const doc = valueElement.ownerDocument ?? ownerDoc;
    const preambleElement = doc.createElement(PREAMBLE_ENTRY_TAG);
    preambleElement.setAttribute(PREAMBLE_PREFIX_ATTRIBUTE, prefix);
    preambleElement.setAttribute(PREAMBLE_IRI_ATTRIBUTE, iri);
    valueElement.appendChild(preambleElement);
  }

  return valueElement;
}

function createParserSettingsDialog(
  editorUi: EditorUi,
  graph: MxGraph,
  model: MxGraphModel,
  rootCell: any,
): { container: HTMLElement; init(): void } | null {
  if (typeof document === "undefined") {
    return null;
  }

  const resolveMetadataElement = (): Element | null => {
    try {
      return ensureRootCellMetadataElement(model, rootCell);
    } catch (error) {
      const valueElement = extractValueElement(model, rootCell);
      if (valueElement) {
        ensureCanonicalMetadataElementInPlace(valueElement);
        return valueElement;
      }
      return null;
    }
  };

  const initialMetadataElement = resolveMetadataElement();

  const settings = readParserSettingsFromGraphInstance(graph, model, rootCell);

  const container = document.createElement("div");
  container.setAttribute(PARSER_SETTINGS_DIALOG_ATTRIBUTE, "true");
  container.style.position = "relative";
  container.style.width = "100%";
  container.style.height = "100%";

  const scrollArea = document.createElement("div");
  scrollArea.style.position = "absolute";
  scrollArea.style.top = "30px";
  scrollArea.style.left = "30px";
  scrollArea.style.right = "30px";
  scrollArea.style.bottom = "80px";
  scrollArea.style.overflowY = "auto";
  scrollArea.style.display = "flex";
  scrollArea.style.flexDirection = "column";
  scrollArea.style.gap = "14px";
  container.appendChild(scrollArea);

  const createSection = (title: string): HTMLElement => {
    const section = document.createElement("div");
    section.style.display = "flex";
    section.style.flexDirection = "column";
    section.style.gap = "8px";

    const heading = document.createElement("div");
    heading.textContent = title;
    heading.style.fontWeight = "bold";
    heading.style.fontSize = "13px";
    section.appendChild(heading);

    return section;
  };

  const createCheckboxRow = (
    label: string,
    initial: boolean,
    dataAttribute: string,
  ): { container: HTMLElement; input: HTMLInputElement } => {
    const row = document.createElement("label");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "8px";
    row.style.cursor = "pointer";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = initial;
    checkbox.defaultChecked = initial;
    checkbox.setAttribute(dataAttribute, "true");
    row.appendChild(checkbox);

    const text = document.createElement("span");
    text.textContent = label;
    text.style.flex = "1 1 auto";
    row.appendChild(text);

    return { container: row, input: checkbox };
  };

  const createLabeledInput = (
    section: HTMLElement,
    label: string,
    initial: string | null,
    dataAttribute: string,
    options?: { type?: string; step?: string },
  ): HTMLInputElement => {
    const wrapper = document.createElement("div");
    wrapper.style.display = "flex";
    wrapper.style.flexDirection = "column";
    wrapper.style.gap = "4px";

    const labelElement = document.createElement("label");
    labelElement.textContent = label;
    labelElement.style.fontSize = "12px";
    labelElement.style.fontWeight = "500";
    wrapper.appendChild(labelElement);

    const input = document.createElement("input");
    input.type = options?.type ?? "text";
    if (options?.step) {
      input.step = options.step;
    }
    input.value = initial ?? "";
    input.setAttribute(dataAttribute, "true");
    input.style.height = "26px";
    input.style.padding = "4px 6px";
    input.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    input.style.borderRadius = "2px";
    input.style.boxSizing = "border-box";
    input.style.fontSize = "12px";
    input.autocomplete = "off";

    const inputId = `rdfexport-parser-${dataAttribute}-${Math.random()
      .toString(36)
      .slice(2)}`;
    input.id = inputId;
    labelElement.htmlFor = inputId;

    wrapper.appendChild(input);
    section.appendChild(wrapper);
    return input;
  };

  const createSelect = <T extends string>(
    section: HTMLElement,
    label: string,
    options: Array<{ value: T; label: string }>,
    initial: T,
    dataAttribute: string,
  ): HTMLSelectElement => {
    const wrapper = document.createElement("div");
    wrapper.style.display = "flex";
    wrapper.style.flexDirection = "column";
    wrapper.style.gap = "4px";

    const labelElement = document.createElement("label");
    labelElement.textContent = label;
    labelElement.style.fontSize = "12px";
    labelElement.style.fontWeight = "500";
    wrapper.appendChild(labelElement);

    const select = document.createElement("select");
    select.setAttribute(dataAttribute, "true");
    select.style.height = "28px";
    select.style.padding = "4px 6px";
    select.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    select.style.borderRadius = "2px";
    select.style.fontSize = "12px";

    for (const option of options) {
      const element = document.createElement("option");
      element.value = option.value;
      element.textContent = option.label;
      select.appendChild(element);
    }

    if (!options.some((option) => option.value === initial)) {
      select.value = options[0]?.value ?? "";
    } else {
      select.value = initial;
    }

    const selectId = `rdfexport-parser-select-${Math.random()
      .toString(36)
      .slice(2)}`;
    select.id = selectId;
    labelElement.htmlFor = selectId;

    wrapper.appendChild(select);
    section.appendChild(wrapper);
    return select;
  };

  const generalSection = createSection("General behaviour");
  scrollArea.appendChild(generalSection);

  const includePreambleRow = createCheckboxRow(
    "Include preamble block in output",
    settings.includePreamble,
    PARSER_SETTINGS_INCLUDE_PREAMBLE_ATTRIBUTE,
  );
  generalSection.appendChild(includePreambleRow.container);
  const includePreambleCheckbox = includePreambleRow.input;

  const includeLabelRow = createCheckboxRow(
    "Include rdfs:label annotations",
    settings.includeLabel,
    PARSER_SETTINGS_INCLUDE_LABEL_ATTRIBUTE,
  );
  generalSection.appendChild(includeLabelRow.container);
  const includeLabelCheckbox = includeLabelRow.input;

  const inferTypesRow = createCheckboxRow(
    "Infer literal datatypes",
    settings.inferTypeOfLiterals,
    PARSER_SETTINGS_INFER_TYPES_ATTRIBUTE,
  );
  generalSection.appendChild(inferTypesRow.container);
  const inferTypesCheckbox = inferTypesRow.input;

  const strictModeRow = createCheckboxRow(
    "Enable strict arrow parsing",
    settings.strictMode,
    PARSER_SETTINGS_STRICT_MODE_ATTRIBUTE,
  );
  generalSection.appendChild(strictModeRow.container);
  const strictModeCheckbox = strictModeRow.input;

  const stripHtmlRow = createCheckboxRow(
    "Strip HTML tags from literal values",
    settings.stripHtml,
    PARSER_SETTINGS_STRIP_HTML_ATTRIBUTE,
  );
  generalSection.appendChild(stripHtmlRow.container);
  const stripHtmlCheckbox = stripHtmlRow.input;

  const identifiersSection = createSection("Identifiers");
  scrollArea.appendChild(identifiersSection);

  const prefixInput = createLabeledInput(
    identifiersSection,
    "Generated individual prefix",
    settings.prefix,
    PARSER_SETTINGS_PREFIX_ATTRIBUTE,
  );

  const prefixIriInput = createLabeledInput(
    identifiersSection,
    "Prefix IRI",
    settings.prefixIri,
    PARSER_SETTINGS_PREFIX_IRI_ATTRIBUTE,
  );

  const ontologyIriInput = createLabeledInput(
    identifiersSection,
    "Ontology IRI",
    settings.ontologyIri,
    PARSER_SETTINGS_ONTOLOGY_IRI_ATTRIBUTE,
  );

  const formattingSection = createSection("Formatting");
  scrollArea.appendChild(formattingSection);

  const indentationInput = createLabeledInput(
    formattingSection,
    "Indentation (spaces)",
    String(settings.indentation),
    PARSER_SETTINGS_INDENTATION_ATTRIBUTE,
    { type: "number" },
  );
  indentationInput.min = "0";

  const maxGapInput = createLabeledInput(
    formattingSection,
    "Maximum gap for loose arrows",
    String(settings.maxGap),
    PARSER_SETTINGS_MAX_GAP_ATTRIBUTE,
    { type: "number", step: "0.1" },
  );
  maxGapInput.min = "0";

  const capitalisationSelect = createSelect(
    formattingSection,
    "Capitalisation scheme",
    CAPITALISATION_SCHEME_OPTIONS,
    settings.capitalisationScheme,
    PARSER_SETTINGS_CAPITALISATION_ATTRIBUTE,
  );

  const metacharSection = createSection("Metacharacter substitution");
  scrollArea.appendChild(metacharSection);

  const strategySelect = createSelect(
    metacharSection,
    "Default handling",
    METACHARACTER_STRATEGY_OPTIONS,
    settings.metacharacterStrategy,
    PARSER_SETTINGS_STRATEGY_ATTRIBUTE,
  );

  type MetacharEntryState = {
    container: HTMLElement;
    select: HTMLSelectElement;
    replacement: HTMLInputElement;
  };

  const entriesList = document.createElement("div");
  entriesList.style.display = "flex";
  entriesList.style.flexDirection = "column";
  entriesList.style.gap = "6px";
  entriesList.setAttribute(PARSER_SETTINGS_METACHAR_LIST_ATTRIBUTE, "true");
  metacharSection.appendChild(entriesList);

  const entries: MetacharEntryState[] = [];

  const addEntry = (character: string, replacement: string) => {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "8px";
    row.setAttribute(PARSER_SETTINGS_METACHAR_ENTRY_ATTRIBUTE, "true");

    const charSelect = document.createElement("select");
    charSelect.style.flex = "0 0 140px";
    charSelect.style.height = "28px";
    charSelect.style.padding = "4px 6px";
    charSelect.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    charSelect.style.borderRadius = "2px";
    charSelect.style.fontSize = "12px";
    charSelect.setAttribute(PARSER_SETTINGS_METACHAR_CHAR_ATTRIBUTE, "true");

    const ensureOption = (value: string, label: string) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      charSelect.appendChild(option);
    };

    for (const option of METACHARACTER_OPTIONS) {
      ensureOption(option.value, option.label);
    }

    if (!METACHARACTER_OPTIONS.some((option) => option.value === character)) {
      const fallbackLabel =
        character === " "
          ? "Space ( )"
          : character === "\u00a0"
            ? "Non-breaking space"
            : character;
      ensureOption(character, fallbackLabel);
    }

    charSelect.value = character;

    const replacementInput = document.createElement("input");
    replacementInput.type = "text";
    replacementInput.value = replacement;
    replacementInput.style.flex = "1 1 auto";
    replacementInput.style.height = "26px";
    replacementInput.style.padding = "4px 6px";
    replacementInput.style.border =
      "1px solid var(--geInputBorderColor, #d5d5d5)";
    replacementInput.style.borderRadius = "2px";
    replacementInput.style.fontSize = "12px";
    replacementInput.setAttribute(
      PARSER_SETTINGS_METACHAR_REPLACEMENT_ATTRIBUTE,
      "true",
    );

    let state: MetacharEntryState;

    const removeEntry = () => {
      const index = entries.indexOf(state);
      if (index >= 0) {
        entries.splice(index, 1);
      }
      if (row.parentNode) {
        row.parentNode.removeChild(row);
      }
    };

    const removeButton = ((): HTMLElement => {
      if (typeof mxUtils.button === "function") {
        return mxUtils.button("Remove", () => {
          removeEntry();
        });
      }
      const button = document.createElement("button");
      button.textContent = "Remove";
      button.addEventListener("click", () => {
        removeEntry();
      });
      return button;
    })();
    removeButton.setAttribute(
      PARSER_SETTINGS_METACHAR_REMOVE_ATTRIBUTE,
      "true",
    );
    removeButton.className =
      (removeButton as HTMLElement).className || "geButton";

    state = {
      container: row,
      select: charSelect,
      replacement: replacementInput,
    };

    row.appendChild(charSelect);
    row.appendChild(replacementInput);
    row.appendChild(removeButton);
    entriesList.appendChild(row);
    entries.push(state);
  };

  if (settings.metacharacterEntries.length > 0) {
    for (const entry of settings.metacharacterEntries) {
      addEntry(entry.character, entry.replacement);
    }
  }

  const addButtonContainer = document.createElement("div");
  addButtonContainer.style.display = "flex";
  addButtonContainer.style.justifyContent = "flex-end";

  const addButton = ((): HTMLElement => {
    if (typeof mxUtils.button === "function") {
      return mxUtils.button("Add substitution", () => {
        addEntry(" ", "");
      });
    }
    const button = document.createElement("button");
    button.textContent = "Add substitution";
    button.addEventListener("click", () => {
      addEntry(" ", "");
    });
    return button;
  })();

  addButton.setAttribute(PARSER_SETTINGS_METACHAR_ADD_ATTRIBUTE, "true");
  addButton.className = (addButton as HTMLElement).className || "geButton";
  addButtonContainer.appendChild(addButton);
  metacharSection.appendChild(addButtonContainer);

  const buttons = document.createElement("div");
  buttons.style.position = "absolute";
  buttons.style.left = "30px";
  buttons.style.right = "30px";
  buttons.style.bottom = "30px";
  buttons.style.height = "40px";
  buttons.style.display = "flex";
  buttons.style.alignItems = "center";
  buttons.style.justifyContent = "flex-end";
  buttons.style.gap = "10px";
  container.appendChild(buttons);

  const cancelLabel = resolveLabel("cancel", "Cancel");
  const cancelButton = ((): HTMLElement => {
    if (typeof mxUtils.button === "function") {
      return mxUtils.button(cancelLabel, () => {
        editorUi.hideDialog?.();
      });
    }
    const button = document.createElement("button");
    button.textContent = cancelLabel;
    button.addEventListener("click", () => {
      editorUi.hideDialog?.();
    });
    return button;
  })();
  cancelButton.setAttribute(PARSER_SETTINGS_CANCEL_ATTRIBUTE, "true");
  cancelButton.className =
    (cancelButton as HTMLElement).className || "geButton";
  buttons.appendChild(cancelButton);

  const applyLabel = resolveLabel("apply", "Apply");

  const handleApply = () => {
    const indentationRaw = indentationInput.value.trim();
    const maxGapRaw = maxGapInput.value.trim();

    const partialSettings: Partial<ParserSettings> = {
      includePreamble: includePreambleCheckbox.checked,
      includeLabel: includeLabelCheckbox.checked,
      inferTypeOfLiterals: inferTypesCheckbox.checked,
      strictMode: strictModeCheckbox.checked,
      stripHtml: stripHtmlCheckbox.checked,
      prefix: prefixInput.value,
      prefixIri: prefixIriInput.value,
      ontologyIri: ontologyIriInput.value,
      capitalisationScheme: capitalisationSelect.value as CapitalisationScheme,
      metacharacterStrategy: strategySelect.value as MetacharacterStrategy,
      metacharacterEntries: entries.map((entry) => ({
        character: entry.select.value,
        replacement: entry.replacement.value,
      })),
    };

    if (indentationRaw.length > 0) {
      partialSettings.indentation = Number(indentationRaw);
    }

    if (maxGapRaw.length > 0) {
      partialSettings.maxGap = Number(maxGapRaw);
    }

    const updatedSettings = normaliseParserSettings(partialSettings);

    writeParserSettingsToGraphInstance(graph, model, rootCell, updatedSettings);
    editorUi.hideDialog?.();
  };

  const applyButton = ((): HTMLElement => {
    if (typeof mxUtils.button === "function") {
      return mxUtils.button(applyLabel, () => {
        handleApply();
      });
    }
    const button = document.createElement("button");
    button.textContent = applyLabel;
    button.addEventListener("click", () => {
      handleApply();
    });
    return button;
  })();

  applyButton.setAttribute(PARSER_SETTINGS_APPLY_ATTRIBUTE, "true");
  const applyElement = applyButton as HTMLElement;
  if (applyElement.className) {
    if (!/\bgePrimaryBtn\b/.test(applyElement.className)) {
      applyElement.className += " gePrimaryBtn";
    }
  } else {
    applyElement.className = "geButton gePrimaryBtn";
  }
  buttons.appendChild(applyButton);

  const dialog = {
    container,
    init() {
      prefixInput.focus?.();
    },
  };

  return dialog;
}

function createPreambleDialog(
  editorUi: EditorUi,
  model: MxGraphModel,
  rootCell: any,
  labels: PreambleDialogLabels,
): { container: HTMLElement; init(): void } | null {
  if (typeof document === "undefined") {
    return null;
  }

  const resolveMetadataElement = (): Element | null => {
    try {
      return ensureRootCellMetadataElement(model, rootCell);
    } catch (error) {
      const valueElement = extractValueElement(model, rootCell);
      if (valueElement) {
        ensureCanonicalMetadataElementInPlace(valueElement);
        return valueElement;
      }
      return null;
    }
  };

  const initialMetadataElement = resolveMetadataElement();

  const container = document.createElement("div");
  container.setAttribute("data-rdfexport-preamble-dialog", "true");
  container.style.position = "relative";
  container.style.width = "100%";
  container.style.height = "100%";

  const top = document.createElement("div");
  top.style.position = "absolute";
  top.style.top = "30px";
  top.style.left = "30px";
  top.style.right = "30px";
  top.style.bottom = "80px";
  top.style.overflowY = "auto";
  top.style.display = "flex";
  top.style.flexDirection = "column";
  top.style.gap = "6px";
  container.appendChild(top);

  const entriesList = document.createElement("div");
  entriesList.style.display = "flex";
  entriesList.style.flexDirection = "column";
  entriesList.style.gap = "6px";
  top.appendChild(entriesList);

  type EntryState = {
    container: HTMLElement;
    prefixInput: HTMLInputElement;
    iriInput: HTMLInputElement;
  };

  const entries: EntryState[] = [];

  const removeEntry = (entry: EntryState): void => {
    const index = entries.indexOf(entry);
    if (index >= 0) {
      entries.splice(index, 1);
    }

    const parent = (entry.container as any).parentNode;
    if (parent && typeof parent.removeChild === "function") {
      parent.removeChild(entry.container);
    } else if (typeof (entry.container as any).remove === "function") {
      (entry.container as any).remove();
    }
  };

  const createTextInput = (placeholder: string): HTMLInputElement => {
    const input = document.createElement("input");
    input.type = "text";
    input.setAttribute("type", "text");
    input.placeholder = placeholder;
    input.setAttribute("placeholder", placeholder);
    input.setAttribute("autocomplete", "off");
    input.style.flex = "1 1 auto";
    input.style.minWidth = "0";
    input.style.padding = "4px";
    input.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    input.style.borderRadius = "2px";
    input.style.boxSizing = "border-box";
    input.style.height = "24px";
    return input;
  };

  const addEntry = (prefix: string, iri: string) => {
    const entryContainer = document.createElement("div");
    entryContainer.setAttribute("data-rdfexport-preamble-entry", "true");
    entryContainer.style.display = "flex";
    entryContainer.style.alignItems = "center";
    entryContainer.style.gap = "6px";

    const prefixInput = createTextInput(labels.prefixPlaceholder);
    prefixInput.setAttribute("data-rdfexport-preamble-entry-prefix", "true");
    prefixInput.style.flex = "1 1 35%";
    prefixInput.value = prefix;
    entryContainer.appendChild(prefixInput);

    const iriInput = createTextInput(labels.iriPlaceholder);
    iriInput.setAttribute("data-rdfexport-preamble-entry-iri", "true");
    iriInput.style.flex = "1 1 65%";
    iriInput.value = iri;
    entryContainer.appendChild(iriInput);

    const entryState: EntryState = {
      container: entryContainer,
      prefixInput,
      iriInput,
    };

    const removeLabel = resolveLabel("delete", "Delete");
    const removeButton = ((): HTMLElement => {
      if (typeof mxUtils.button === "function") {
        return mxUtils.button(removeLabel, () => {
          removeEntry(entryState);
        });
      }

      const button = document.createElement("button");
      button.textContent = removeLabel;
      button.addEventListener("click", () => {
        removeEntry(entryState);
      });
      return button;
    })();

    removeButton.setAttribute("data-rdfexport-preamble-entry-remove", "true");
    (removeButton as HTMLElement).className =
      (removeButton as HTMLElement).className || "geButton";
    removeButton.style.flex = "0 0 auto";
    removeButton.style.height = "24px";
    removeButton.style.padding = "0px 8px";
    entryContainer.appendChild(removeButton);

    entries.push(entryState);
    entriesList.appendChild(entryContainer);
  };

  const baseValue =
    initialMetadataElement ??
    (typeof model.getValue === "function" ? model.getValue(rootCell) : null);
  for (const entry of extractPreambleEntries(baseValue)) {
    addEntry(entry.prefix, entry.iri);
  }

  const addRow = document.createElement("div");
  addRow.setAttribute("data-rdfexport-preamble-add-row", "true");
  addRow.style.display = "flex";
  addRow.style.alignItems = "center";
  addRow.style.gap = "6px";
  addRow.style.marginTop = "6px";
  top.appendChild(addRow);

  const newPrefixInput = createTextInput(labels.prefixPlaceholder);
  newPrefixInput.setAttribute("data-rdfexport-preamble-prefix-input", "true");
  newPrefixInput.style.flex = "1 1 35%";
  addRow.appendChild(newPrefixInput);

  const newIriInput = createTextInput(labels.iriPlaceholder);
  newIriInput.setAttribute("data-rdfexport-preamble-iri-input", "true");
  newIriInput.style.flex = "1 1 65%";
  addRow.appendChild(newIriInput);

  const handleAdd = () => {
    const prefix = newPrefixInput.value.trim();
    const iri = newIriInput.value.trim();

    if (!prefix || !iri) {
      return;
    }

    addEntry(prefix, iri);
    newPrefixInput.value = "";
    newIriInput.value = "";
    updateAddButtonState();
  };

  const addButton = ((): HTMLElement => {
    if (typeof mxUtils.button === "function") {
      return mxUtils.button(labels.addButtonLabel, () => {
        handleAdd();
      });
    }

    const button = document.createElement("button");
    button.textContent = labels.addButtonLabel;
    button.addEventListener("click", () => {
      handleAdd();
    });
    return button;
  })();

  addButton.setAttribute("data-rdfexport-preamble-add-button", "true");
  (addButton as HTMLElement).className =
    (addButton as HTMLElement).className || "geButton";
  addButton.style.flex = "0 0 auto";
  addButton.style.whiteSpace = "nowrap";
  addButton.style.height = "28px";
  addRow.appendChild(addButton);

  const updateAddButtonState = () => {
    const prefix = newPrefixInput.value.trim();
    const iri = newIriInput.value.trim();

    if (prefix && iri) {
      addButton.removeAttribute("disabled");
    } else {
      addButton.setAttribute("disabled", "disabled");
    }
  };

  newPrefixInput.addEventListener("input", updateAddButtonState);
  newIriInput.addEventListener("input", updateAddButtonState);
  newPrefixInput.addEventListener("change", updateAddButtonState);
  newIriInput.addEventListener("change", updateAddButtonState);
  newIriInput.addEventListener("keydown", (evt) => {
    const keyboardEvent = evt as KeyboardEvent;
    if (keyboardEvent.key === "Enter") {
      handleAdd();
    }
  });

  const handleApply = () => {
    const normalizedEntries = entries
      .map((entry) => ({
        prefix: entry.prefixInput.value.trim(),
        iri: entry.iriInput.value.trim(),
      }))
      .filter((entry) => entry.prefix.length > 0 && entry.iri.length > 0);

    const metadataElement = resolveMetadataElement();
    const baseValue =
      metadataElement ??
      (typeof model.getValue === "function" ? model.getValue(rootCell) : null);

    const newValue = buildValueWithPreamble(baseValue, normalizedEntries);

    model.beginUpdate?.();
    try {
      if (typeof model.setValue === "function") {
        model.setValue(rootCell, newValue);
      } else {
        (rootCell as { value?: any }).value = newValue;
        (model as { markDirty?: () => void }).markDirty?.();
      }
    } finally {
      model.endUpdate?.();
    }

    editorUi.hideDialog?.();
  };

  const buttons = document.createElement("div");
  buttons.style.position = "absolute";
  buttons.style.left = "30px";
  buttons.style.right = "30px";
  buttons.style.bottom = "30px";
  buttons.style.height = "40px";
  buttons.style.display = "flex";
  buttons.style.alignItems = "center";
  buttons.style.justifyContent = "flex-end";
  buttons.style.gap = "10px";
  container.appendChild(buttons);

  const cancelLabel = resolveLabel("cancel", "Cancel");
  const cancelButton = ((): HTMLElement => {
    if (typeof mxUtils.button === "function") {
      return mxUtils.button(cancelLabel, () => {
        editorUi.hideDialog?.();
      });
    }

    const button = document.createElement("button");
    button.textContent = cancelLabel;
    button.addEventListener("click", () => {
      editorUi.hideDialog?.();
    });
    return button;
  })();

  cancelButton.setAttribute("data-rdfexport-preamble-cancel", "true");
  (cancelButton as HTMLElement).className =
    (cancelButton as HTMLElement).className || "geButton";
  buttons.appendChild(cancelButton);

  const applyLabel = resolveLabel("apply", "Apply");
  const applyButton = ((): HTMLElement => {
    if (typeof mxUtils.button === "function") {
      return mxUtils.button(applyLabel, () => {
        handleApply();
      });
    }

    const button = document.createElement("button");
    button.textContent = applyLabel;
    button.addEventListener("click", () => {
      handleApply();
    });
    return button;
  })();

  applyButton.setAttribute("data-rdfexport-preamble-apply", "true");
  const applyButtonElement = applyButton as HTMLElement;
  if (applyButtonElement.className) {
    if (!/\bgePrimaryBtn\b/.test(applyButtonElement.className)) {
      applyButtonElement.className += " gePrimaryBtn";
    }
  } else {
    applyButtonElement.className = "geButton gePrimaryBtn";
  }
  buttons.appendChild(applyButton);

  const dialog = {
    container,
    init() {
      updateAddButtonState();

      if (entries.length > 0) {
        entries[0]?.prefixInput.focus?.();
      } else {
        newPrefixInput.focus?.();
      }
    },
  };

  return dialog;
}

installCsvPathProperty();

Draw.loadPlugin(function (editorUi: any): void {
  installCsvPathProperty();

  function serializeDiagramXml(
    ui: any,
    options?: SerializeDiagramOptions,
  ): string {
    const graphXml = ui.editor.getGraphXml();
    const workingGraphXml = cloneGraphXml(graphXml);

    ensureGraphXmlMetadataNode(workingGraphXml);

    const rmlEnabled = options?.rmlEnabled === true;
    applyRmlEnabledMetadata(workingGraphXml, rmlEnabled);
    const stripHtml = options?.stripHtml ?? true;
    applyStripHtmlMetadata(workingGraphXml, stripHtml);

    function elementToDocument(el: Element): Document {
      if (el.ownerDocument) return el.ownerDocument; // usually fine
      const doc = document.implementation.createDocument(null, null, null);
      doc.appendChild(doc.importNode(el, true));
      return doc;
    }

    return mxUtils.getPrettyXml(elementToDocument(workingGraphXml));
  }

  mxResources.parse(
    "exportRdfXml=GBAD: Export as RDF/Turtle (.ttl)...\n" +
      "exportRml=GBAD: Export as RML (.ttl)...",
  );

  editorUi.actions.addAction("exportRdfXml", async function (): Promise<void> {
    logInfo(LOG_PREFIX.PIPELINE, "exportRdfXml action invoked");

    try {
      const parserConfig = buildParserConfigPayloadFromGraph(
        editorUi?.editor?.graph ?? null,
      );
      const serializedXml = serializeDiagramXml(editorUi, {
        rmlEnabled: false,
        stripHtml: parserConfig.strip_html,
      });
      logInfo(
        LOG_PREFIX.PIPELINE,
        `Generated DrawIO XML payload (${serializedXml.length} characters)`,
      );
      const blackBoxPayload = await runDrawioPipeline(
        serializedXml,
        parserConfig,
      );
      const filename = editorUi.getBaseFilename() + ".ttl";

      logInfo(LOG_PREFIX.PIPELINE, `Saving export payload to ${filename}`);
      editorUi.saveData(filename, "turtle", blackBoxPayload, "text/turtle");
      logInfo(LOG_PREFIX.PIPELINE, `Export pipeline completed for ${filename}`);
    } catch (e) {
      logError(LOG_PREFIX.PIPELINE, "Export pipeline failed", e);
      editorUi.handleError(e as Error);
    }
  });

  editorUi.actions.addAction("exportRml", async function (): Promise<void> {
    logInfo(LOG_PREFIX.PIPELINE, "exportRml action invoked");

    try {
      const parserConfig = buildParserConfigPayloadFromGraph(
        editorUi?.editor?.graph ?? null,
      );
      const rmlConfig: DrawioParserConfigPayload = {
        ...parserConfig,
        rml_enabled: true,
      };
      const serializedXml = serializeDiagramXml(editorUi, {
        rmlEnabled: true,
        stripHtml: parserConfig.strip_html,
      });
      logInfo(
        LOG_PREFIX.PIPELINE,
        `Generated DrawIO XML payload (${serializedXml.length} characters) for RML export`,
      );
      const blackBoxPayload = await runDrawioPipeline(serializedXml, rmlConfig);
      const filename = editorUi.getBaseFilename() + ".rml.ttl";

      logInfo(LOG_PREFIX.PIPELINE, `Saving RML export payload to ${filename}`);
      editorUi.saveData(filename, "turtle", blackBoxPayload, "text/turtle");
      logInfo(
        LOG_PREFIX.PIPELINE,
        `Export pipeline completed for ${filename} (RML mode)`,
      );
    } catch (e) {
      logError(LOG_PREFIX.PIPELINE, "Export pipeline failed", e);
      editorUi.handleError(e as Error);
    }
  });

  const exportMenu = editorUi.menus.get("exportAs");

  if (exportMenu != null) {
    const oldFunct = exportMenu.funct;

    exportMenu.funct = function (menu: any, parent: any): void {
      oldFunct.call(this, menu, parent);
      editorUi.menus.addMenuItems(
        menu,
        ["-", "exportRdfXml", "exportRml"],
        parent,
      );
    };
  }
});
