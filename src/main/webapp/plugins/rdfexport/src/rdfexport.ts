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

const CSV_FIELD_FLAG = "__rdfexportCsvFieldAttached";

let csvPropertyPatched = false;
let csvResourceRegistered = false;

function resolveCsvLabel(): string {
  const defaultLabel = "CSV path";

  if (!csvResourceRegistered) {
    try {
      mxResources.parse?.(`${CSV_PATH_RESOURCE_KEY}=${defaultLabel};`);
    } catch (error) {
      // ignore resource registration errors
    }

    csvResourceRegistered = true;
  }

  try {
    const label = mxResources.get?.(CSV_PATH_RESOURCE_KEY);
    if (typeof label === "string" && label.length > 0) {
      return label;
    }
  } catch (error) {
    // ignore lookup errors and fall back to the default label
  }

  return defaultLabel;
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
    const container: HTMLElement | undefined = (result ?? div) as HTMLElement | undefined;

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

    const labelText = resolveCsvLabel();

    const fieldContainer = document.createElement("div");
    fieldContainer.setAttribute("data-rdfexport-csv-field", "true");
    fieldContainer.style.display = "flex";
    fieldContainer.style.flexDirection = "column";
    fieldContainer.style.gap = "4px";
    fieldContainer.style.padding = "6px 0 6px 26px";

    const label = document.createElement("label");
    label.textContent = labelText;
    label.style.fontSize = "11px";
    label.style.userSelect = "none";
    label.style.color = "var(--geLabelColor, #000000)";

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = labelText;
    input.style.boxSizing = "border-box";
    input.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    input.style.borderRadius = "2px";
    input.style.padding = "3px 6px";
    input.style.height = "24px";
    input.style.fontSize = "12px";
    input.style.width = "100%";

    const inputId = `rdfexport-csv-path-${Date.now().toString(36)}-${Math.floor(
      Math.random() * 1e6,
    )}`;
    input.id = inputId;
    label.setAttribute("for", inputId);

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

    fieldContainer.appendChild(label);
    fieldContainer.appendChild(input);
    container.appendChild(fieldContainer);

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
