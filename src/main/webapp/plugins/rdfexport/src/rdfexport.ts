// Originally generated with OpenAI Codex on 2025-09-15
// Ported to TypeScript with Claude Sonnet 4 on 2025-09-15

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
  setAttributeForCell(cell: any, attributeName: string, value: string | null): void;
}

interface MxPage {
  getId(): string;
}

interface MxEditor {
  getGraphXml(): Element;
  graph: MxGraph;
}

interface MxAction {
  (): void;
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
const PREAMBLE_PREFIX_ATTRIBUTE = "rdfPrefix";
const PREAMBLE_IRI_ATTRIBUTE = "rdfIRI";

import { runMockBlackBox } from './mockBlackBox';

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

    typedContainer[PREAMBLE_SECTION_FLAG] = true;

    const sectionLabel = resolveLabel(
      CSV_SECTION_RESOURCE_KEY,
      DEFAULT_CSV_SECTION_LABEL,
    );

    const createTitle =
      typeof (this as { createTitle?: (title: string) => HTMLElement }).createTitle ===
      "function"
        ? ((this as any).createTitle as (title: string) => HTMLElement).bind(this)
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
      typeof (this as { createOption?: (...args: any[]) => HTMLElement }).createOption ===
      "function"
        ? ((this as any).createOption as (
            label: string,
            isCheckedFn: () => boolean,
            setCheckedFn: (checked: boolean) => void,
            listener?: unknown,
            fn?: unknown,
          ) => HTMLElement).bind(this)
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
          ? createOption(label, () => true, () => undefined)
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

      const optionChildren = collectChildren(optionElement).filter(isElementNode);

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

