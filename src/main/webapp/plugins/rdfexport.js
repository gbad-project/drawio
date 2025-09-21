// src/rdfexport.ts
var CSV_PATH_ATTRIBUTE = "csvPath";
var CSV_PATH_RESOURCE_KEY = "csvPath";
var CSV_SECTION_RESOURCE_KEY = "csvPreamble";
var CSV_FIELD_FLAG = "__rdfexportCsvFieldAttached";
var DEFAULT_CSV_PATH_LABEL = "CSV path";
var DEFAULT_CSV_SECTION_LABEL = "Preamble";
var csvPropertyPatched = false;
var registeredResourceKeys = new Set;
function registerResource(key, fallback) {
  if (registeredResourceKeys.has(key)) {
    return;
  }
  try {
    mxResources.parse?.(`${key}=${fallback}
`);
  } catch (error) {}
  registeredResourceKeys.add(key);
}
function resolveLabel(key, fallback) {
  registerResource(key, fallback);
  try {
    const label = mxResources.get?.(key);
    if (typeof label === "string" && label.length > 0) {
      return label;
    }
  } catch (error) {}
  return fallback;
}
function installCsvPathProperty() {
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
  DiagramFormatPanel.prototype.addOptions = function(div) {
    const result = originalAddOptions.apply(this, arguments);
    const container = result ?? div;
    if (!container || typeof document === "undefined") {
      return result;
    }
    const typedContainer = container;
    if (typedContainer[CSV_FIELD_FLAG]) {
      return result;
    }
    const ui = this.editorUi;
    const graph = ui?.editor?.graph;
    const model = graph?.getModel?.();
    if (!graph || !model || typeof model.getRoot !== "function" || typeof graph.getAttributeForCell !== "function" || typeof graph.setAttributeForCell !== "function") {
      return result;
    }
    typedContainer[CSV_FIELD_FLAG] = true;
    const sectionLabel = resolveLabel(CSV_SECTION_RESOURCE_KEY, DEFAULT_CSV_SECTION_LABEL);
    const fieldLabel = resolveLabel(CSV_PATH_RESOURCE_KEY, DEFAULT_CSV_PATH_LABEL);
    const createTitle = typeof this.createTitle === "function" ? this.createTitle.bind(this) : (title) => {
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
    const createOption = typeof this.createOption === "function" ? this.createOption.bind(this) : null;
    const optionElement = createOption ? createOption(fieldLabel, () => true, () => {
      return;
    }) : (() => {
      const option = document.createElement("div");
      option.style.display = "flex";
      option.style.alignItems = "center";
      option.style.padding = "3px 0px";
      option.style.height = "18px";
      const checkbox2 = document.createElement("input");
      checkbox2.type = "checkbox";
      checkbox2.style.margin = "1px 6px 0px 0px";
      checkbox2.style.verticalAlign = "top";
      option.appendChild(checkbox2);
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
    const collectChildren = (element) => {
      if (!element) {
        return [];
      }
      const children = element.children;
      if (Array.isArray(children)) {
        return [...children];
      }
      if (children != null && typeof children.length === "number") {
        return Array.from(children);
      }
      return [];
    };
    const isElementNode = (node) => {
      return node != null && typeof node === "object" && typeof node.tagName === "string";
    };
    const getTagName = (node) => {
      if (!isElementNode(node)) {
        return null;
      }
      const rawTag = node.tagName;
      return typeof rawTag === "string" ? rawTag.toUpperCase() : null;
    };
    const optionChildren = collectChildren(optionElement).filter(isElementNode);
    const checkbox = optionChildren.find((child) => {
      if (getTagName(child) !== "INPUT") {
        return false;
      }
      const inputNode = child;
      const explicitType = typeof inputNode.type === "string" ? inputNode.type : typeof inputNode.getAttribute === "function" ? inputNode.getAttribute("type") : undefined;
      return (explicitType ?? "").toLowerCase() === "checkbox";
    });
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
    if (existingLabel && typeof optionElement.removeChild === "function") {
      optionElement.removeChild(existingLabel);
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
    const inputId = `rdfexport-csv-path-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6)}`;
    input.id = inputId;
    input.setAttribute("id", inputId);
    labelElement.setAttribute("for", inputId);
    optionElement.appendChild(input);
    container.appendChild(optionElement);
    const getRootCell = () => {
      try {
        return model.getRoot();
      } catch (e) {
        return null;
      }
    };
    const readCsvPath = () => {
      const rootCell = getRootCell();
      if (!rootCell) {
        return "";
      }
      const stored = graph.getAttributeForCell(rootCell, CSV_PATH_ATTRIBUTE, "");
      return stored != null ? stored : "";
    };
    const updateInputFromModel = () => {
      input.value = readCsvPath();
    };
    const applyInputValue = () => {
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
      const keyboardEvent = evt;
      if (keyboardEvent.key === "Enter") {
        applyInputValue();
      }
    });
    updateInputFromModel();
    if (typeof model.addListener === "function" && typeof model.removeListener === "function") {
      const listenersArray = Array.isArray(this.listeners) ? this.listeners : null;
      const changeHandler = () => {
        updateInputFromModel();
      };
      model.addListener("change", changeHandler);
      listenersArray?.push({
        destroy: () => {
          model.removeListener(changeHandler);
        }
      });
    }
    return result;
  };
  csvPropertyPatched = true;
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
