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
const CSV_PATH_RESOURCE_KEY = "csvPath";
const CSV_SECTION_RESOURCE_KEY = "csvPreamble";

const CSV_FIELD_FLAG = "__rdfexportCsvFieldAttached";

const DEFAULT_CSV_PATH_LABEL = "CSV path";
const DEFAULT_CSV_SECTION_LABEL = "Preamble";

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
    const result = originalAddOptions.apply(this, arguments);
    const container: HTMLElement | undefined = (result ?? div) as
      | HTMLElement
      | undefined;

    if (!container || typeof document === "undefined") {
      return result;
    }

    const typedContainer = container as HTMLElement & {
      [CSV_FIELD_FLAG]?: boolean;
    };

    if (typedContainer[CSV_FIELD_FLAG]) {
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

    typedContainer[CSV_FIELD_FLAG] = true;

    const sectionLabel = resolveLabel(
      CSV_SECTION_RESOURCE_KEY,
      DEFAULT_CSV_SECTION_LABEL,
    );
    const fieldLabel = resolveLabel(CSV_PATH_RESOURCE_KEY, DEFAULT_CSV_PATH_LABEL);

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

    container.appendChild(createTitle(sectionLabel));

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

    const optionElement: HTMLElement = createOption
      ? createOption(fieldLabel, () => true, () => undefined)
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
          fallbackLabel.textContent = fieldLabel;
          fallbackLabel.style.display = "inline-block";
          fallbackLabel.style.whiteSpace = "nowrap";
          fallbackLabel.style.textOverflow = "ellipsis";
          fallbackLabel.style.overflow = "hidden";
          fallbackLabel.style.maxWidth = "160px";
          fallbackLabel.style.userSelect = "none";
          option.appendChild(fallbackLabel);

          return option;
        })();

    optionElement.setAttribute("data-rdfexport-csv-field", "true");
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

      if (children != null && typeof (children as { length?: number }).length === "number") {
        return Array.from(children as ArrayLike<any>);
      }

      return [];
    };

    const isElementNode = (node: any): node is HTMLElement => {
      return node != null && typeof node === "object" && typeof (node as any).tagName === "string";
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

    const existingLabel = optionChildren.find((child) => getTagName(child) === "DIV");

    const labelElement = document.createElement("label");
    labelElement.textContent = fieldLabel;
    labelElement.title = fieldLabel;
    labelElement.setAttribute("title", fieldLabel);
    labelElement.style.display = "inline-block";
    labelElement.style.whiteSpace = "nowrap";
    labelElement.style.textOverflow = "ellipsis";
    labelElement.style.overflow = "hidden";
    labelElement.style.maxWidth = "160px";
    labelElement.style.userSelect = "none";
    labelElement.style.marginRight = "6px";
    labelElement.style.cursor = "default";
    labelElement.style.flex = "0 0 auto";

    if (existingLabel && typeof (optionElement as any).removeChild === "function") {
      (optionElement as any).removeChild(existingLabel);
    }

    optionElement.appendChild(labelElement);

    const input = document.createElement("input");
    input.type = "text";
    input.setAttribute("type", "text");
    input.placeholder = fieldLabel;
    input.setAttribute("placeholder", fieldLabel);
    input.setAttribute("aria-label", fieldLabel);
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
    input.autocomplete = "off";

    const inputId = `rdfexport-csv-path-${Date.now().toString(36)}-${Math.floor(
      Math.random() * 1e6,
    )}`;
    input.id = inputId;
    input.setAttribute("id", inputId);
    labelElement.setAttribute("for", inputId);

    optionElement.appendChild(input);
    container.appendChild(optionElement);

    const getRootCell = (): any | null => {
      try {
        return model.getRoot();
      } catch (e) {
        return null;
      }
    };

    const readCsvPath = (): string => {
      const rootCell = getRootCell();
      if (!rootCell) {
        return "";
      }

      const stored = graph.getAttributeForCell(rootCell, CSV_PATH_ATTRIBUTE, "");
      return stored != null ? stored : "";
    };

    const updateInputFromModel = (): void => {
      input.value = readCsvPath();
    };

    const applyInputValue = (): void => {
      const rootCell = getRootCell();

      if (!rootCell) {
        return;
      }

      const normalizedRaw = input.value.trim();
      const newValue = normalizedRaw.length > 0 ? normalizedRaw : null;
      const currentValue = graph.getAttributeForCell(rootCell, CSV_PATH_ATTRIBUTE, "") || null;

      if (currentValue !== newValue) {
        model.beginUpdate?.();
        try {
          graph.setAttributeForCell(rootCell, CSV_PATH_ATTRIBUTE, newValue);
        } finally {
          model.endUpdate?.();
        }
      }

      if (newValue === null && input.value !== "") {
        input.value = "";
      } else if (newValue !== null && input.value !== newValue) {
        input.value = newValue;
      }
    };

    input.addEventListener("change", () => {
      applyInputValue();
    });
    input.addEventListener("blur", () => {
      applyInputValue();
    });
    input.addEventListener("keydown", (evt) => {
      const keyboardEvent = evt as KeyboardEvent;
      if (keyboardEvent.key === "Enter") {
        applyInputValue();
      }
    });

    updateInputFromModel();

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
        updateInputFromModel();
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
      const rdf = createRdfXml(editorUi);
      const filename = editorUi.getBaseFilename() + ".rdf";
      editorUi.saveData(filename, "rdf", rdf, "application/rdf+xml");
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
