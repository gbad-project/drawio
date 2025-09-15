// src/rdfexport.ts
Draw.loadPlugin(function(editorUi) {
  const EXAMPLE_NS = "http://example.com/ns#";
  const RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
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
        for (let i = 0;i < element.attributes.length; i++) {
          const attr = element.attributes[i];
          if (attr != null) {
            if (attr.prefix != null && attr.prefix.length > 0) {
              newElement.setAttributeNS(attr.namespaceURI, attr.name, attr.value);
            } else {
              newElement.setAttribute(attr.name, attr.value);
            }
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
    doc.appendChild(rdfRoot);
    const diagramElement = doc.createElementNS(EXAMPLE_NS, "example:Diagram");
    const pageId = ui.currentPage != null && typeof ui.currentPage.getId === "function" ? ui.currentPage.getId() : "diagram";
    diagramElement.setAttributeNS(RDF_NS, "rdf:about", "urn:diagram:" + pageId);
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
  mxResources.parse("exportRdfXml=Export as RDF/XML...");
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
      oldFunct.apply(this, arguments);
      editorUi.menus.addMenuItems(menu, ["-", "exportRdfXml"], parent);
    };
  }
});
