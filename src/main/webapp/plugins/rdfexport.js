/**
 * RDF/XML export plugin.
 */
Draw.loadPlugin(function(editorUi)
{
        var EXAMPLE_NS = 'http://example.com/ns#';
        var RDF_NS = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';

        function cloneWithExampleNamespace(node, doc)
        {
                if (node == null)
                {
                        return null;
                }

                if (node.nodeType == mxConstants.NODETYPE_ELEMENT)
                {
                        var localName = node.localName || node.nodeName;

                        if (localName.indexOf(':') >= 0)
                        {
                                localName = localName.substring(localName.indexOf(':') + 1);
                        }

                        var element = doc.createElementNS(EXAMPLE_NS, 'example:' + localName);

                        if (node.attributes != null)
                        {
                                for (var i = 0; i < node.attributes.length; i++)
                                {
                                        var attr = node.attributes[i];

                                        if (attr != null)
                                        {
                                                if (attr.prefix != null && attr.prefix.length > 0)
                                                {
                                                        element.setAttributeNS(attr.namespaceURI, attr.name, attr.value);
                                                }
                                                else
                                                {
                                                        element.setAttribute(attr.name, attr.value);
                                                }
                                        }
                                }
                        }

                        var child = node.firstChild;

                        while (child != null)
                        {
                                var childClone = cloneWithExampleNamespace(child, doc);

                                if (childClone != null)
                                {
                                        element.appendChild(childClone);
                                }

                                child = child.nextSibling;
                        }

                        return element;
                }
                else if (node.nodeType == mxConstants.NODETYPE_TEXT)
                {
                        return doc.createTextNode(node.nodeValue);
                }
                else if (node.nodeType == mxConstants.NODETYPE_CDATA)
                {
                        return doc.createCDATASection(node.nodeValue);
                }

                return null;
        };

        function createRdfXml(editorUi)
        {
                var graphXml = editorUi.editor.getGraphXml();
                var doc = mxUtils.createXmlDocument();
                var rdfRoot = doc.createElementNS(RDF_NS, 'rdf:RDF');
                rdfRoot.setAttribute('xmlns:rdf', RDF_NS);
                rdfRoot.setAttribute('xmlns:example', EXAMPLE_NS);
                doc.appendChild(rdfRoot);

                var diagramElement = doc.createElementNS(EXAMPLE_NS, 'example:Diagram');
                var pageId = (editorUi.currentPage != null && typeof editorUi.currentPage.getId === 'function') ?
                        editorUi.currentPage.getId() : 'diagram';
                diagramElement.setAttributeNS(RDF_NS, 'rdf:about', 'urn:diagram:' + pageId);
                rdfRoot.appendChild(diagramElement);

                var titleElement = doc.createElementNS(EXAMPLE_NS, 'example:Title');
                titleElement.appendChild(doc.createTextNode(editorUi.getBaseFilename(true)));
                diagramElement.appendChild(titleElement);

                var modelElement = cloneWithExampleNamespace(graphXml.documentElement, doc);

                if (modelElement != null)
                {
                        diagramElement.appendChild(modelElement);
                }

                return mxUtils.getPrettyXml(doc);
        };

        mxResources.parse('exportRdfXml=Export as RDF/XML...');

        editorUi.actions.addAction('exportRdfXml', function()
        {
                try
                {
                        var rdf = createRdfXml(editorUi);
                        var filename = editorUi.getBaseFilename() + '.rdf';
                        editorUi.saveData(filename, 'rdf', rdf, 'application/rdf+xml');
                }
                catch (e)
                {
                        editorUi.handleError(e);
                }
        });

        var exportMenu = editorUi.menus.get('exportAs');

        if (exportMenu != null)
        {
                var oldFunct = exportMenu.funct;

                exportMenu.funct = function(menu, parent)
                {
                        oldFunct.apply(this, arguments);
                        editorUi.menus.addMenuItems(menu, ['-', 'exportRdfXml'], parent);
                };
        }
});
