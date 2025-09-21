// src/rdfexport.ts
const CSV_PATH_ATTRIBUTE = "csvPath";
let csvPropertyPatched = !1;
function installCsvPathProperty() {
  if (csvPropertyPatched) {
    return;
  }
  if (typeof DiagramFormatPanel === "undefined") {
    return;
  }
  const originalAddDocumentProperties =
    DiagramFormatPanel.prototype.addDocumentProperties;
  if (typeof originalAddDocumentProperties !== "function") {
    return;
  }
  DiagramFormatPanel.prototype.addDocumentProperties = function (div) {
    const result = originalAddDocumentProperties.apply(this, arguments);
    const container = result != null ? result : div;
    if (!container || typeof document === "undefined") {
      return result;
    }
    if (this.__rdfexportCsvFieldInitialized === !0) {
      return result;
    }
    const ui = this.editorUi;
    const graph = ui && ui.editor ? ui.editor.graph : null;
    const model = graph && typeof graph.getModel === "function" ? graph.getModel() : null;
    if (!graph || !model || typeof model.getRoot !== "function") {
      return result;
    }
    this.__rdfexportCsvFieldInitialized = !0;
    const fieldContainer = document.createElement("div");
    fieldContainer.style.display = "flex";
    fieldContainer.style.flexDirection = "column";
    fieldContainer.style.paddingTop = "6px";
    fieldContainer.style.paddingRight = "16px";
    const label = document.createElement("label");
    label.textContent = "CSV path";
    label.style.fontSize = "11px";
    label.style.marginBottom = "4px";
    label.style.userSelect = "none";
    label.style.color = "var(--geLabelColor, #000000)";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Enter CSV path";
    input.style.boxSizing = "border-box";
    input.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    input.style.borderRadius = "2px";
    input.style.padding = "4px 6px";
    input.style.height = "26px";
    input.style.fontSize = "13px";
    const inputId =
      "rdfexport-csv-path-" +
      Date.now().toString(36) +
      "-" +
      Math.floor(Math.random() * 1e6);
    input.id = inputId;
    label.setAttribute("for", inputId);
    const getRootCell = () => {
      try {
        return model.getRoot();
      } catch (e) {
        return null;
      }
    };
    const readCsvPath = () => {
      const rootCell = getRootCell();
      if (!rootCell || typeof graph.getAttributeForCell !== "function") {
        return "";
      }
      const stored = graph.getAttributeForCell(rootCell, CSV_PATH_ATTRIBUTE, "");
      return null != stored ? stored : "";
    };
    const updateInputFromModel = () => {
      input.value = readCsvPath();
    };
    const applyInputValue = () => {
      const rootCell = getRootCell();
      if (!rootCell || typeof graph.setAttributeForCell !== "function") {
        return;
      }
      const normalizedRaw = input.value.trim();
      const newValue = 0 < normalizedRaw.length ? normalizedRaw : null;
      const currentValue =
        graph.getAttributeForCell(rootCell, CSV_PATH_ATTRIBUTE, "") || null;
      if (currentValue !== newValue) {
        if (typeof model.beginUpdate === "function") {
          model.beginUpdate();
        }
        try {
          graph.setAttributeForCell(rootCell, CSV_PATH_ATTRIBUTE, newValue);
        } finally {
          if (typeof model.endUpdate === "function") {
            model.endUpdate();
          }
        }
      }
      if (null === newValue && input.value !== "") {
        input.value = "";
      } else if (null !== newValue && input.value !== newValue) {
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
      if (evt && evt.key === "Enter") {
        applyInputValue();
      }
    });
    updateInputFromModel();
    fieldContainer.appendChild(label);
    fieldContainer.appendChild(input);
    container.appendChild(fieldContainer);
    if (typeof model.addListener === "function" && typeof model.removeListener === "function") {
      const listenerEntry = Array.isArray(this.listeners) ? this.listeners : null;
      const changeHandler = () => {
        updateInputFromModel();
      };
      model.addListener("change", changeHandler);
      if (listenerEntry) {
        listenerEntry.push({
          destroy: () => {
            model.removeListener(changeHandler);
          },
        });
      }
    }
    return result;
  };
  csvPropertyPatched = !0;
}
installCsvPathProperty();
Draw.loadPlugin(function(editorUi) {
  installCsvPathProperty();
  const EXAMPLE_NS = "http://example.com/ns#";
  const RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
  const ATTRIBUTE_PRIORITY = new Map([
    ["id", 0],
    ["value", 1],
    ["style", 2],
    ["parent", 3],
    ["source", 4],
    ["target", 5],
    ["connectable", 6],
    ["edge", 7],
    ["vertex", 8]
  ]);
  const ATTRIBUTE_PRIORITY_SIZE = ATTRIBUTE_PRIORITY.size;
  function getAttributePriority(name, fallbackIndex) {
    const priority = ATTRIBUTE_PRIORITY.get(name);
    if (priority != null) {
      return priority;
    }
    return ATTRIBUTE_PRIORITY_SIZE + fallbackIndex;
  }
  function cloneWithExampleNamespace(node, doc) {
    if (node == null) {
      return null;
    }
    if (node.nodeType === mxConstants.NODETYPE_ELEMENT) {
      const element = node;
      let localName = element.localName || element.nodeName;
      if (localName.indexOf(":") >= 0) {
        localName = localName.substring(localName.indexOf(":") + 1);
      }
      const newElement = doc.createElementNS(EXAMPLE_NS, "example:" + localName);
      if (element.attributes != null) {
        const attributes = [];
        for (let i = 0;i < element.attributes.length; i++) {
          const attr = element.attributes[i];
          if (attr != null) {
            const attrName = attr.name ?? attr.nodeName;
            if (localName === "mxGraphModel" && (attrName === "dx" || attrName === "dy")) {
              continue;
            }
            attributes.push({
              name: attrName,
              nodeName: attr.nodeName ?? attrName,
              value: attr.value ?? "",
              namespaceURI: attr.namespaceURI ?? null,
              prefix: attr.prefix ?? null,
              index: i
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
            newElement.setAttributeNS(attr.namespaceURI, attr.nodeName, attr.value);
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
  function createRdfXml(ui) {
    const graphXml = ui.editor.getGraphXml();
    const doc = mxUtils.createXmlDocument();
    const rdfRoot = doc.createElementNS(RDF_NS, "rdf:RDF");
    rdfRoot.setAttribute("xmlns:rdf", RDF_NS);
    rdfRoot.setAttribute("xmlns:example", EXAMPLE_NS);
    rdfRoot.setAttribute("xmlns", RDF_NS);
    doc.appendChild(rdfRoot);
    const diagramElement = doc.createElementNS(EXAMPLE_NS, "example:Diagram");
    const pageId = ui.currentPage != null && typeof ui.currentPage.getId === "function" ? ui.currentPage.getId() : "diagram";
    diagramElement.setAttributeNS(RDF_NS, "rdf:about", "urn:diagram:" + pageId);
    diagramElement.setAttribute("xmlns", EXAMPLE_NS);
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
  editorUi.actions.addAction("exportRdfXml", function() {
    try {
      const rdf = createRdfXml(editorUi);
      const filename = editorUi.getBaseFilename() + ".rdf";
      editorUi.saveData(filename, "rdf", rdf, "application/rdf+xml");
    } catch (e) {
      editorUi.handleError(e);
    }
  });
  const exportMenu = editorUi.menus.get("exportAs");
  if (exportMenu != null) {
    const oldFunct = exportMenu.funct;
    exportMenu.funct = function(menu, parent) {
      oldFunct.call(this, menu, parent);
      editorUi.menus.addMenuItems(menu, ["-", "exportRdfXml"], parent);
    };
  }
});
