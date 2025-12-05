import type {
  MxUtils,
  ParserSettings,
} from "../../aicode/typescript_plugin/src/rdfexport";

export const PARSER_SETTINGS_LITERAL_DEF_LIST_ATTRIBUTE =
  "data-rdfexport-parser-literal-def-list";
export const PARSER_SETTINGS_LITERAL_DEF_ENTRY_ATTRIBUTE =
  "data-rdfexport-parser-literal-def-entry";
export const PARSER_SETTINGS_LITERAL_DEF_KEY_ATTRIBUTE =
  "data-rdfexport-parser-literal-def-key";
export const PARSER_SETTINGS_LITERAL_DEF_VALUE_ATTRIBUTE =
  "data-rdfexport-parser-literal-def-value";
export const PARSER_SETTINGS_LITERAL_DEF_REMOVE_ATTRIBUTE =
  "data-rdfexport-parser-literal-def-remove";
export const PARSER_SETTINGS_LITERAL_DEF_ADD_ATTRIBUTE =
  "data-rdfexport-parser-literal-def-add";

export type LiteralDefEntryState = {
  container: HTMLElement;
  keyInput: HTMLInputElement;
  valueInput: HTMLInputElement;
};

export interface LiteralParserSettingsEntry {
  attrKey: string;
  attrVal: string;
}

export function createDefList() {
  const literalDefList = document.createElement("div");
  literalDefList.style.display = "flex";
  literalDefList.style.flexDirection = "column";
  literalDefList.style.gap = "6px";
  literalDefList.setAttribute(
    PARSER_SETTINGS_LITERAL_DEF_LIST_ATTRIBUTE,
    "true",
  );
  return literalDefList;
}

export function createLiteralDefSection(
  settings: ParserSettings,
  mxUtils: MxUtils,
  createSection: (t: string) => HTMLElement,
  literalDefEntries: LiteralDefEntryState[],
  literalDefList: HTMLDivElement,
) {
  const literalDefSection = createSection("Literal definitions");

  const addLiteralDefEntry = (attrKey: string, attrVal: string) => {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "8px";
    row.setAttribute(PARSER_SETTINGS_LITERAL_DEF_ENTRY_ATTRIBUTE, "true");

    const keyInput = document.createElement("input");
    keyInput.type = "text";
    keyInput.value = attrKey;
    keyInput.placeholder = "Attribute key (e.g., style)";
    keyInput.style.flex = "1 1 auto";
    keyInput.style.height = "26px";
    keyInput.style.padding = "4px 6px";
    keyInput.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    keyInput.style.borderRadius = "2px";
    keyInput.style.fontSize = "12px";
    keyInput.setAttribute(PARSER_SETTINGS_LITERAL_DEF_KEY_ATTRIBUTE, "true");

    const valueInput = document.createElement("input");
    valueInput.type = "text";
    valueInput.value = attrVal;
    valueInput.placeholder = "Attribute value (e.g., rounded=1)";
    valueInput.style.flex = "1 1 auto";
    valueInput.style.height = "26px";
    valueInput.style.padding = "4px 6px";
    valueInput.style.border = "1px solid var(--geInputBorderColor, #d5d5d5)";
    valueInput.style.borderRadius = "2px";
    valueInput.style.fontSize = "12px";
    valueInput.setAttribute(
      PARSER_SETTINGS_LITERAL_DEF_VALUE_ATTRIBUTE,
      "true",
    );

    let state: LiteralDefEntryState;

    const removeLiteralDefEntry = () => {
      const index = literalDefEntries.indexOf(state);
      if (index >= 0) {
        literalDefEntries.splice(index, 1);
      }
      if (row.parentNode) {
        row.parentNode.removeChild(row);
      }
    };

    const removeButton = ((): HTMLElement => {
      if (typeof mxUtils.button === "function") {
        return mxUtils.button("Remove", () => {
          removeLiteralDefEntry();
        });
      }
      const button = document.createElement("button");
      button.textContent = "Remove";
      button.addEventListener("click", () => {
        removeLiteralDefEntry();
      });
      return button;
    })();
    removeButton.setAttribute(
      PARSER_SETTINGS_LITERAL_DEF_REMOVE_ATTRIBUTE,
      "true",
    );
    removeButton.className =
      (removeButton as HTMLElement).className || "geButton";

    state = {
      container: row,
      keyInput: keyInput,
      valueInput: valueInput,
    };

    row.appendChild(keyInput);
    row.appendChild(valueInput);
    row.appendChild(removeButton);

    literalDefList.appendChild(row);
    literalDefEntries.push(state);
  };

  const literalDefAddButtonContainer = (() => {
    const literalDefAddButtonContainer = document.createElement("div");
    literalDefAddButtonContainer.style.display = "flex";
    literalDefAddButtonContainer.style.justifyContent = "flex-end";

    const literalDefAddButton = ((): HTMLElement => {
      if (typeof mxUtils.button === "function") {
        return mxUtils.button("Add literal definition", () => {
          addLiteralDefEntry("", "");
        });
      }

      const button = document.createElement("button");
      button.textContent = "Add literal definition";
      button.addEventListener("click", () => {
        addLiteralDefEntry("", "");
      });

      button.setAttribute(PARSER_SETTINGS_LITERAL_DEF_ADD_ATTRIBUTE, "true");
      button.className = (button as HTMLElement).className || "geButton";

      return button;
    })();

    literalDefAddButtonContainer.appendChild(literalDefAddButton);

    return literalDefAddButtonContainer;
  })();

  if (settings.literalDefinitions.length > 0) {
    for (const def of settings.literalDefinitions) {
      addLiteralDefEntry(def.attrKey, def.attrVal);
    }
  }

  literalDefSection.appendChild(literalDefList);
  literalDefSection.appendChild(literalDefAddButtonContainer);

  return literalDefSection;
}
