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

function collectExistingPreambleElements(
  rootElement: Element,
): DrawioPreambleElement[] {
  const entries = new Map<string, string>();

  for (const child of collectChildElements(rootElement)) {
    const tagName = child.tagName?.toLowerCase() ?? "";

    if (tagName !== "userobject" && tagName !== "object") {
      continue;
    }

    for (const preamble of collectChildElements(child)) {
      const preambleTag = preamble.tagName?.toLowerCase() ?? "";

      if (preambleTag !== "userobjectpreambleelement") {
        continue;
      }

      const prefix = preamble.getAttribute("rdfPrefix")?.trim();
      const iri = preamble.getAttribute("rdfIRI")?.trim();

      if (!prefix || !iri) {
        continue;
      }

      if (!entries.has(prefix)) {
        entries.set(prefix, iri);
      }
    }
  }

  return Array.from(entries.entries()).map(([rdfPrefix, rdfIRI]) => ({
    rdfPrefix,
    rdfIRI,
  }));
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
  const existingUserObject = rootChildren.find(
    (child) => child.tagName === "UserObject",
  );

  if (existingUserObject) {
    throw new Error(
      "Drawio document already contains a <UserObject> root metadata node",
    );
  }

  const rootCell = rootChildren.find(
    (child) => child.tagName === "mxCell" && child.getAttribute("id") === "0",
  );
  const anchorNode = rootCell ?? rootChildren[0] ?? null;
  const outerWhitespace =
    rootCell?.previousSibling?.nodeValue ??
    anchorNode?.previousSibling?.nodeValue ??
    "\n        ";
  const innerWhitespace = `${outerWhitespace}  `;

  const metadataNode = document.createElement("UserObject");
  metadataNode.setAttribute("label", options.label ?? "");
  metadataNode.setAttribute("csvPath", options.csvPath);
  metadataNode.setAttribute("baseUri", options.baseUri);
  metadataNode.setAttribute("id", "0");

  metadataNode.appendChild(createWhitespaceNode(document, innerWhitespace));

  const mergedPreamble = new Map<string, string>();
  for (const existing of collectExistingPreambleElements(rootElement)) {
    mergedPreamble.set(existing.rdfPrefix, existing.rdfIRI);
  }
  for (const preambleEntry of options.preamble) {
    mergedPreamble.set(preambleEntry.rdfPrefix, preambleEntry.rdfIRI);
  }

  for (const [rdfPrefix, rdfIRI] of mergedPreamble) {
    const preambleNode = document.createElement("userObjectPreambleElement");
    preambleNode.setAttribute("rdfPrefix", rdfPrefix);
    preambleNode.setAttribute("rdfIRI", rdfIRI);
    metadataNode.appendChild(preambleNode);
    metadataNode.appendChild(createWhitespaceNode(document, innerWhitespace));
  }

  const mxCellNode = document.createElement("mxCell");
  metadataNode.appendChild(mxCellNode);
  metadataNode.appendChild(createWhitespaceNode(document, outerWhitespace));

  if (rootCell) {
    rootElement.replaceChild(metadataNode, rootCell);
  } else if (anchorNode) {
    rootElement.insertBefore(metadataNode, anchorNode);
  } else {
    rootElement.appendChild(metadataNode);
  }

  const serializer = new XMLSerializer();
  return serializer.serializeToString(document);
}
