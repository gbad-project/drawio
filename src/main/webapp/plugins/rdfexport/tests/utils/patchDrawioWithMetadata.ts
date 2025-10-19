import { DOMParser, XMLSerializer } from "@xmldom/xmldom";

export interface DrawioPreambleElement {
  rdfPrefix: string;
  rdfIRI: string;
}

export interface DrawioMetadataPatchOptions {
  csvPath: string;
  baseUri: string;
  preamble: DrawioPreambleElement[];
  label?: string;
}

function assertElement<T extends Element | null>(
  element: T,
  message: string,
): asserts element is Exclude<T, null> {
  if (!element) {
    throw new Error(message);
  }
}

function collectChildElements(node: Node): Element[] {
  const elements: Element[] = [];

  for (let index = 0; index < node.childNodes.length; index += 1) {
    const child = node.childNodes.item(index);

    if (child.nodeType === child.ELEMENT_NODE) {
      elements.push(child as Element);
    }
  }

  return elements;
}

function createWhitespaceNode(document: Document, value: string): Text {
  return document.createTextNode(value);
}

export function patchDrawioWithMetadata(
  source: string,
  options: DrawioMetadataPatchOptions,
): string {
  const parser = new DOMParser({
    errorHandler: {
      error: (message: string) => {
        throw new Error(`Failed to parse drawio XML: ${message}`);
      },
    },
  });

  const document = parser.parseFromString(source, "text/xml");
  const parseErrors = document.getElementsByTagName("parsererror");

  if (parseErrors.length > 0) {
    throw new Error("Drawio XML contains parser errors");
  }

  const graphModel = document.getElementsByTagName("mxGraphModel").item(0);
  assertElement(
    graphModel,
    "Unable to locate <mxGraphModel> element in drawio document",
  );

  const graphChildren = collectChildElements(graphModel);
  const rootElement = graphChildren.find((child) => child.tagName === "root");
  assertElement(
    rootElement ?? null,
    "Unable to locate <root> element inside <mxGraphModel>",
  );

  const rootChildren = collectChildElements(rootElement);
  const existingMetadataNode = rootChildren.find(
    (child) =>
      child.tagName === "UserObject" && child.getAttribute("id") === "0",
  );

  const rootCell = rootChildren.find(
    (child) => child.tagName === "mxCell" && child.getAttribute("id") === "0",
  );

  if (!existingMetadataNode) {
    assertElement(
      rootCell ?? null,
      'Unable to locate root <mxCell id="0"> element to patch',
    );
  }

  const outerWhitespace = existingMetadataNode
    ? (() => {
        const lastChild = existingMetadataNode.lastChild;
        if (lastChild && lastChild.nodeType === lastChild.TEXT_NODE) {
          return lastChild.nodeValue ?? "\n        ";
        }
        return "\n        ";
      })()
    : (rootCell?.previousSibling?.nodeValue ?? "\n        ");

  const innerWhitespace = existingMetadataNode
    ? (() => {
        for (
          let index = 0;
          index < existingMetadataNode.childNodes.length;
          index += 1
        ) {
          const child = existingMetadataNode.childNodes.item(index);
          if (child.nodeType === child.TEXT_NODE) {
            return child.nodeValue ?? `${outerWhitespace}  `;
          }
        }
        return `${outerWhitespace}  `;
      })()
    : `${outerWhitespace}  `;

  const metadataNode =
    existingMetadataNode ?? document.createElement("UserObject");
  metadataNode.setAttribute("label", options.label ?? "");
  metadataNode.setAttribute("csvPath", options.csvPath);
  metadataNode.setAttribute("baseUri", options.baseUri);
  metadataNode.setAttribute("id", "0");

  const preservedMxCell = existingMetadataNode
    ? (() => {
        const candidate = existingMetadataNode
          .getElementsByTagName("mxCell")
          .item(0);
        return candidate ? (candidate.cloneNode(true) as Element) : null;
      })()
    : null;

  while (metadataNode.firstChild) {
    metadataNode.removeChild(metadataNode.firstChild);
  }

  metadataNode.appendChild(createWhitespaceNode(document, innerWhitespace));

  for (const preambleEntry of options.preamble) {
    const preambleNode = document.createElement("userObjectPreambleElement");
    preambleNode.setAttribute("rdfPrefix", preambleEntry.rdfPrefix);
    preambleNode.setAttribute("rdfIRI", preambleEntry.rdfIRI);
    metadataNode.appendChild(preambleNode);
    metadataNode.appendChild(createWhitespaceNode(document, innerWhitespace));
  }

  const mxCellNode = preservedMxCell ?? document.createElement("mxCell");
  metadataNode.appendChild(mxCellNode);
  metadataNode.appendChild(createWhitespaceNode(document, outerWhitespace));

  if (!existingMetadataNode) {
    assertElement(
      rootCell ?? null,
      'Unable to locate root <mxCell id="0"> element to patch',
    );
    rootElement.replaceChild(metadataNode, rootCell);
  }

  const serializer = new XMLSerializer();
  return serializer.serializeToString(document);
}
