// src/rdfexport.ts
var CSV_PATH_ATTRIBUTE = "csvPath";
var BASE_URI_ATTRIBUTE = "baseUri";
var CSV_PATH_RESOURCE_KEY = "csvPath";
var BASE_URI_RESOURCE_KEY = "baseUri";
var CSV_SECTION_RESOURCE_KEY = "csvPreamble";
var PREAMBLE_BUTTON_RESOURCE_KEY = "editPreamble";
var PREAMBLE_PREFIX_PLACEHOLDER_KEY = "enterPrefix";
var PREAMBLE_IRI_PLACEHOLDER_KEY = "enterIri";
var PREAMBLE_ADD_BUTTON_RESOURCE_KEY = "addPrefix";
var PREAMBLE_SECTION_FLAG = "__rdfexportPreambleAttached";
var PREAMBLE_SECTION_DATA_ATTRIBUTE = "data-rdfexport-preamble-section";
var DEFAULT_CSV_PATH_LABEL = "CSV Path";
var DEFAULT_BASE_URI_LABEL = "Base URI";
var DEFAULT_CSV_SECTION_LABEL = "Preamble";
var DEFAULT_PREAMBLE_BUTTON_LABEL = "Edit Preamble...";
var DEFAULT_PREFIX_PLACEHOLDER = "Enter Prefix";
var DEFAULT_IRI_PLACEHOLDER = "Enter IRI";
var DEFAULT_ADD_PREFIX_LABEL = "Add Prefix";
var PREAMBLE_ENTRY_TAG = "userObjectPreambleElement";
var PREAMBLE_PREFIX_ATTRIBUTE = "rdfPrefix";
var PREAMBLE_IRI_ATTRIBUTE = "rdfIRI";
var BLACK_BOX_PREFIX = "[BLACKBOX]";
var BLACK_BOX_SUFFIX = "[/BLACKBOX]";
function runMockBlackBox(serializedXml) {
  const lengthLabel = serializedXml.length.toString(10);
  return `${BLACK_BOX_PREFIX} len=${lengthLabel}
${serializedXml}
${BLACK_BOX_SUFFIX}`;
}
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
    if (typedContainer[PREAMBLE_SECTION_FLAG]) {
      return result;
    }
    const ui = this.editorUi;
    const graph = ui?.editor?.graph;
    const model = graph?.getModel?.();
    if (!graph || !model || typeof model.getRoot !== "function" || typeof graph.getAttributeForCell !== "function" || typeof graph.setAttributeForCell !== "function") {
      return result;
    }
    typedContainer[PREAMBLE_SECTION_FLAG] = true;
    const sectionLabel = resolveLabel(CSV_SECTION_RESOURCE_KEY, DEFAULT_CSV_SECTION_LABEL);
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
    const preambleSection = document.createElement("div");
    preambleSection.className = "geFormatSection";
    preambleSection.setAttribute(PREAMBLE_SECTION_DATA_ATTRIBUTE, "true");
    preambleSection.style.padding = "12px 0px 8px 14px";
    preambleSection.style.whiteSpace = "nowrap";
    preambleSection.style.width = "100%";
    preambleSection.style.boxSizing = "border-box";
    preambleSection.appendChild(createTitle(sectionLabel));
    const createOption = typeof this.createOption === "function" ? this.createOption.bind(this) : null;
    const textFieldConfigs = [
      {
        attributeName: CSV_PATH_ATTRIBUTE,
        labelKey: CSV_PATH_RESOURCE_KEY,
        fallbackLabel: DEFAULT_CSV_PATH_LABEL,
        dataAttribute: "data-rdfexport-csv-field"
      },
      {
        attributeName: BASE_URI_ATTRIBUTE,
        labelKey: BASE_URI_RESOURCE_KEY,
        fallbackLabel: DEFAULT_BASE_URI_LABEL,
        dataAttribute: "data-rdfexport-base-uri-field"
      }
    ];
    const fieldStates = [];
    const buildTextOption = (label, dataAttribute, options) => {
      const optionElement = createOption != null ? createOption(label, () => true, () => {
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
      if (existingLabel && typeof optionElement.removeChild === "function") {
        optionElement.removeChild(existingLabel);
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
      const inputId = `rdfexport-${suffix}-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6)}`;
      input.id = inputId;
      input.setAttribute("id", inputId);
      labelElement.setAttribute("for", inputId);
      optionElement.appendChild(input);
      return { optionElement, input };
    };
    const getRootCell = () => {
      try {
        return model.getRoot();
      } catch (e) {
        return null;
      }
    };
    const readAttribute = (attributeName) => {
      const rootCell = getRootCell();
      if (!rootCell) {
        return "";
      }
      const stored = graph.getAttributeForCell(rootCell, attributeName, "");
      return stored != null ? stored : "";
    };
    const updateInputsFromModel = () => {
      for (const field of fieldStates) {
        field.input.value = readAttribute(field.attributeName);
      }
    };
    const applyInputValue = (field) => {
      const rootCell = getRootCell();
      if (!rootCell) {
        return;
      }
      const normalizedRaw = field.input.value.trim();
      const newValue = normalizedRaw.length > 0 ? normalizedRaw : null;
      const currentValue = graph.getAttributeForCell(rootCell, field.attributeName, "") || null;
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
        inputMarginRight: "6px"
      });
      const fieldState = {
        attributeName: config.attributeName,
        input
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
        const keyboardEvent = evt;
        if (keyboardEvent.key === "Enter") {
          applyInputValue(fieldState);
        }
      });
      preambleSection.appendChild(optionElement);
    }
    const openPreambleDialog = () => {
      if (!ui || typeof document === "undefined") {
        return;
      }
      const rootCell = getRootCell();
      if (!rootCell) {
        return;
      }
      const dialog = createPreambleDialog(ui, model, rootCell, {
        prefixPlaceholder: resolveLabel(PREAMBLE_PREFIX_PLACEHOLDER_KEY, DEFAULT_PREFIX_PLACEHOLDER),
        iriPlaceholder: resolveLabel(PREAMBLE_IRI_PLACEHOLDER_KEY, DEFAULT_IRI_PLACEHOLDER),
        addButtonLabel: resolveLabel(PREAMBLE_ADD_BUTTON_RESOURCE_KEY, DEFAULT_ADD_PREFIX_LABEL)
      });
      if (!dialog) {
        return;
      }
      ui.showDialog?.(dialog.container, 480, 420, true, true, null, false);
      dialog.init?.();
    };
    const preambleButtonLabel = resolveLabel(PREAMBLE_BUTTON_RESOURCE_KEY, DEFAULT_PREAMBLE_BUTTON_LABEL);
    const preambleButton = (() => {
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
    preambleButton.className = preambleButton.className || "geButton";
    preambleSection.appendChild(preambleButton);
    const panelContainer = this.container ?? null;
    const findFormatSectionAncestor = (node) => {
      let current = node;
      while (current) {
        const candidate = current;
        const className = typeof candidate?.className === "string" ? candidate.className : "";
        if (className.split(/\s+/).includes("geFormatSection")) {
          return candidate;
        }
        current = current.parentNode ?? null;
      }
      return null;
    };
    const optionsSection = findFormatSectionAncestor(container);
    const fallbackParent = optionsSection?.parentNode ?? container.parentNode ?? null;
    let inserted = false;
    if (panelContainer && typeof panelContainer.insertBefore === "function") {
      const firstChild = panelContainer.firstChild;
      const referenceChild = firstChild === preambleSection ? preambleSection : firstChild;
      panelContainer.insertBefore(preambleSection, referenceChild ?? null);
      inserted = preambleSection.parentNode === panelContainer;
    }
    if (!inserted) {
      const referenceNode = optionsSection ? optionsSection : fallbackParent && container.parentNode === fallbackParent ? container : null;
      if (fallbackParent && typeof fallbackParent.insertBefore === "function") {
        fallbackParent.insertBefore(preambleSection, referenceNode);
        inserted = preambleSection.parentNode === fallbackParent;
      } else if (fallbackParent && typeof fallbackParent.appendChild === "function") {
        fallbackParent.appendChild(preambleSection);
        inserted = preambleSection.parentNode === fallbackParent;
      }
    }
    const ensurePanelPlacement = () => {
      if (!panelContainer || typeof panelContainer.insertBefore !== "function") {
        return;
      }
      const firstChild = panelContainer.firstChild;
      const referenceChild = firstChild === preambleSection ? preambleSection : firstChild;
      if (preambleSection.parentNode !== panelContainer || referenceChild !== preambleSection) {
        panelContainer.insertBefore(preambleSection, referenceChild ?? null);
      }
    };
    if (!inserted) {
      ensurePanelPlacement();
      if (preambleSection.parentNode !== panelContainer && typeof window !== "undefined" && typeof window.setTimeout === "function") {
        window.setTimeout(() => {
          ensurePanelPlacement();
        }, 0);
      }
    }
    updateInputsFromModel();
    if (typeof model.addListener === "function" && typeof model.removeListener === "function") {
      const listenersArray = Array.isArray(this.listeners) ? this.listeners : null;
      const changeHandler = () => {
        updateInputsFromModel();
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
function isElementNode(node) {
  return node != null && typeof node === "object" && node.nodeType === mxConstants.NODETYPE_ELEMENT;
}
function normalizeNodeName(node) {
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
function extractPreambleEntries(value) {
  const entries = [];
  if (!isElementNode(value)) {
    return entries;
  }
  let child = value.firstChild;
  while (child != null) {
    if (child.nodeType === mxConstants.NODETYPE_ELEMENT && normalizeNodeName(child) === PREAMBLE_ENTRY_TAG) {
      const element = child;
      const prefix = element.getAttribute(PREAMBLE_PREFIX_ATTRIBUTE) ?? "";
      const iri = element.getAttribute(PREAMBLE_IRI_ATTRIBUTE) ?? "";
      entries.push({ prefix, iri });
    }
    child = child.nextSibling;
  }
  return entries;
}
function buildValueWithPreamble(baseValue, entries) {
  let valueElement;
  if (isElementNode(baseValue)) {
    valueElement = baseValue.cloneNode(true) ?? baseValue;
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
    if (child.nodeType === mxConstants.NODETYPE_ELEMENT && normalizeNodeName(child) === PREAMBLE_ENTRY_TAG) {
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
function createPreambleDialog(editorUi, model, rootCell, labels) {
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
  const entries = [];
  const removeEntry = (entry) => {
    const index = entries.indexOf(entry);
    if (index >= 0) {
      entries.splice(index, 1);
    }
    const parent = entry.container.parentNode;
    if (parent && typeof parent.removeChild === "function") {
      parent.removeChild(entry.container);
    } else if (typeof entry.container.remove === "function") {
      entry.container.remove();
    }
  };
  const createTextInput = (placeholder) => {
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
  const addEntry = (prefix, iri) => {
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
    const entryState = {
      container: entryContainer,
      prefixInput,
      iriInput
    };
    const removeLabel = resolveLabel("delete", "Delete");
    const removeButton = (() => {
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
    removeButton.className = removeButton.className || "geButton";
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
  const addButton = (() => {
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
  addButton.className = addButton.className || "geButton";
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
    const keyboardEvent = evt;
    if (keyboardEvent.key === "Enter") {
      handleAdd();
    }
  });
  const handleApply = () => {
    const normalizedEntries = entries.map((entry) => ({
      prefix: entry.prefixInput.value.trim(),
      iri: entry.iriInput.value.trim()
    })).filter((entry) => entry.prefix.length > 0 && entry.iri.length > 0);
    const baseValue2 = typeof model.getValue === "function" ? model.getValue(rootCell) : null;
    const newValue = buildValueWithPreamble(baseValue2, normalizedEntries);
    model.beginUpdate?.();
    try {
      if (typeof model.setValue === "function") {
        model.setValue(rootCell, newValue);
      } else {
        rootCell.value = newValue;
        model.markDirty?.();
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
  const cancelButton = (() => {
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
  cancelButton.className = cancelButton.className || "geButton";
  buttons.appendChild(cancelButton);
  const applyLabel = resolveLabel("apply", "Apply");
  const applyButton = (() => {
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
  const applyButtonElement = applyButton;
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
    }
  };
  return dialog;
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
      const serializedRdf = createRdfXml(editorUi);
      const blackBoxPayload = runMockBlackBox(serializedRdf);
      const filename = editorUi.getBaseFilename() + ".rdf";
      editorUi.saveData(filename, "rdf", blackBoxPayload, "application/rdf+xml");
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
export {
  runMockBlackBox
};
