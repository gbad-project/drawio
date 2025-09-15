# RDF/XML Export Plugin

The RDF/XML export plugin adds a proof-of-concept exporter that serializes the
current diagram to a lightweight RDF/XML document where every Draw.io element is
copied into the `example` namespace.

## Enabling the plugin

You can load the plugin in any Draw.io build that includes this repository:

* **URL parameter** – append `?p=rdf` (or add `&p=rdf` to an existing query) to
the editor URL. Reload the editor to load the plugin immediately.
* **Plugins dialog** – open **Extras → Plugins…**, choose **Add**, enter `rdf`,
and confirm. The plugin becomes active after reloading the editor.

## Exporting to RDF/XML

Once the plugin is active, a new entry **File → Export as → Export as RDF/XML…**
appears. Selecting it immediately downloads a `.rdf` file. The file name is
based on the current diagram name.

## Output characteristics

* The RDF/XML document declares the namespaces `rdf` and `example`.
* A root `<example:Diagram>` element is created for the current page with a
  stable `rdf:about` identifier (`urn:diagram:{pageId}`).
* The existing Draw.io `<mxGraphModel>` tree is cloned under the
  `<example:Diagram>` node, but every element is recreated in the `example`
  namespace. Attribute names and values are preserved verbatim.
* The exporter intentionally avoids using additional RDF tooling so that the
  plugin remains small and dependency free.

Because this exporter is intentionally blunt, the resulting document is a good
starting point for experimentation rather than a production-ready serialization.
