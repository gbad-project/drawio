/**
 * RDF/XML export plugin - TypeScript version
 */

// Originally generated with OpenAI Codex on 2025-09-15
// Ported to TypeScript with Claude Sonnet 4 on 2025-09-15

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
}

interface MxPage {
  getId(): string;
}

interface MxEditor {
  getGraphXml(): Element;
}

interface MxAction {
  (this: any): void;
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
  saveData(filename: string, format: string, data: string, mimeType: string): void;
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

Draw.loadPlugin(function(editorUi: EditorUi): void {
  const EXAMPLE_NS = 'http://example.com/ns#';
  const RDF_NS = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';

  function cloneWithExampleNamespace(node: Node | null, doc: Document): Element | Text | CDATASection | null {
    if (node == null) {
      return null;
    }

    if (node.nodeType === mxConstants.NODETYPE_ELEMENT) {
      const element = node as Element;
      let localName = element.localName || element.nodeName;

      if (localName.indexOf(':') >= 0) {
        localName = localName.substring(localName.indexOf(':') + 1);
      }

      const newElement = doc.createElementNS(EXAMPLE_NS, 'example:' + localName);

      if (element.attributes != null) {
        for (let i = 0; i < element.attributes.length; i++) {
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
      return doc.createTextNode(node.nodeValue || '');
    } else if (node.nodeType === mxConstants.NODETYPE_CDATA) {
      return doc.createCDATASection(node.nodeValue || '');
    }

    return null;
  }

  function createRdfXml(editorUi: EditorUi): string {
    const graphXml = editorUi.editor.getGraphXml();
    const doc = mxUtils.createXmlDocument();
    const rdfRoot = doc.createElementNS(RDF_NS, 'rdf:RDF');
    
    rdfRoot.setAttribute('xmlns:rdf', RDF_NS);
    rdfRoot.setAttribute('xmlns:example', EXAMPLE_NS);
    doc.appendChild(rdfRoot);

    const diagramElement = doc.createElementNS(EXAMPLE_NS, 'example:Diagram');
    const pageId = (editorUi.currentPage != null && typeof editorUi.currentPage.getId === 'function') ?
      editorUi.currentPage.getId() : 'diagram';
    
    diagramElement.setAttributeNS(RDF_NS, 'rdf:about', 'urn:diagram:' + pageId);
    rdfRoot.appendChild(diagramElement);

    const titleElement = doc.createElementNS(EXAMPLE_NS, 'example:Title');
    titleElement.appendChild(doc.createTextNode(editorUi.getBaseFilename(true)));
    diagramElement.appendChild(titleElement);

    const modelElement = cloneWithExampleNamespace(graphXml, doc);

    if (modelElement != null) {
      diagramElement.appendChild(modelElement);
    }

    return mxUtils.getPrettyXml(doc);
  }

  mxResources.parse('exportRdfXml=Export as RDF/XML...');

  editorUi.actions.addAction('exportRdfXml', function(this: any): void {
    try {
      const rdf = createRdfXml(editorUi);
      const filename = editorUi.getBaseFilename() + '.rdf';
      editorUi.saveData(filename, 'rdf', rdf, 'application/rdf+xml');
    } catch (e) {
      editorUi.handleError(e as Error);
    }
  });

  const exportMenu = editorUi.menus.get('exportAs');

  if (exportMenu != null) {
    const oldFunct = exportMenu.funct;

    exportMenu.funct = function(menu: any, parent: any): void {
      oldFunct.apply(this, arguments);
      editorUi.menus.addMenuItems(menu, ['-', 'exportRdfXml'], parent);
    };
  }
});