      if (existingLabel && typeof (optionElement as any).removeChild === "function") {
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
      const { optionElement, input } = buildTextOption(label, config.dataAttribute, {
        inputMarginRight: "6px",
      });
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
    preambleButton.style.display = "inline-block";
    preambleButton.style.textAlign = "center";
    (preambleButton as HTMLElement).className =
      (preambleButton as HTMLElement).className || "geButton";
    preambleSection.appendChild(preambleButton);

    const panelContainer: (HTMLElement & {
      insertBefore?: (node: Node, child: Node | null) => Node;
    }) | null = ((this as { container?: HTMLElement }).container ?? null) as
      | (HTMLElement & {
          insertBefore?: (node: Node, child: Node | null) => Node;
        })
      | null;

    const findFormatSectionAncestor = (
      node: Node | null,
    ): (Node & {
      className?: string;
      parentNode: Node & {
        insertBefore?: (node: Node, child: Node | null) => Node;
        appendChild?: (node: Node) => Node;
      };
    }) | null => {
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
    const fallbackParent = (optionsSection?.parentNode ?? container.parentNode ??
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
        firstChild === preambleSection ? (preambleSection as ChildNode) : firstChild;
      panelContainer.insertBefore(preambleSection, referenceChild ?? null);
      inserted = preambleSection.parentNode === panelContainer;
    }

    if (!inserted) {
      const referenceNode: Node | null = optionsSection
        ? (optionsSection as unknown as Node)
        : fallbackParent && container.parentNode === fallbackParent
        ? (container as unknown as Node)
        : null;

      if (
        fallbackParent &&
        typeof fallbackParent.insertBefore === "function"
      ) {
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
      if (!panelContainer || typeof panelContainer.insertBefore !== "function") {
        return;
      }

      const firstChild = panelContainer.firstChild as ChildNode | null;
      const referenceChild =
        firstChild === preambleSection ? (preambleSection as ChildNode) : firstChild;
      if (preambleSection.parentNode !== panelContainer || referenceChild !== preambleSection) {
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

function extractPreambleEntries(value: any): PreambleEntry[] {
  const entries: PreambleEntry[] = [];

  if (!isElementNode(value)) {
    return entries;
  }

  let child: ChildNode | null = value.firstChild;

  while (child != null) {
    if (
      child.nodeType === mxConstants.NODETYPE_ELEMENT &&
      normalizeNodeName(child as Element) === PREAMBLE_ENTRY_TAG
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
  let valueElement: Element;

  if (isElementNode(baseValue)) {
    valueElement = (baseValue.cloneNode(true) as Element) ?? baseValue;
  } else {
    const doc = mxUtils.createXmlDocument();
    valueElement = doc.createElement("object");
    if (typeof baseValue === "string" && baseValue.length > 0) {
      valueElement.setAttribute("label", baseValue);
    }
    doc.appendChild(valueElement);
  }

  const ownerDoc = valueElement.ownerDocument ?? mxUtils.createXmlDocument();

  if (valueElement.ownerDocument == null) {
    ownerDoc.appendChild(valueElement);
  }

  let child = valueElement.firstChild;
  while (child != null) {
    const next = child.nextSibling;
    if (
      child.nodeType === mxConstants.NODETYPE_ELEMENT &&
      normalizeNodeName(child as Element) === PREAMBLE_ENTRY_TAG
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

function createPreambleDialog(
  editorUi: EditorUi,
  model: MxGraphModel,
  rootCell: any,
  labels: PreambleDialogLabels,
): { container: HTMLElement; init(): void } | null {
  if (typeof document === "undefined") {
    return null;
  }

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

  const baseValue = typeof model.getValue === "function" ? model.getValue(rootCell) : null;
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

    const baseValue = typeof model.getValue === "function"
      ? model.getValue(rootCell)
      : null;

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

  const EXAMPLE_NS = "http://example.com/ns#";
  const RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";

  const ATTRIBUTE_PRIORITY = new Map<string, number>([
    ["id", 0],
    ["value", 1],
    ["style", 2],
    ["parent", 3],
    ["source", 4],
    ["target", 5],
    ["connectable", 6],
    ["edge", 7],
    ["vertex", 8],
  ]);

  const ATTRIBUTE_PRIORITY_SIZE = ATTRIBUTE_PRIORITY.size;

  function getAttributePriority(name: string, fallbackIndex: number): number {
    const priority = ATTRIBUTE_PRIORITY.get(name);
    if (priority != null) {
      return priority;
    }

    return ATTRIBUTE_PRIORITY_SIZE + fallbackIndex;
  }

  function cloneWithExampleNamespace(node: any, doc: any): any {
    if (node == null) {
      return null;
    }

    if (node.nodeType === mxConstants.NODETYPE_ELEMENT) {
      const element = node;
      let localName = element.localName || element.nodeName;

      if (localName.indexOf(":") >= 0) {
        localName = localName.substring(localName.indexOf(":") + 1);
      }

      const newElement = doc.createElementNS(
        EXAMPLE_NS,
        "example:" + localName,
      );

      if (element.attributes != null) {
        const attributes: Array<{
          name: string;
          nodeName: string;
          value: string;
          namespaceURI: string | null;
          prefix: string | null;
          index: number;
        }> = [];

        for (let i = 0; i < element.attributes.length; i++) {
          const attr = element.attributes[i];

          if (attr != null) {
            const attrName = attr.name ?? attr.nodeName;

            // Skip dx/dy on mxGraphModel because they change randomly on different machines/deployments
            if (
              localName === "mxGraphModel" &&
              (attrName === "dx" || attrName === "dy")
            ) {
              continue;
            }

            attributes.push({
              name: attrName,
              nodeName: attr.nodeName ?? attrName,
              value: attr.value ?? "",
              namespaceURI: attr.namespaceURI ?? null,
              prefix: attr.prefix ?? null,
              index: i,
            });
          }
        }

        attributes.sort((a, b) => {
          const priorityA = getAttributePriority(a.name, a.index);
          const priorityB = getAttributePriority(b.name, b.index);

          if (priorityA !== priorityB) {
            return priorityA - priorityB;
          }

          if (a.index !== b.index) {
            return a.index - b.index;
          }

          return a.name.localeCompare(b.name);
        });

        for (const attr of attributes) {
          if (attr.prefix != null && attr.prefix.length > 0) {
            newElement.setAttributeNS(
              attr.namespaceURI,
              attr.nodeName,
              attr.value,
            );
          } else {
            newElement.setAttribute(attr.name, attr.value);
          }
        }
      }

      let child = node.firstChild;

      while (child != null) {
        const childClone = cloneWithExampleNamespace(child, doc);

        if (childClone != null) {
          newElement.appendChild(childClone);
        }

        child = child.nextSibling;
      }

      return newElement;
    } else if (node.nodeType === mxConstants.NODETYPE_TEXT) {
      return doc.createTextNode(node.nodeValue || "");
    } else if (node.nodeType === mxConstants.NODETYPE_CDATA) {
      return doc.createCDATASection(node.nodeValue || "");
    }

    return null;
  }

  function createRdfXml(ui: any): string {
    const graphXml = ui.editor.getGraphXml();
    const doc = mxUtils.createXmlDocument();
    const rdfRoot = doc.createElementNS(RDF_NS, "rdf:RDF");

    rdfRoot.setAttribute("xmlns:rdf", RDF_NS);
    rdfRoot.setAttribute("xmlns:example", EXAMPLE_NS);
    rdfRoot.setAttribute("xmlns", RDF_NS); // for test to work
    doc.appendChild(rdfRoot);

    const diagramElement = doc.createElementNS(EXAMPLE_NS, "example:Diagram");
    const pageId =
      ui.currentPage != null && typeof ui.currentPage.getId === "function"
        ? ui.currentPage.getId()
        : "diagram";

    diagramElement.setAttributeNS(RDF_NS, "rdf:about", "urn:diagram:" + pageId);
    diagramElement.setAttribute("xmlns", EXAMPLE_NS); // for test to work
    rdfRoot.appendChild(diagramElement);

    const titleElement = doc.createElementNS(EXAMPLE_NS, "example:Title");
    titleElement.appendChild(doc.createTextNode(ui.getBaseFilename(true)));
    diagramElement.appendChild(titleElement);

    const modelElement = cloneWithExampleNamespace(graphXml, doc);

    if (modelElement != null) {
      diagramElement.appendChild(modelElement);
    }

    return mxUtils.getPrettyXml(doc);
  }

  mxResources.parse("exportRdfXml=GBAD: Export as RDF/XML...");

  editorUi.actions.addAction("exportRdfXml", function (): void {
    try {
      const serializedRdf = createRdfXml(editorUi);
      const blackBoxPayload = runMockBlackBox(serializedRdf);
      const filename = editorUi.getBaseFilename() + ".rdf";
      editorUi.saveData(
        filename,
        "rdf",
        blackBoxPayload,
        "application/rdf+xml",
      );
    } catch (e) {
      editorUi.handleError(e as Error);
    }
  });

  const exportMenu = editorUi.menus.get("exportAs");

  if (exportMenu != null) {
    const oldFunct = exportMenu.funct;

    exportMenu.funct = function (menu: any, parent: any): void {
      oldFunct.call(this, menu, parent);
      editorUi.menus.addMenuItems(menu, ["-", "exportRdfXml"], parent);
    };
  }
});
