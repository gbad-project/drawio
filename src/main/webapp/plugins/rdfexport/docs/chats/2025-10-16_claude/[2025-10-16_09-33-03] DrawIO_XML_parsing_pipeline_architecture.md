# DrawIO XML parsing pipeline architecture
*URL:* https://claude.ai/chat/b7309fbd-3f67-4347-ac64-f848125063cf
*Created:* 10/16/2025, 9:33:03 AM
*Updated:* 10/16/2025, 9:56:03 AM
*Exported:* 10/16/2025, 9:57:57 AM

__________

## 0 - Human
*Branch:* Main
*UUID:* `3256e159-8fdb-406c-9872-cf74d3e93b1a`
*Created:* 10/16/2025, 9:33:05 AM

attached is original script  and a meta builder that reworks this script. your point of interest is MAPPING list. it is already full in terms of that it provides full coverage, so focus only on the classifications. does everything make sense? the idea is that in the original script, there is (described clearly in main docstring) a  clearest separation that anything that happens before individuals and arrows are generated is xml level processing. additionally, some metadata processing happens at xml level (separation out of some metadata from xml tree) as well as some metadata coming from an external source (eg, argparse). so, we have metadata from xml which are partially separate (like csv_path) and partially integrated (like prefixes), and then we also have metadata from external source  which are not in the loop, which is rather a limitation than a benefit, stemming from the fact that within-xml metadata were added later on in the process. then individuals/arrows as well as applicable metadata (ideally would've been all metadata as said above but only a subset for now) are passed along into `individual_blocks` and now are at internal model stage where we are applying some processing (most importantly string parsing/edits) to individuals/arrows, based on metadata, to ultimately get a tuple of blocks, object props and data props which is really a data structure ready to produce rdflib graph. ultimately this is being leveraged in serialise to graph method - however note that this produces a pure rdflib graph and other scaffoloding (like `_build_graph_from_raw_xml`) is needed here to produce a full featured DrawIOParserGraph which includes both graph and metadata in appropriate format; the need for such a scaffolding is really in contrast with current very clear and from up to bottom approach in meta builder, but again that's because of tech debt because _build_graph_from_raw_xml was introduced earlier than metabuilder. in fact, metabuilder was inspired exactly for that reason, to make things crystal clear and concerns separated. also, there is `parse_drawio_to_graph` method that really wraps _build_graph_from_raw_xml for allowing pythonic sdk style directly from file reading (and this method is really unused currently), and then there is `_run` that wraps _build_graph_from_raw_xml for cli usage. SO! to sum up, we clearly have the following axes or like ways to structure the pipeline. in fact, what i want to change in builder is to make pre, core, post classes all nested within a new pipeline class! so what we have:

* preprocessing: data from xml (no data from internal nor rdf because these don't exist yet nor are passed from outside); metadata from xml, metadata from internal (eg coming from user), no metadata from rdf because this is not passes (but might be in the future if for example an existing rdf graph is provided for reuse of prefixes for example);  control for xml (while for data this is fully handled by xml etree, custom  processing is applied to separate out and replace metadata from xml), control for internal (like obtaining data and metadata from user through various sources except xml, to supplement individuals and arrows when they go into individual_blocks together), no control for rdf (becaause again no rdf exists at this point and none is passed in current implementatin)
* core processing: data from xml (ALL logic that takes xml -stripped of metadata UserObject node! - as input, and until individuals and arrows are produced), no data from internal (no specific processing is applied to individuals and arrows alone at this point because the idea is to process them based on metadata), no data from rdf (because rdf doesn't exist yet and as mentioned before was not passed);  no metadata from xml (as it was already processed and is not touched here);  metadata from internal (no processing applied to metadata received from for example argparse at pre stage);  no metadata from rdf (again doesnt exist nor passed); no control for xml (xml doesnt exist anymore already at this point!), control for internal (ANY logic where individuals and arrows are coupled with metadata to produce ultimate tuple of blocks and obj props and data props), no control for rdf (basically serialise_to_graph which takes outputs of control internal including blocks, obj and datatype props, as well as builds serialisation config and stuff to prepare everything for ultimate drawioparsergraph production, as well as the very drawioparsergraph class; i have to say serialise is tightly coupled and all of these things are taking place like serialisation config should prbably be separate there but that's not something we can address with metabuilder)
* post processing: none for xml nor internal data nor metadata nor control because everything is within drawioparsergraph now; for rdf there is also no data or metadata because everything is inbuilt in drawioparsergraph instance, but there is rdf control which includes wrappers over _build_graph_from_raw_xml and any secondary (ie., rdflib based) serializations or postprocessing of drawioparsergraph instance (like also adding new triples).


NOW! please provide a summary and your udnerstanding of what i said, comprehensively and with all details. draw a comprehensive mermaid diagram for flow and all these things, you may even want to create a rdf turtle graph to describe this lol because it's 3x3x4 dimensional so not really fits well in a table format lol.

FINALLY! provide me an updated MAPPING list of tuples and only it; note that you are not changing metabuilder in anyway, just editing that list.

**Attachment:** 
*ID:* `288a73be-0fdc-42f8-b862-6b5746b4d2cb`

<details>

```
# pylint: disable=too-many-lines

"""
Constructs individuals in OWL with respect to the ontology Records in Contexts
from a draw.io graph.

Intended to be run as a script: the underlying XML of the graph should be sent
into the script via stdin. A number of command line parameters are available for
configuration: run

python draw_io_parser.py --help

for a full list.

Codewise, the DrawIOXMLTree class takes a raw drawio XML string in its
constructor, and exposes only one method, 'individuals_and_arrows', which
returns as a generator all RiC-O individuals and properties (arrows) that it
finds upon parsing the tree, including, for arrows, the data of which
individuals are the source and target of the arrow. Part of the parsing is
already carried out upon calling the constructor, for effectivity.

Two further functions are exposed by the module. The method 'individual_blocks'
takes an iterator of individuals and arrows such as that outputted by the
'individuals_and_arrows' method of a DrawIOXMLTree instance, and assembles them
into a dictionary whose keys are individual IRIs. The value for a given key is
itself a dictionary, collecting together the facts and types for that individual
IRI which were defined by some Individual or Arrow instance in the iterator (the
individual IRI may occur many times in Individual instances with differing
values for the 'class' variable).

The method 'serialise' takes such a dictionary of individuals and their facts
and types, arranges each pair of a key (individual) and its values (facts and
types) into an Individual block in OWL Manchester syntax, and concatenates all
of these into one large string.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, InitVar
from datetime import datetime
from html.parser import HTMLParser
from sys import exit as sys_exit, stdin
from typing import Generator, Iterator, Optional, Dict, Any, Type
from copy import deepcopy
from xml.etree.ElementTree import Element, fromstring, tostring
import urllib.parse
import traceback
import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD


class DrawIOParserGraph(Graph):
    """Graph subclass that records Draw.io specific metadata."""

    def __init__(self, *args, csv_path: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_path = csv_path


def get_prefixes():
    return {
        "rico": "https://www.ica.org/standards/RiC/ontology#",
        "add": "https://data.archives.gov.on.test.gbad.ca/Schema/Description-Listings/",
        "auth": "https://data.archives.gov.on.test.gbad.ca/Schema/Authority/",
        "gbad": "https://data.archives.gov.on.test.gbad.ca/Schema/",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
    }


def get_ontology_iri(qname: str | None = None) -> str:
    return f"ontology://generated-from-draw-io/{
        qname or datetime.strftime(datetime.now(), '%Y-%m-%dT%H-%M-%S')
    }"


def get_prefix() -> str | None:
    return os.getenv("PREFIX")


def get_prefix_iri(ontology_iri: str | None = None) -> str:
    return os.getenv("PREFIX_IRI", f"{ontology_iri or get_ontology_iri()}#")


def _extract_drawio_metadata(
    raw_xml: str,
) -> tuple[dict[str, str], Optional[str], Optional[str], Optional[Element]]:
    """Extracts CSV path, base URI, prefixes, and returns parsed XML root."""
    try:
        root = fromstring(raw_xml)
    except Exception:  # pragma: no cover - defensive guard around XML parsing
        return {}, None, None, None

    metadata_node = root.find(".//mxGraphModel/root/UserObject[@id='0']")
    if metadata_node is None:
        return {}, None, None, root

    csv_path_raw = metadata_node.attrib.get("csvPath", "")
    base_uri_raw = metadata_node.attrib.get("baseUri", "")

    csv_path = csv_path_raw.strip() or None
    base_uri = base_uri_raw.strip() or None

    prefixes: dict[str, str] = {}
    for preamble in metadata_node.findall("userObjectPreambleElement"):
        prefix = (preamble.attrib.get("rdfPrefix") or "").strip()
        iri = (preamble.attrib.get("rdfIRI") or "").strip()
        if prefix and iri:
            prefixes[prefix] = iri

    return prefixes, base_uri, csv_path, root


def _strip_metadata_user_object(raw_xml: str, root: Optional[Element]) -> str:
    if root is None:
        return raw_xml

    working_root = deepcopy(root)
    graph_root = working_root.find(".//mxGraphModel/root")
    if graph_root is None:
        return raw_xml

    metadata_node = graph_root.find("UserObject[@id='0']")
    if metadata_node is None:
        return raw_xml

    replacement = Element("mxCell", {"id": "0"})
    children = list(graph_root)
    for index, child in enumerate(children):
        if child is metadata_node:
            graph_root.remove(metadata_node)
            graph_root.insert(index, replacement)
            break

    return tostring(working_root, encoding="unicode")


def _split_curie(curie: str) -> tuple[str, str]:
    if ":" not in curie:
        return "", ""
    prefix, remainder = curie.split(":", 1)
    return prefix, remainder.strip()


def _ensure_known_curie(
    curie: str, prefixes: dict[str, str], error_message: str
) -> tuple[str, str]:
    prefix, reference = _split_curie(curie)
    if prefix not in prefixes or not reference:
        raise NotInKnownException(error_message)
    return prefix, reference


Blocks = dict[tuple[str, str], dict[str, set[str]]]
CellID = str
XCoordinate = float
YCoordinate = float
Width = float
Height = float
ArrowStart = tuple[XCoordinate, YCoordinate]
ArrowEnd = tuple[XCoordinate, YCoordinate]
Label = str
ArrowData = tuple[Element, Optional[ArrowStart], Optional[ArrowEnd], Label]
Dimensions = tuple[XCoordinate, YCoordinate, Width, Height]
Paragraph = str
Metacharacter = str
Replacement = str


DEFAULT_CAPITALISATION_SCHEME = "upper-camel"
DEFAULT_INDENTATION = 2
DEFAULT_MAX_GAP = 10
OWL_METACHARACTERS = [
    "(",
    ")",
    "[",
    "]",
    "{",
    "}",
    "/",
    ",",
    ":",
    ".",
    "'",
    '"',
    " ",
    "#",
]


class NothingToParseException(Exception):
    """
    Can be thrown when calling the constructor of the DrawIOXMLTree class if the
    passed-in XML appears to define an empty graph
    """


class NotInKnownException(Exception):
    """
    Can be thrown if an arrow has a label which does not correspond to an
    object or datatype property in RiC-O, and if it has been specified that this
    is not to be permitted
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class _NoCellCloseEnoughException(Exception):
    pass


class NoSourceException(Exception):
    """
    Can be thrown when calling the 'individuals_and_arrows' function if a given
    arrow has no source that can be identified
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class NoTargetException(Exception):
    """
    Can be thrown when calling the 'individuals_and_arrows' function if a given
    arrow has no target that can be identified
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class _NoValueException(Exception):
    pass


class _SourceNotIndividualException(Exception):
    pass


class ArrowWithoutIndividualAsSourceException(Exception):
    """
    Can be thrown when calling the 'individuals_and_arrows' function if a given
    arrow has a source that appears not to be an individual node
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class _MetacharacterSubstituteParseException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class MetacharacterException(Exception):
    """
    Can be thrown when calling the 'individual_blocks' function if an individual
    has an identifier (the text in the upper half of an individual node)
    containing an OWL metacharacter
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class _InvalidCapitalisationSchemeException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ParseException(Exception):
    """
    Can be thrown if the XML being parsed does not have the anticipated
    structure in some respect
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass(frozen=True)
class Individual:
    """
    Represents an OWL individual with type a RiC-O class, coming from a node in
    the parsed graph
    """

    identifier: str
    ric_class: str


@dataclass(frozen=True)
class Arrow:
    """
    Represents an OWL object or datatype property with type a RiC-O class,
    coming from an arrow in the parsed graph
    """

    identifier: str
    source: str
    target: str
    is_datatype: bool


class NodeHTMLParser(HTMLParser):
    """
    Subclasses HTMLParser to define its behaviour with respect to 'handle_data',
    'handle_starttag', and 'handle_endtag' (this is the usage pattern expected
    by HTMLParser). It seems that text, including multi-line text, in draw.io
    may come in three forms: as a simple string; as a string within a blockquote
    element; or as a sequence of strings inside divs inside a blockquote. In
    the simple string case, our subclassing of the three afore-mentioned methods
    is such as to discard all information except these strings, and to collect
    them, in the sequence they are encountered in, into a list.

    The 'content' function takes such a list and collects the strings together
    into paragraphs. Single line-breaks in the original graph (corresponding
    usually to three consecutive divs, the middle one of which contains no
    string) are ignored; two or more line-breaks in the original graph will lead
    to a paragraph break.

    The 'clear' function resets the internal state of the class, and should be
    called before parsing a new chunk of HTML.
    """

    def __init__(self):
        super().__init__()
        self._chunks = []

    def handle_starttag(self, tag: str, _: list[tuple[str, str | None]]) -> None:
        if tag in ["div", "blockquote", "p", "br"]:
            # Otherwise words stick together in place of a single line break
            self._chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ["div", "blockquote", "p"]:
            # Otherwise words stick together in place of a single line break
            self._chunks.append(" ")

    def handle_data(self, data: str) -> None:
        """
        Overrides a function in HTMLParser, storing the raw data (text) inside
        a HTML element in the instance variable 'raw_data'.
        """
        # Implementing chunks universally seems to fix lost data with single <br> tags
        self._chunks.append(data)

    def _prettify_linebreaks(self) -> Generator[Paragraph, None, None]:
        # This method is unsafe because can also generate line breaks in Individuals
        previous_was_empty = False
        paragraph_already_handled = False
        current = ""
        for chunk in self._chunks:
            if not chunk:
                if current:
                    yield current
                current = ""
                if previous_was_empty and not paragraph_already_handled:
                    yield "\n\n"
                    paragraph_already_handled = True
                else:
                    previous_was_empty = True
                continue
            current += chunk
            previous_was_empty = False
            paragraph_already_handled = False
        if current:
            yield current

    def content(self) -> str:
        """
        Takes all of the string chunks (within divs and blockquotes) obtained
        during the current run of the parser, and collects them together
        into paragraphs, handling line breaks as described in the docstring
        for this class
        """
        return "".join(self._prettify_linebreaks()).strip()

    def clear(self) -> None:
        """
        Clears the internal state of the parser so that it is as though newly
        constructed
        """
        self._chunks = []


@dataclass(frozen=True)
class SerialisationConfig:
    """
    Holds various user-configurable parameters for configuring the serialisation
    to OWL outputted by the 'serialise' function
    """

    infer_type_of_literals: bool
    include_preamble: bool
    ontology_iri: str | None
    prefix: str | None
    prefix_iri: str | None
    indentation: int
    include_label: bool


@dataclass(frozen=True)
class DrawIOXMLTree:
    """
    The purpose of this class is to parse a raw draw.io XML to a list of
    instances of the Individual and Arrow classes, corresponding respectively to
    nodes and arrows in the graph which the  XML defines. The constructor takes
    such an XML string, and part of the parsing is already carried out upon
    calling the constructor, for effectivity (elements which will be looped
    over are extracted once and for all). The method
    'individuals_and_arrows' can then be called to complete the parsing and
    return the obtained Individual and Arrow instances as a generator
    """

    draw_io_xml_tree: Element = field(init=False)
    literal_node_html_parser: NodeHTMLParser = field(init=False)
    individual_cells: list[tuple[Element, Individual, Dimensions]] = field(init=False)
    arrow_cells: list[ArrowData] = field(init=False)
    literal_cells: list[tuple[Element, Dimensions]] = field(init=False)

    raw_xml: InitVar[str]
    prefixes: InitVar[dict]

    def __post_init__(self, raw_xml, prefixes):
        object.__setattr__(self, "prefixes", prefixes)
        object.__setattr__(self, "literal_node_html_parser", NodeHTMLParser())
        object.__setattr__(self, "draw_io_xml_tree", fromstring(raw_xml))
        object.__setattr__(self, "individual_cells", [])
        object.__setattr__(self, "arrow_cells", [])
        object.__setattr__(self, "literal_cells", [])
        self._extract_individual_and_arrow_and_literal_cells(prefixes)

    def _cell_with_id(self, _id: str) -> Element:
        cell = self.draw_io_xml_tree.find(f".//*[@id='{_id}']")
        if cell is None:
            raise ValueError(f"No cell with id: {_id}")
        return cell

    def _value_of(self, cell: Element) -> str:
        try:
            value = cell.attrib["value"].strip()
        except KeyError as key_error:
            raise _NoValueException from key_error
        self.literal_node_html_parser.clear()
        self.literal_node_html_parser.feed(value)
        return self.literal_node_html_parser.content()

    def _parent_of(self, cell: Element) -> Element:
        try:
            parent_id = cell.attrib["parent"]
        except KeyError as key_error:
            raise ParseException(
                "Could not parse XML tree: found an 'mxCell' element with "
                "the following id which has value beginning with 'rico:' but "
                f"with no parent: {cell.attrib['id']}"
            ) from key_error
        return self._cell_with_id(parent_id)

    def _child_of(self, parent_id: str) -> Generator[Element, None, None]:
        yield from self.draw_io_xml_tree.findall(f".//*[@parent='{parent_id}']")

    @staticmethod
    def _geometry(cell: Element) -> Element:
        try:
            for element in cell:
                if element.tag == "mxGeometry":
                    return element
        except IndexError as index_error:
            raise ParseException(
                "Expecting the cell with the following id to have an "
                "mxGeometry sub-element, but has no sub-elements at all: "
                f"{cell.attrib['id']}"
            ) from index_error
        raise ParseException(
            "Expecting the cell with the following id to have an mxGeometry "
            f"sub-element: {cell.attrib['id']}"
        )

    @staticmethod
    def _x_and_y_in_geometry(
        geometry: Element, cell_id: str
    ) -> tuple[XCoordinate, YCoordinate]:
        try:
            x = float(geometry.attrib["x"])
        except KeyError as key_error:
            raise ParseException(
                "Encountered an mxGeometry element of the cell with the "
                f"following id without an 'x' attribute: {cell_id}"
            ) from key_error
        try:
            y = float(geometry.attrib["y"])
        except KeyError as key_error:
            raise ParseException(
                "Encountered an mxGeometry element of the cell with the "
                f"following id without a 'y' attribute: {cell_id}"
            ) from key_error
        return x, y

    @staticmethod
    def _has_correct_as_attribute(
        element: Element, as_attribute: str, cell_id: str
    ) -> bool:
        try:
            return element.attrib["as"] == as_attribute
        except KeyError as key_error:
            raise ParseException(
                "Encountered an mxPoint element of the cell with the "
                f"following id without an 'as' attribute: {cell_id}"
            ) from key_error

    @staticmethod
    def _is_locked(cell: Element, as_attribute: str) -> bool:
        if as_attribute == "sourcePoint" and ("source" in cell.attrib):
            return True
        if as_attribute == "targetPoint" and ("target" in cell.attrib):
            return True
        return False

    def _start_or_end(
        self, cell: Element, as_attribute: str | None
    ) -> tuple[XCoordinate, YCoordinate] | None:
        """
        The cell can be part of a group (have another 'parent' than that of the
        top-level graph), in which case the immediate x and y coordinates will
        be relative to the parent in the group rather than absolute; recursion
        is used here to obtain absolute coordinates
        """
        geometry = DrawIOXMLTree._geometry(cell)
        if as_attribute is None:
            return self._x_and_y_in_geometry(geometry, cell.attrib["id"])
        if len(geometry) == 0:
            raise ParseException(
                "Expecting the mxGeometry element of the cell with the "
                "following id to have sub-elements, but has no sub-elements "
                f"at all: {cell.attrib['id']}"
            )
        for element in geometry:
            if element.tag != "mxPoint" or not self._has_correct_as_attribute(
                element, as_attribute, cell.attrib["id"]
            ):
                continue
            try:
                x = float(element.attrib["x"])
            except KeyError as key_error:
                if self._is_locked(cell, as_attribute):
                    return None
                raise ParseException(
                    "Encountered an mxPoint element of the cell with the "
                    "following id without an 'x' attribute: "
                    f"{cell.attrib['id']}"
                ) from key_error
            try:
                y = float(element.attrib["y"])
            except KeyError as key_error:
                if self._is_locked(cell, as_attribute):
                    return None
                raise ParseException(
                    "Encountered an mxPoint element of the cell with the "
                    "following id without a 'y' attribute: "
                    f"{cell.attrib['id']}"
                ) from key_error
            parent_id = cell.attrib["parent"]
            if parent_id == "1":
                return x, y
            parent_coordinates = self._start_or_end(self._parent_of(cell), None)
            if parent_coordinates is None:
                raise ValueError
            parent_x, parent_y = parent_coordinates
            return x + parent_x, y + parent_y
        raise ParseException(
            "Expecting the mxGeometry element of the cell with the following "
            "id to have an mxPoint sub-element with 'as' attribute having "
            f"value 'sourcePoint', but it does not: {cell.attrib['id']}"
        )

    def _arrow_start(self, arrow_cell: Element) -> ArrowStart | None:
        return self._start_or_end(arrow_cell, "sourcePoint")

    def _arrow_end(self, arrow_cell: Element) -> ArrowEnd | None:
        return self._start_or_end(arrow_cell, "targetPoint")

    @staticmethod
    def _dimensions(individual_cell: Element) -> Dimensions:
        geometry = DrawIOXMLTree._geometry(individual_cell)
        try:
            x = float(geometry.attrib["x"])
        except KeyError:
            x = 0.0
            # raise ParseException(
            #    "Expecting the mxGeometry element of the cell with the "
            #    "following id to have an 'x' attribute, but it does not: "
            #    f"{individual_cell.attrib['id']}"
            # ) from key_error
        try:
            y = float(geometry.attrib["y"])
        except KeyError:
            y = 0.0
            # raise ParseException(
            #    "Expecting the mxGeometry element of the cell with the "
            #    "following id to have a 'y' attribute, but it does not: "
            #    f"{individual_cell.attrib['id']}"
            # ) from key_error
        try:
            width = float(geometry.attrib["width"])
        except KeyError as key_error:
            raise ParseException(
                "Expecting the mxGeometry element of the cell with the "
                "following id to have a 'width' attribute, but it does not: "
                f"{individual_cell.attrib['width']}"
            ) from key_error
        try:
            height = float(geometry.attrib["height"])
        except KeyError as key_error:
            raise ParseException(
                "Expecting the mxGeometry element of the cell with the "
                "following id to have a 'height' attribute, but it does not: "
                f"{individual_cell.attrib['height']}"
            ) from key_error
        return x, y, width, height

    @staticmethod
    def _is_possible_literal(cell: Element) -> bool:
        try:
            if cell.attrib["parent"] != "1":
                return False
            return "rounded=1" in cell.attrib["style"]
        except KeyError:
            return False

    def _arrow_label(self, arrow_cell: Element) -> str:
        for cell in self._child_of(arrow_cell.attrib["id"]):
            try:
                style = cell.attrib["style"]
            except KeyError:
                continue
            if "edgeLabel" in style:
                return self._value_of(cell)
        raise _NoValueException

    def _add_arrow_if_find_label(self, cell: Element) -> None:
        try:
            label = self._arrow_label(cell)
            arrow_data = (cell, self._arrow_start(cell), self._arrow_end(cell), label)
            self.arrow_cells.append(arrow_data)
        except _NoValueException:
            pass

    def _extract_individual_and_arrow_and_literal_cells(self, prefixes) -> None:
        try:
            if len(self.draw_io_xml_tree[0][0][0]) == 0:
                raise NothingToParseException
        except IndexError as key_error:
            raise NothingToParseException from key_error
        for cell in self.draw_io_xml_tree[0][0][0]:
            if cell.tag != "mxCell":
                raise ParseException(
                    "Could not parse XML tree: expecting an element with tag "
                    f"'mxCell', but had tag '{cell.tag}'"
                )
            try:
                cell_value = self._value_of(cell)
            except _NoValueException:
                continue
            if not cell_value:
                self._add_arrow_if_find_label(cell)
                continue
            if cell_value.split(":")[0] not in self.prefixes.keys():
                if self._is_possible_literal(cell):
                    self.literal_cells.append((cell, self._dimensions(cell)))
                continue
            try:
                parent = self._parent_of(cell)
                individual_identifier = self._value_of(parent)
            except _NoValueException:
                try:
                    arrow_data = (
                        cell,
                        self._arrow_start(cell),
                        self._arrow_end(cell),
                        cell.attrib["value"],
                    )
                    self.arrow_cells.append(arrow_data)
                except _NoValueException:
                    pass
                continue
            if not individual_identifier:
                continue
            for prefix in self.prefixes.keys():
                for ric_class in cell_value.split(f"{prefix}:")[1:]:
                    ric_class = f"{prefix}:" + ric_class.strip()
                    _verify_is_ric_class(ric_class, self.prefixes)
                    individual = Individual(individual_identifier, ric_class)
                    self.individual_cells.append(
                        (cell, individual, self._dimensions(parent))
                    )
            # for ric_class in cell_value.split("rico:")[1:]:
            #    ric_class = ric_class.strip()
            #    _verify_is_ric_class(ric_class)
            #    individual = Individual(individual_identifier, ric_class)
            #    self.individual_cells.append(
            #        (cell, individual, self._dimensions(parent)))

    @staticmethod
    def _close_enough(
        arrow_endpoint: ArrowStart | ArrowEnd,
        cell_dimensions: Dimensions,
        max_gap: float,
    ) -> bool:
        endpoint_x, endpoint_y = arrow_endpoint
        cell_x, cell_y, cell_width, cell_height = cell_dimensions
        return (cell_x - max_gap <= endpoint_x <= cell_x + cell_width + max_gap) and (
            cell_y - max_gap <= endpoint_y <= cell_y + cell_height + max_gap
        )

    def _cell_close_to(
        self, arrow_endpoint: ArrowStart | ArrowEnd, max_gap: float
    ) -> Element:
        for cell, _, dimensions in self.individual_cells:
            if self._close_enough(arrow_endpoint, dimensions, max_gap):
                return cell
        for cell, dimensions in self.literal_cells:
            if self._close_enough(arrow_endpoint, dimensions, max_gap):
                return cell
        raise _NoCellCloseEnoughException

    def _defines_individual(self, identifier: str) -> bool:
        for _, individual, _ in self.individual_cells:
            if individual.identifier == identifier:
                return True
        return False

    def _cell_is_literal(self, candidate: Element) -> bool:
        return any(literal_cell is candidate for literal_cell, _ in self.literal_cells)

    def _source_or_target(
        self, source_or_target_cell: Element, must_be_individual: bool
    ) -> str:
        try:
            value = self._value_of(source_or_target_cell)
        except KeyError as key_error:
            raise _NoValueException from key_error
        if value.split(":")[0] in self.prefixes.keys():
            return self._value_of(self._parent_of(source_or_target_cell))
        if must_be_individual and not self._defines_individual(value):
            raise _SourceNotIndividualException
        return value

    def _arrow(self, arrow_data: ArrowData, strict_mode: bool, max_gap: float) -> Arrow:
        arrow_cell, arrow_start, arrow_end, arrow_label = arrow_data
        try:
            source_cell = self._cell_with_id(arrow_cell.attrib["source"])
        except KeyError as key_error:
            if strict_mode or arrow_start is None:
                raise NoSourceException(
                    f"The mxCell element with label '{arrow_label}' and id "
                    f"{arrow_cell.attrib['id']} seems to be an arrow, but its "
                    "source was not able to be determined"
                ) from key_error
            try:
                source_cell = self._cell_close_to(arrow_start, max_gap)
            except _NoCellCloseEnoughException as not_close_enough_exception:
                raise NoSourceException(
                    f"The mxCell element with label '{arrow_label}' and id "
                    f"{arrow_cell.attrib['id']} seems to be an arrow, but its "
                    "source was not able to be determined"
                ) from not_close_enough_exception
        try:
            source = self._source_or_target(source_cell, True)
        except _SourceNotIndividualException as exception:
            raise ArrowWithoutIndividualAsSourceException(
                f"The arrow with id {arrow_cell.attrib['id']} and label "
                f"{arrow_label} has a source which appears not to be a node "
                "defining a RiC-O individual"
            ) from exception
        try:
            target_cell = self._cell_with_id(arrow_cell.attrib["target"])
        except KeyError as key_error:
            if strict_mode or arrow_end is None:
                raise NoSourceException(
                    f"The mxCell element with label '{arrow_label}' and id "
                    f"{arrow_cell.attrib['id']} seems to be an arrow, but its "
                    "target was not able to be determined"
                ) from key_error
            try:
                target_cell = self._cell_close_to(arrow_end, max_gap)
            except _NoCellCloseEnoughException as not_close_enough_exception:
                raise NoSourceException(
                    f"The mxCell element with label '{arrow_label}' and id "
                    f"{arrow_cell.attrib['id']} seems to be an arrow, but its "
                    "target was not able to be determined"
                ) from not_close_enough_exception
        target = self._source_or_target(target_cell, False)
        is_datatype = self._cell_is_literal(target_cell)
        if not is_datatype and not self._defines_individual(target):
            is_datatype = True
        return Arrow(str(arrow_label.strip()), source, target, is_datatype)

    def individuals_and_arrows(
        self, strict_mode: bool, max_gap: float
    ) -> Generator[Individual | Arrow, None, None]:
        """
        Returns as a generator all Individual and Arrow instances obtained
        when parsing the nodes and arrows of the draw.io XML graph fed into the
        DrawIOXMLTree instance upon its construction
        """
        for _, individual, _ in self.individual_cells:
            yield individual
        for arrow_data in self.arrow_cells:
            yield self._arrow(arrow_data, strict_mode, max_gap)


def _verify_is_ric_class(ric_class: str, prefixes: dict[str, str]):
    _ensure_known_curie(ric_class, prefixes, f"Not a known class: {ric_class}")


def _handle_spaces(
    identifier: str, space_substitute: Replacement, capitalisation_scheme: str
) -> str:
    if capitalisation_scheme == "upper-camel":
        return f"{space_substitute}".join(
            word[0].upper() + word[1:] for word in identifier.split()
        )
    if capitalisation_scheme == "lower-camel":
        words = identifier.split()
        return f"{space_substitute}".join(
            [words[0][0].lower() + words[0][1:]]
            + [word[0].upper() + word[1:] for word in words[1:]]
        )
    if capitalisation_scheme == "flat":
        return f"{space_substitute}".join(
            word[0].lower() + word[1:] for word in identifier.split()
        )
    if capitalisation_scheme == "none":
        return f"{space_substitute}".join(identifier.split())
    raise ValueError


def _replace_metacharacter(
    metacharacter: str,
    identifier: str,
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
) -> str:
    if metacharacter not in identifier:
        return identifier
    for to_replace, replacement in metacharacter_substitutes:
        if metacharacter == to_replace:
            return identifier.replace(to_replace, replacement)
    raise MetacharacterException(
        f"The following contains the OWL metacharacter '{metacharacter}': "
        f"'{identifier}'. Use the -m/--metacharacter-substitute option, more "
        "than once if necessary, to define a character or string to substitute "
        "it with, or to specify that it should be removed"
    )


def _replace_metacharacters(
    identifier: str,
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
) -> str:
    if " " in identifier:
        if space_substitute is None:
            raise MetacharacterException(
                "The following contains a space, but how to handle spaces in "
                "individual nodes has not been specified (spaces cannot be "
                f"used in OWL IRIs): '{identifier}'. Use the "
                "-m/--metacharacter-substitute and -c/--capitalisation-scheme "
                "options to define how to handle spaces"
            )
        identifier = _handle_spaces(identifier, space_substitute, capitalisation_scheme)
    elif capitalisation_scheme in ["lower-camel", "flat"]:
        identifier = identifier[0].lower() + identifier[1:]
    for metacharacter in OWL_METACHARACTERS:
        identifier = _replace_metacharacter(
            metacharacter, identifier, metacharacter_substitutes
        )
    return identifier


def _add_individual_type(
    blocks: Blocks,
    individual: Individual,
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
) -> None:
    individual_id = _replace_metacharacters(
        individual.identifier,
        metacharacter_substitutes,
        space_substitute,
        capitalisation_scheme,
    )
    try:
        block = blocks[(individual_id, individual.identifier)]
    except KeyError:
        blocks[(individual_id, individual.identifier)] = {
            "Types": {individual.ric_class}
        }
        return
    try:
        block["Types"].add(individual.ric_class)
    except KeyError:
        block["Types"] = {individual.ric_class}


def individual_blocks(
    individuals_and_arrows: Iterator[Individual | Arrow],
    metacharacter_substitutes: list[tuple[Metacharacter, Replacement]],
    space_substitute: Replacement | None,
    capitalisation_scheme: str,
    prefixes: dict[str, str],
) -> tuple[Blocks, set[str], set[str]]:
    """
    Takes an iterator of Individual and Arrow instances, such as that outputted
    by the 'individuals_and_arrows' method of a DrawIOXMLTree instance, and
    assembles them into adictionary whose keys are individual IRIs. The value
    for a given key is itself a dictionary, collecting together the facts and
    types for that individual IRI which were defined by some Individual or Arrow
    instance in the iterator (the individual IRI may occur many times in
    Individual instances with differing values for the 'class' variable).
    """
    blocks: Blocks = {}
    object_properties: set[str] = set()
    datatype_properties: set[str] = set()
    for individual_or_arrow in individuals_and_arrows:
        if isinstance(individual_or_arrow, Individual):
            _add_individual_type(
                blocks,
                individual_or_arrow,
                metacharacter_substitutes,
                space_substitute,
                capitalisation_scheme,
            )
            continue
        _ensure_known_curie(
            individual_or_arrow.identifier,
            prefixes,
            (
                f"An arrow has label '{individual_or_arrow.identifier}', "
                "which is not a known object property or datatype property"
            ),
        )
        if individual_or_arrow.is_datatype:
            datatype_properties.add(individual_or_arrow.identifier)
            target_identifier = individual_or_arrow.target
        else:
            object_properties.add(individual_or_arrow.identifier)
            target_identifier = _replace_metacharacters(
                individual_or_arrow.target,
                metacharacter_substitutes,
                space_substitute,
                capitalisation_scheme,
            )
        source_identifier = _replace_metacharacters(
            individual_or_arrow.source,
            metacharacter_substitutes,
            space_substitute,
            capitalisation_scheme,
        )
        try:
            block = blocks[(source_identifier, individual_or_arrow.source)]
        except KeyError:
            blocks[(source_identifier, individual_or_arrow.source)] = {
                individual_or_arrow.identifier: {target_identifier}
            }
            continue
        try:
            block[individual_or_arrow.identifier].add(target_identifier)
        except KeyError:
            block[individual_or_arrow.identifier] = {target_identifier}
    return blocks, object_properties, datatype_properties


def serialise_to_graph(
    blocks: Blocks,
    object_properties: set[str],
    datatype_properties: set[str],
    serialisation_config: SerialisationConfig,
    prefixes: dict,
    graph_cls: Type[Graph] = Graph,
    graph_kwargs: Optional[Dict[str, Any]] = None,
) -> Graph:
    graph_kwargs = graph_kwargs or {}
    g = graph_cls(**graph_kwargs)

    # Bind prefixes
    for prefix, uri in prefixes.items():
        g.bind(prefix, Namespace(uri), replace=True)
    if serialisation_config.prefix:
        g.bind(
            serialisation_config.prefix,
            Namespace(
                serialisation_config.prefix_iri
                or get_prefix_iri(serialisation_config.ontology_iri)
            ),
        )

    if serialisation_config.include_preamble:
        # Add ontology definition
        ontology_iri = serialisation_config.ontology_iri
        if not ontology_iri:
            ontology_iri = get_ontology_iri()
        g.add((URIRef(ontology_iri), RDF.type, OWL.Ontology))
        g.add((URIRef(ontology_iri), OWL.imports, URIRef(prefixes["rico"])))

    # Add property definitions
    for prop in sorted(
        prop for prop in object_properties if not prop.startswith("rico:")
    ):
        prop_prefix, prop_name = prop.split(":")
        prop_uri = Namespace(prefixes[prop_prefix])[prop_name]
        g.add((prop_uri, RDF.type, OWL.ObjectProperty))

    for prop in sorted(
        prop for prop in datatype_properties if not prop.startswith("rico:")
    ):
        prop_prefix, prop_name = prop.split(":")
        prop_uri = Namespace(prefixes[prop_prefix])[prop_name]
        g.add((prop_uri, RDF.type, OWL.DatatypeProperty))

    # Add individuals and their properties
    for (individual_id, individual_label), types_and_facts in blocks.items():
        prefix = serialisation_config.prefix
        prefix_iri = serialisation_config.prefix_iri or get_prefix_iri(
            serialisation_config.ontology_iri
        )
        if prefix and prefix_iri:
            individual_uri = Namespace(prefix_iri)[individual_id]
        else:
            # Fallback to a default base URI if no prefix is defined
            base_uri = prefix_iri or get_prefix_iri(ontology_iri)
            individual_uri = URIRef(f"{base_uri}{individual_id}")

        g.add((individual_uri, RDF.type, OWL.NamedIndividual))

        # Add types
        for rdf_type in types_and_facts.get("Types", set()):
            prefix, name = rdf_type.split(":")
            g.add((individual_uri, RDF.type, Namespace(prefixes[prefix])[name]))

        # Add label
        if serialisation_config.include_label:
            g.add((individual_uri, RDFS.label, Literal(individual_label)))

        # Add facts
        for prop, values in types_and_facts.items():
            if prop == "Types":
                continue

            prop_prefix, prop_name = prop.split(":")
            prop_uri = Namespace(prefixes[prop_prefix])[prop_name]

            for value in values:
                if prop in object_properties:
                    if prefix and prefix_iri:
                        target_uri = Namespace(prefix_iri)[value]
                    else:
                        base_uri = prefix_iri or get_prefix_iri(ontology_iri)
                        target_uri = URIRef(f"{base_uri}{value}")
                    g.add((individual_uri, prop_uri, target_uri))
                elif prop in datatype_properties:
                    # Simplified type inference
                    if isinstance(value, int) or value.isnumeric():
                        literal_value = Literal(value, datatype=XSD.integer)
                    elif isinstance(value, float):
                        literal_value = Literal(value, datatype=XSD.float)
                    else:
                        try:
                            datetime.strptime(value, "%Y-%m-%d")
                            literal_value = Literal(value, datatype=XSD.date)
                        except (ValueError, TypeError):
                            literal_value = Literal(value)
                    g.add((individual_uri, prop_uri, literal_value))
                else:
                    # Default to treating as a literal for safety
                    g.add((individual_uri, prop_uri, Literal(value)))

    return g


def _parse_space_substitute(metacharacter_substitutes: list[str]) -> str | None:
    has_remove = False
    has_url = False
    for substitution_definition in metacharacter_substitutes:
        if substitution_definition == "remove":
            has_remove = True
            if not has_url:
                continue
        if substitution_definition == "url":
            has_url = True
            if not has_remove:
                continue
        if substitution_definition[0] != " ":
            if not has_url:
                continue
        if substitution_definition[1] != "=":
            raise _MetacharacterSubstituteParseException(
                "The second character of a string other than 'remove' or 'url' "
                "passed into the -m/--metadata-substitute option must be '='. This is "
                f"not the case for: {substitution_definition}"
            )
        return substitution_definition.split("=")[1]
    if has_remove:
        return ""
    elif has_url:
        return "%20"
    return None


def _parse_metacharacter_substitutes(
    metacharacter_substitutes: list[str],
) -> Generator[tuple[Metacharacter, Replacement], None, None]:
    has_remove = False
    has_url = False
    handled = []
    for substitution_definition in metacharacter_substitutes:
        if substitution_definition[0] == " ":
            continue
        if substitution_definition == "remove":
            has_remove = True
            if not has_url:
                continue
        if substitution_definition == "url":
            has_url = True
            if not has_remove:
                continue
        if substitution_definition[0] not in OWL_METACHARACTERS:
            metacharacters = ", ".join(
                f"'{character}'" for character in OWL_METACHARACTERS
            )
            raise _MetacharacterSubstituteParseException(
                "The first character of a string other than 'remove' or 'url' "
                "passed into the -m/--metadata-substitute option must be an OWL "
                f"metacharacter, namely one of the following: {metacharacters}"
                f". This is not the case for: {substitution_definition}"
            )
        if substitution_definition[1] != "=":
            raise _MetacharacterSubstituteParseException(
                "The second character of a string other than 'remove' passed "
                "into the -m/--metadata-substitute option must be '='. This is "
                f"not the case for: {substitution_definition}"
            )
        metacharacter, replacement = substitution_definition.split("=", 1)
        handled.append(metacharacter)
        yield metacharacter, replacement
    for metacharacter in OWL_METACHARACTERS:
        if metacharacter not in handled:
            if has_url:
                yield metacharacter, urllib.parse.quote(metacharacter, safe="")
            else:
                yield metacharacter, ""
    if not has_remove:
        return


def _parse_capitalisation_scheme(capitalisation_scheme: str) -> None:
    if capitalisation_scheme not in ["upper-camel", "lower-camel", "flat", "none"]:
        raise _InvalidCapitalisationSchemeException(
            "The following was passed into the -c/--capitalisation-scheme "
            f"option, which is not a permitted value: "
            f"{capitalisation_scheme}. See the documentation of the "
            "-c/--capitalisation-scheme option for the permitted values"
        )


def _build_graph_from_raw_xml(
    raw_xml: str, config_args: dict[str, Any]
) -> DrawIOParserGraph:
    metadata_prefixes, base_uri, csv_path, parsed_root = _extract_drawio_metadata(
        raw_xml
    )
    prefixes = get_prefixes()
    prefixes.update(metadata_prefixes)

    working_xml = _strip_metadata_user_object(raw_xml, parsed_root)

    ontology_iri = (
        config_args["ontology_iri"] or get_ontology_iri()
    )  # AICODE-NOTE: override via XML unsupported yet. Never delete this note. Signed off: human
    prefix = (
        config_args["prefix"] or get_prefix()
    )  # AICODE-NOTE: override via XML unsupported yet. Never delete this note. Signed off: human
    prefix_iri = config_args["prefix_iri"] or base_uri or get_prefix_iri(ontology_iri)

    serialisation_config = SerialisationConfig(
        infer_type_of_literals=config_args["infer_type_of_literals"],
        include_preamble=config_args["include_preamble"],
        ontology_iri=ontology_iri,
        prefix=prefix,
        prefix_iri=prefix_iri,
        indentation=config_args["indentation"],
        include_label=config_args["include_label"],
    )

    space_substitute = _parse_space_substitute(config_args["metacharacter_substitute"])
    metacharacter_substitutes = list(
        _parse_metacharacter_substitutes(config_args["metacharacter_substitute"])
    )

    _parse_capitalisation_scheme(config_args["capitalisation_scheme"])

    draw_io_xml_tree = DrawIOXMLTree(working_xml, prefixes)
    blocks, object_properties, datatype_properties = individual_blocks(
        draw_io_xml_tree.individuals_and_arrows(
            config_args["strict_mode"], config_args["max_gap"]
        ),
        metacharacter_substitutes,
        space_substitute,
        config_args["capitalisation_scheme"],
        prefixes,
    )

    graph = serialise_to_graph(
        blocks,
        object_properties,
        datatype_properties,
        serialisation_config,
        prefixes,
        graph_cls=DrawIOParserGraph,
        graph_kwargs={"csv_path": csv_path},
    )

    if base_uri:
        graph.namespace_manager.bind("", Namespace(base_uri), replace=True)
    # ===== This was causing a very bad bug =====
    # AICODE-NOTE: Never touch this commented out section. Signed off: human.
    # The bug was that @base was misinterpreted at Turtle parsing later on,
    # leading to corrupted relative IRIs.
    # =====
    #   graph.base = base_uri
    # =====

    return graph


def parse_drawio_to_graph(drawio_file_path: str, **kwargs) -> DrawIOParserGraph:
    """
    Parses a draw.io file and returns a DrawIOParserGraph with metadata.
    """
    with open(drawio_file_path, "r", encoding="utf-8") as f:
        raw_xml = f.read()

    # Default settings, can be overridden by kwargs
    config_args = {
        "infer_type_of_literals": True,
        "include_preamble": True,
        "ontology_iri": None,
        "prefix": None,
        "prefix_iri": None,
        "indentation": DEFAULT_INDENTATION,
        "include_label": True,
        "max_gap": DEFAULT_MAX_GAP,
        "strict_mode": False,
        "metacharacter_substitute": [],
        "capitalisation_scheme": DEFAULT_CAPITALISATION_SCHEME,
    }
    config_args.update(kwargs)
    return _build_graph_from_raw_xml(raw_xml, config_args)


def _arguments_parser():
    argument_parser = argparse.ArgumentParser(
        description=(
            "Constructs individuals in OWL with respect to the ontology "
            "Records in Contexts from a draw.io graph. The underlying XML of "
            "the graph should be sent into the script via stdin."
        )
    )
    argument_parser.add_argument(
        "-d",
        "--preamble-disable",
        action="store_true",
        help=(
            "Disable inclusion of a preamble (defining prefix and ontology "
            "IRIs and imports)"
        ),
    )
    argument_parser.add_argument(
        "-g",
        "--max-gap",
        type=float,
        default=DEFAULT_MAX_GAP,
        help=(
            "only taken into account if the '-s/--strict-mode' flag is not "
            "used. In this case, when parsing an arrow whose source or target "
            "is not locked to a node, the geometry of the graph will be taken "
            "into consideration, and a node regarded as the source or target "
            "respectively if the gap (in pixels) between the node and the "
            "start or target of the arrow is less than the max gap defined "
            "here. Can be an integer or a decimal. If not specified, a default "
            f"value of {DEFAULT_MAX_GAP} will be used"
        ),
    )
    argument_parser.add_argument(
        "-i",
        "--infer-types-disable",
        action="store_true",
        help="disable attempted inference of the type of literals",
    )
    argument_parser.add_argument(
        "-n",
        "--indentation",
        type=int,
        default=DEFAULT_INDENTATION,
        help=(
            "the number of spaces to indent by in the outputted OWL syntax. "
            f"If not specified, a default value of {DEFAULT_INDENTATION} will "
            "be used"
        ),
    )
    argument_parser.add_argument(
        "-o",
        "--ontology-iri",
        type=str,
        default=get_ontology_iri(),
        help=(
            "an IRI to use to define the ontology. By default an IRI, a priori "
            "non-dereferenceable, will be generated, and will include a "
            "current timestamp"
        ),
    )
    argument_parser.add_argument(
        "-p",
        "--prefix-iri",
        type=str,
        default=get_prefix_iri(),
        help=(
            "an IRI to use with the prefix used for generated individuals, or "
            "the default one if none is specified using the '-x/--prefix' "
            "flag. By default, the ontology IRI will be used with the symbol "
            "'#' appended"
        ),
    )
    argument_parser.add_argument(
        "-s",
        "--strict-mode",
        action="store_true",
        help=(
            "parse arrows in 'strict mode': both the source and the target "
            "must be locked to a node, and no attempt will made to guess them "
            "from the graph geometry if they are not present"
        ),
    )
    argument_parser.add_argument(
        "-x",
        "--prefix",
        type=str,
        default=get_prefix(),
        help=(
            "a prefix to use with all generated individuals when defining "
            "their IRIs. By default no prefix is used"
        ),
    )
    metacharacters = ", ".join(f"'{character}'" for character in OWL_METACHARACTERS)
    argument_parser.add_argument(
        "-m",
        "--metacharacter-substitute",
        type=str,
        nargs="*",
        default=[],
        action="extend",
        help=(
            "defines a substitute for an OWL metacharacter, namely for a space "
            f"character ' ' or one of the following: {metacharacters}. This "
            "option can be used multiple times, for each metacharacter one "
            "wishes to handle. The string passed into the option must "
            "be 'remove' or 'url'; otherwise., the syntax 'c=d' must be used, "
            "where c is the metacharacter and d is its substitute, which can "
            "consist of zero, one, or more characters. The case of zero characters, "
            "that is to say when the syntax reads 'c=', has the effect of simply "
            "removing any occurrence of c. In several cases it will be "
            "necessary to include the quotation marks in the syntax, and "
            "indeed doing so in all cases will not harm. In the special case "
            "of the metacharacter ' ', that is to say a space, any consecutive "
            "chain of spaces will be treated as one, i.e. the entire chain "
            "will be replaced by the character/string d or removed. If the "
            "special string 'remove' is used, all metacharacters will simply "
            "be removed except for those for which a replacement has been "
            "defined by means of a separate use of the "
            "-m/--metacharacter-substitute option. "
            "If the special string 'url' is used, all metacharacters will simply "
            "be replaced with corresponding URL entities except for those "
            "for which a replacement has been defined by means of a separate use "
            "of the -m/--metacharacter-substitute option."
        ),
    )
    argument_parser.add_argument(
        "-l",
        "--label-disable",
        action="store_true",
        help=(
            "disable the inclusion in the outputted OWL individual blocks of "
            "an rdfs:label annotation property recording the original text "
            "in a node of the graph from which the IRI of the individual is "
            "constructed (if spaces and other metacharacters are present in "
            "the original text, these will need to be handled by means of the "
            "-m/--metacharacter-substitute and -c/--capitalisation-scheme "
            "options"
        ),
    )
    argument_parser.add_argument(
        "-c",
        "--capitalisation-scheme",
        type=str,
        default=DEFAULT_CAPITALISATION_SCHEME,
        help=(
            "spaces are not permitted in OWL individual IRIs, and thus a "
            "choice of how to separate multiple words is needed. The "
            "-m/--metacharacter-substitute option allows for specification "
            "of which character or string to replace spaces by, or whether "
            "to simply remove spaces. The option documented here allows in "
            "addition for adjusting the capitalisation of the words now "
            "combined by the replacing of/removal of spaces. The option "
            "accepts one of the following strings: 'upper-camel', "
            "'lower-camel', 'flat', 'none', of which the default is "
            "'upper-camel'. Here 'upper-camel' capitalises the first letter "
            "of every word; 'lower-camel' capitalises the first letter of "
            "every word except the first, which is made lower-case; 'flat' "
            "makes every word lower-case; and 'none' leaves the words "
            "untouched"
        ),
    )
    argument_parser.add_argument(
        "file",
        nargs="?",
        type=argparse.FileType("r"),
        default=None,
        help="A draw.io file to parse. If not provided, reads from stdin.",
    )
    return argument_parser


def _run(args=None) -> None:
    parser = _arguments_parser()
    arguments = parser.parse_args(args)

    capitalisation_scheme = arguments.capitalisation_scheme

    config_args = {
        "infer_type_of_literals": not arguments.infer_types_disable,
        "include_preamble": not arguments.preamble_disable,
        "ontology_iri": arguments.ontology_iri,
        "prefix": arguments.prefix,
        "prefix_iri": arguments.prefix_iri,
        "indentation": arguments.indentation,
        "include_label": not arguments.label_disable,
        "max_gap": arguments.max_gap,
        "strict_mode": arguments.strict_mode,
        "metacharacter_substitute": arguments.metacharacter_substitute,
        "capitalisation_scheme": capitalisation_scheme,
    }

    if arguments.file:
        raw_xml = arguments.file.read()
    else:
        raw_xml = stdin.read()

    try:
        graph = _build_graph_from_raw_xml(raw_xml, config_args)
    except NothingToParseException:
        sys_exit("The draw IO XML graph passed in appears to be empty")
    except (
        _MetacharacterSubstituteParseException,
        _InvalidCapitalisationSchemeException,
    ) as exception:
        sys_exit(f"{exception}")
    except NoSourceException as exception:
        if arguments.strict_mode:
            message = (
                f"{exception}. If so, try to lock the arrow to an individual "
                "node in the original graph; or the underlying XML could be "
                "edited to indicate the source. Alternatively, try running the "
                "parser in non-strict mode (without the '-s/--strict-mode' "
                "flag), optionally making use of the '-g/--max-gap' option"
            )
        else:
            message = (
                f"{exception}. If so, consider using the '-g/--max gap' option "
                "when running the script to increase the max recognised gap "
                "between a node and an arrow end; or try to lock the arrow to "
                "an individual node in the original graph; or the underlying "
                "XML could be edited"
            )
        sys_exit(message)
    except (
        NotInKnownException,
        ArrowWithoutIndividualAsSourceException,
        MetacharacterException,
    ) as exception:
        sys_exit(f"{exception}")

    print(graph.serialize(format="turtle"))


def main(args=None) -> None:
    try:
        _run(args)
    except ParseException as exception:
        sys_exit(str(exception))
    except Exception as exception:  # pylint: disable=broad-exception-caught
        error_type = type(exception).__name__
        error_traceback = traceback.format_exc()
        sys_exit(
            f"An unexpected error occurred: {error_type}: {exception}\n\nTraceback:\n{error_traceback}"
        )


if __name__ == "__main__":
    main()

```

</details>

**Attachment:** 
*ID:* `0d072643-0b48-4914-a8c3-923645087d69`

<details>

```
# drawio_meta_builder.py
# Generate a new source file drawio_meta.py by reorganizing real code bodies
# from draw_io_parser across three axes (data_type, data_role, phase).

from __future__ import annotations
import importlib
import importlib.util
import inspect
import os
import sys
import ast
from typing import List, Tuple
import argparse


# ---- Load legacy module ----
def load_legacy():
    try:
        return importlib.import_module("legacy.legacy.draw_io_parser")
    except ModuleNotFoundError:
        here = os.path.dirname(__file__)
        for name in ["draw_io_parser.py"]:
            path = os.path.join(here, name)
            if os.path.exists(path):
                spec = importlib.util.spec_from_file_location("draw_io_parser", path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["draw_io_parser"] = mod
                spec.loader.exec_module(mod)  # type: ignore
                return mod
        raise RuntimeError("draw_io_parser source not found")


draw = load_legacy()

# ---- Explicit mapping ----
MAPPING: List[Tuple[str, str, str, str]] = [
    # constants / defaults
    ("DEFAULT_CAPITALISATION_SCHEME", "internal", "metadata", "pre"),
    ("DEFAULT_INDENTATION", "internal", "metadata", "pre"),
    ("DEFAULT_MAX_GAP", "internal", "metadata", "pre"),
    ("OWL_METACHARACTERS", "internal", "metadata", "pre"),
    # type aliases
    ("Blocks", "internal", "metadata", "pre"),
    ("CellID", "internal", "metadata", "pre"),
    ("XCoordinate", "internal", "metadata", "pre"),
    ("YCoordinate", "internal", "metadata", "pre"),
    ("Width", "internal", "metadata", "pre"),
    ("Height", "internal", "metadata", "pre"),
    ("ArrowStart", "internal", "metadata", "pre"),
    ("ArrowEnd", "internal", "metadata", "pre"),
    ("Label", "internal", "metadata", "pre"),
    ("ArrowData", "internal", "metadata", "pre"),
    ("Dimensions", "internal", "metadata", "pre"),
    ("Paragraph", "internal", "metadata", "pre"),
    ("Metacharacter", "internal", "metadata", "pre"),
    ("Replacement", "internal", "metadata", "pre"),
    # exceptions
    ("NothingToParseException", "xml", "data", "core"),
    ("NotInKnownException", "rdf", "data", "core"),
    ("_NoCellCloseEnoughException", "xml", "data", "core"),
    ("NoSourceException", "xml", "data", "core"),
    ("NoTargetException", "xml", "data", "core"),
    ("_NoValueException", "xml", "data", "core"),
    ("_SourceNotIndividualException", "internal", "data", "core"),
    ("ArrowWithoutIndividualAsSourceException", "internal", "data", "core"),
    ("_MetacharacterSubstituteParseException", "rdf", "data", "pre"),
    ("MetacharacterException", "rdf", "data", "pre"),
    ("_InvalidCapitalisationSchemeException", "rdf", "control", "pre"),
    ("ParseException", "xml", "data", "core"),
    # metadata getters
    ("get_prefixes", "internal", "metadata", "pre"),
    ("get_ontology_iri", "internal", "metadata", "pre"),
    ("get_prefix", "internal", "metadata", "pre"),
    ("get_prefix_iri", "internal", "metadata", "pre"),
    # xml + curie helpers
    ("_extract_drawio_metadata", "xml", "metadata", "pre"),
    ("_strip_metadata_user_object", "xml", "metadata", "pre"),
    ("_split_curie", "internal", "data", "core"),
    ("_ensure_known_curie", "internal", "data", "core"),
    ("_verify_is_ric_class", "internal", "data", "core"),
    # internal model
    ("Individual", "internal", "data", "core"),
    ("Arrow", "internal", "data", "core"),
    # html/xml text parser
    ("NodeHTMLParser", "xml", "data", "pre"),
    # rdf config
    ("SerialisationConfig", "internal", "metadata", "pre"),
    # xml tree + all key methods
    ("DrawIOXMLTree", "xml", "data", "core"),
    ("DrawIOXMLTree._geometry", "xml", "data", "core"),
    ("DrawIOXMLTree._x_and_y_in_geometry", "xml", "data", "core"),
    ("DrawIOXMLTree._has_correct_as_attribute", "xml", "data", "core"),
    ("DrawIOXMLTree._is_locked", "xml", "data", "core"),
    ("DrawIOXMLTree._dimensions", "xml", "data", "core"),
    ("DrawIOXMLTree._close_enough", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_with_id", "xml", "data", "core"),
    ("DrawIOXMLTree._value_of", "xml", "data", "core"),
    ("DrawIOXMLTree._parent_of", "xml", "data", "core"),
    ("DrawIOXMLTree._child_of", "xml", "data", "core"),
    ("DrawIOXMLTree._start_or_end", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_start", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_end", "xml", "data", "core"),
    ("DrawIOXMLTree._is_possible_literal", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_label", "xml", "data", "core"),
    ("DrawIOXMLTree._add_arrow_if_find_label", "xml", "data", "core"),
    (
        "DrawIOXMLTree._extract_individual_and_arrow_and_literal_cells",
        "xml",
        "data",
        "core",
    ),
    ("DrawIOXMLTree._cell_close_to", "xml", "data", "core"),
    ("DrawIOXMLTree._defines_individual", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_is_literal", "xml", "data", "core"),
    ("DrawIOXMLTree._source_or_target", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow", "xml", "data", "core"),
    ("DrawIOXMLTree.individuals_and_arrows", "internal", "data", "post"),
    # model processing
    ("_handle_spaces", "rdf", "data", "pre"),
    ("_replace_metacharacter", "rdf", "data", "pre"),
    ("_replace_metacharacters", "rdf", "data", "pre"),
    ("_add_individual_type", "internal", "data", "core"),
    ("individual_blocks", "internal", "data", "post"),
    # rdf graph
    ("DrawIOParserGraph", "rdf", "control", "core"),
    ("serialise_to_graph", "rdf", "control", "post"),
    # cli / sdk
    ("_parse_space_substitute", "internal", "data", "core"),
    ("_parse_metacharacter_substitutes", "internal", "data", "core"),
    ("_parse_capitalisation_scheme", "rdf", "control", "pre"),
    ("_build_graph_from_raw_xml", "internal", "control", "core"),
    ("parse_drawio_to_graph", "internal", "control", "post"),
    ("_arguments_parser", "internal", "control", "pre"),
    ("_run", "internal", "control", "post"),
    ("main", "internal", "control", "post"),
]


# ---- Helpers ----
def resolve(dotted: str):
    cur = draw
    for part in dotted.split("."):
        cur = getattr(cur, part)
    return cur


def safe_source(obj) -> str:
    import textwrap

    try:
        src = inspect.getsource(obj)
        return textwrap.dedent(src)
    except Exception:
        return f"# source unavailable for {getattr(obj, '__name__', repr(obj))}\n"


def indent(text: str, n: int = 8) -> str:
    pad = " " * n
    return "\n".join(pad + line if line.strip() else "" for line in text.splitlines())


def legacy_imports():
    src = inspect.getsource(draw)
    imps = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("import ") or (
            s.startswith("from ") and not s.startswith("from __future__")
        ):
            imps.append(line)
    seen = set()
    ordered = []
    for imp in imps:
        if imp not in seen:
            seen.add(imp)
            ordered.append(imp)
    return ("\n".join(ordered) + "\n") if ordered else ""


def get_source_or_repr(name: str, obj) -> str:
    import inspect
    import textwrap

    try:
        if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
            return textwrap.dedent(inspect.getsource(obj))
    except Exception:
        pass
    # fallback for constants, aliases, etc.
    if isinstance(obj, type) or isinstance(obj, type(str)) or callable(obj):
        return f"{name} = {getattr(obj, '__name__', repr(obj))}\n"
    return f"{name} = {repr(obj)}\n"

def strip_static_methods(src: str, class_name: str, methods: set[str]) -> str:
    tree = ast.parse(src)

    class _Strip(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            if node.name != class_name:
                return node
            node.body = [
                n
                for n in node.body
                if not (
                    isinstance(n, ast.FunctionDef)
                    and n.name in methods
                    and any(
                        (isinstance(d, ast.Name) and d.id == "staticmethod")
                        or (isinstance(d, ast.Attribute) and d.attr == "staticmethod")
                        for d in getattr(n, "decorator_list", [])
                    )
                )
            ]
            return node

    new_tree = _Strip().visit(tree)
    try:
        return ast.unparse(new_tree)
    except Exception:
        return src

# ---- Code generator ----
def build_output() -> str:
    header = [
        "# AUTO-GENERATED FILE — DO NOT EDIT",
        "# Generated by drawio_meta_builder.py",
        "from __future__ import annotations",
        "",
    ]

    mod_src = inspect.getsource(draw)
    tree = ast.parse(mod_src)
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if (
                isinstance(node, ast.ImportFrom)
                and getattr(node, "module", "") == "__future__"
            ):
                continue
            if isinstance(node, ast.Import):
                names = [
                    n.name + (f" as {n.asname}" if n.asname else "") for n in node.names
                ]
                import_lines.append("import " + ", ".join(names))
            else:
                module = ("." * node.level) + (node.module or "")
                names = [
                    n.name + (f" as {n.asname}" if n.asname else "") for n in node.names
                ]
                import_lines.append(f"from {module} import " + ", ".join(names))
    seen = set()
    ordered = []
    for line in import_lines:
        if line not in seen:
            seen.add(line)
            ordered.append(line)
    out = ["\n".join(header) + ("\n" + "\n".join(ordered) + "\n" if ordered else "\n")]

    # Predeclare namespaces
    out.append(
        "class pre:\n"
        "    class xml:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class internal:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class rdf:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
    )
    out.append(
        "class core:\n"
        "    class xml:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class internal:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class rdf:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
    )
    out.append(
        "class post:\n"
        "    class xml:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class internal:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class rdf:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
    )

    grouped = {}
    for dotted, dt, dr, ph in MAPPING:
        grouped.setdefault((dt, dr, ph), []).append(dotted)

    for ph in ["pre", "core", "post"]:
        for dt in ["xml", "internal", "rdf"]:
            for dr in ["metadata", "data", "control"]:
                names = grouped.get((dt, dr, ph), [])
                out.append(f"\n# ===== {ph}.{dt}.{dr} =====\n")
                out.append(f"class {dt}_{dr}_{ph}:")
                if names:
                    for name in names:
                        obj = resolve(name)
                        src = get_source_or_repr(name, obj)
                        if inspect.isclass(obj):
                            clsname = name.split(".")[-1]
                            to_strip = {
                                m.split(".")[-1]
                                for (m, _, _, _) in MAPPING
                                if m.startswith(f"{clsname}.")
                                and isinstance(
                                    getattr(obj, "__dict__", {}).get(
                                        m.split(".")[-1], None
                                    ),
                                    staticmethod,
                                )
                            }
                            if to_strip:
                                src = strip_static_methods(src, clsname, to_strip)
                        block = indent(f"# BEGIN {name}\n{src}\n# END {name}\n", 4)
                        out.append(block)
                else:
                    out.append(indent("pass", 4))
                out.append("")

    orchestrator = """
# ===== orchestrator =====
class DrawIOParser:
    __data_type__ = "internal"
    __data_role__ = "metadata"
    __phase__ = "core"
    def __init__(self):
        self.pre = pre
        self.core = core
        self.post = post
    def to_graph_from_file(self, path, **kw):
        return post.internal.control.parse_drawio_to_graph(path, **kw)
    def run_cli(self, argv=None):
        return post.internal.control.main(argv)
"""
    out.append(orchestrator)
    src = "\n".join(out)

    # ---- Add module-level aliases for mapped symbols ----
    alias_lines = ["", "# ===== module-level aliases ====="]
    added = set()
    for dotted, dt, dr, ph in MAPPING:
        base = dotted.split(".")[-1]
        alias = f"{base} = {dt}_{dr}_{ph}.{base}"
        if base not in added:
            alias_lines.append(alias)
            added.add(base)

    alias_lines.append("")
    alias_lines.append("# ===== attach to nested namespaces =====")
    for dotted, dt, dr, ph in MAPPING:
        base = dotted.split(".")[-1]
        alias_lines.append(f"setattr({ph}.{dt}.{dr}, '{base}', {dt}_{dr}_{ph}.{base})")

    # dynamically attach any extracted static methods back onto their parent classes
    for dotted, dt, dr, ph in MAPPING:
        if "." not in dotted:
            continue
        cls_name, method_name = dotted.rsplit(".", 1)
        try:
            legacy_cls = getattr(draw, cls_name, None)
            if legacy_cls is None:
                # fallback: if class is nested, walk dotted path
                parts = cls_name.split(".")
                legacy_cls = draw
                for part in parts:
                    legacy_cls = getattr(legacy_cls, part)
            if isinstance(
                getattr(legacy_cls, "__dict__", {}).get(method_name, None), staticmethod
            ):
                alias_lines.append(
                    f"setattr({cls_name}, '{method_name}', staticmethod({method_name}))"
                )
        except Exception:
            continue

    src += "\n" + "\n".join(alias_lines) + "\n"

    return src


def write_output(path: str = "drawio_meta.py"):
    src = build_output()
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Generate drawio_meta.py from legacy draw_io_parser sources."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="drawio_meta.py",
        help="Path to the generated file (default: drawio_meta.py)",
    )
    args = parser.parse_args()

    write_output(args.output)


if __name__ == "__main__":
    main()

```

</details>

__________

## 1 - Claude
*Branch:* Main
*UUID:* `a0d56012-3949-481b-94ec-53dbc06228a8`
*Created:* 10/16/2025, 9:34:51 AM

 I'll analyze this complex data pipeline architecture and provide a comprehensive summary, visualizations, and an updated MAPPING.

## Summary

You have a sophisticated three-axis classification system for organizing the Draw.io to RDF conversion pipeline:

### The Three Axes

1. **Data Type** (what domain the code operates in):
   - `xml`: Direct XML manipulation and parsing
   - `internal`: Internal data models (Individual/Arrow) and business logic
   - `rdf`: RDF/OWL graph construction and serialization

2. **Data Role** (what kind of concern):
   - `metadata`: Configuration, prefixes, IRIs, settings
   - `data`: Core entities and their transformations
   - `control`: Orchestration, flow control, scaffolding

3. **Phase** (when in the pipeline):
   - `pre`: Before Individual/Arrow generation
   - `core`: Individual/Arrow generation and processing
   - `post`: After blocks/props are ready, final graph construction

### Pipeline Flow

**Pre-Processing Phase:**
- **xml.metadata.pre**: Extract metadata from XML (prefixes, base URI, csv_path via `_extract_drawio_metadata`), strip metadata node
- **xml.control.pre**: None (etree handles parsing)
- **internal.metadata.pre**: Constants, defaults, type aliases, get functions for ontology IRI/prefix
- **internal.control.pre**: Argument parsing, user input collection
- **rdf.metadata.pre**: None yet (could be future: importing existing prefixes)
- **rdf.data.pre**: String manipulation rules (metacharacter handling, capitalization schemes)
- **rdf.control.pre**: Validation of capitalization schemes

**Core Processing Phase:**
- **xml.data.core**: ALL logic from stripped XML → Individual/Arrow instances (DrawIOXMLTree class with all geometry, cell identification, arrow parsing)
- **xml.metadata.core**: None (already extracted)
- **xml.control.core**: None (XML no longer exists as input)
- **internal.data.core**: Processing Individual/Arrow instances with metadata (individual_blocks function, CURIE handling, type additions)
- **internal.metadata.core**: None (no new metadata created)
- **internal.control.core**: Coupling individuals/arrows with metadata, producing blocks/props tuple; also `_build_graph_from_raw_xml` orchestration
- **rdf.data.core**: None (RDF doesn't exist yet)
- **rdf.metadata.core**: None
- **rdf.control.core**: Graph construction infrastructure (DrawIOParserGraph class, serialise_to_graph preparation - though tightly coupled with actual serialization)

**Post-Processing Phase:**
- **xml.*post**: None (XML processing complete)
- **internal.data.post**: The `individuals_and_arrows` generator method (bridge from XML processing to internal model)
- **internal.control.post**: SDK wrapper (`parse_drawio_to_graph`), CLI wrapper (`_run`, `main`), blocks assembly (`individual_blocks`)
- **rdf.control.post**: `serialise_to_graph` execution, secondary serializations, DrawIOParserGraph manipulation

### Key Insights

1. **Tech Debt**: `_build_graph_from_raw_xml` exists as scaffolding because metadata extraction was added later; ideally all metadata would flow uniformly
2. **Tight Coupling**: `serialise_to_graph` mixes config preparation with serialization
3. **Asymmetry**: XML metadata is partially separated (csv_path) vs integrated (prefixes), while external metadata (argparse) doesn't loop back into XML
4. **Clear Separation**: Pre-phase is XML+metadata gathering; core is Individual/Arrow generation and coupling with metadata; post is RDF graph finalization

**Artifact Created:** Draw.io to RDF Pipeline Flow
*ID:* `drawio_pipeline_flow`
*Command:* `create`
*Version:* 1
*Branch:* branch1 (main) (6ae7dc60...)
*Created:* 10/16/2025, 9:33:45 AM
*Change:* Created

Now let me create an RDF representation of this 3D structure:

**Artifact Created:** Pipeline Architecture Ontology (RDF Turtle)
*ID:* `pipeline_ontology`
*Command:* `create`
*Version:* 1
*Branch:* branch1 (main) (6ae7dc60...)
*Created:* 10/16/2025, 9:34:15 AM
*Change:* Created

Now, the **updated MAPPING list**. Based on my analysis, here are the corrections:

**Artifact Created:** Updated MAPPING List
*ID:* `updated_mapping`
*Command:* `create`
*Version:* 1
*Branch:* branch1 (main) (6ae7dc60...)
*Created:* 10/16/2025, 9:34:41 AM
*Change:* Created

## Key Changes Made to MAPPING:

1. **Moved all exceptions to their proper domains:**
   - `NothingToParseException`, `NoSourceException`, `NoTargetException`, `_NoValueException`, `_NoCellCloseEnoughException`, `ParseException` → `xml.data.core` (XML parsing errors)
   - `NotInKnownException`, `_MetacharacterSubstituteParseException`, `MetacharacterException`, `_InvalidCapitalisationSchemeException` → `rdf.data.core` (RDF compliance errors)
   - `_SourceNotIndividualException`, `ArrowWithoutIndividualAsSourceException` → `internal.data.core` (internal model validation errors)

2. **Reorganized metadata vs control:**
   - `_parse_space_substitute`, `_parse_metacharacter_substitutes` → `internal.control.core` (they orchestrate metadata parsing, not just data)
   - `_parse_capitalisation_scheme` → `rdf.control.pre` (validates RDF-related configuration)

3. **Clarified phase assignments:**
   - `individuals_and_arrows` → `internal.data.post` (it's the generator that bridges from core XML processing to post-phase assembly)
   - `individual_blocks` → `internal.control.post` (assembles blocks in post-phase, not core)

4. **Moved RDF-specific validations:**
   - Exceptions related to RDF compliance (CURIE validation, metacharacter issues) are now properly in `rdf.data.core`

The structure now cleanly separates: XML domain (parsing), internal domain (business logic), and RDF domain (graph construction) across the three phases with proper concern separation (metadata/data/control).

__________

## 2 - Human
*Branch:* Main
*UUID:* `a885f26a-5b78-4d51-9f2e-b8d916037d5c`
*Created:* 10/16/2025, 9:38:02 AM

also ONLY give lines i need to change/add in metabuilder to make pre, post, core nested within pipeline

__________

## 3 - Claude
*Branch:* Main
*UUID:* `3867cfdc-a388-4cd2-acfd-7159413224e3`
*Created:* 10/16/2025, 9:38:20 AM

 Here are the ONLY lines to change/add in the metabuilder:

**Replace this section (around lines 187-199):**
```python
    # Predeclare namespaces
    out.append(
        "class pre:\n"
        "    class xml:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class internal:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class rdf:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
    )
    out.append(
        "class core:\n"
        "    class xml:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class internal:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class rdf:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
    )
    out.append(
        "class post:\n"
        "    class xml:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class internal:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
        "    class rdf:\n        class metadata: pass\n        class data: pass\n        class control: pass\n"
    )
```

**With this:**
```python
    # Predeclare namespaces nested within pipeline
    out.append(
        "class pipeline:\n"
        "    class pre:\n"
        "        class xml:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "        class internal:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "        class rdf:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "    class core:\n"
        "        class xml:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "        class internal:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "        class rdf:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "    class post:\n"
        "        class xml:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "        class internal:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
        "        class rdf:\n            class metadata: pass\n            class data: pass\n            class control: pass\n"
    )
```

**Update the orchestrator section (around lines 228-238):**
```python
# ===== orchestrator =====
class DrawIOParser:
    __data_type__ = "internal"
    __data_role__ = "metadata"
    __phase__ = "core"
    def __init__(self):
        self.pre = pre
        self.core = core
        self.post = post
    def to_graph_from_file(self, path, **kw):
        return post.internal.control.parse_drawio_to_graph(path, **kw)
    def run_cli(self, argv=None):
        return post.internal.control.main(argv)
```

**To:**
```python
# ===== orchestrator =====
class DrawIOParser:
    __data_type__ = "internal"
    __data_role__ = "metadata"
    __phase__ = "core"
    def __init__(self):
        self.pipeline = pipeline
    def to_graph_from_file(self, path, **kw):
        return pipeline.post.internal.control.parse_drawio_to_graph(path, **kw)
    def run_cli(self, argv=None):
        return pipeline.post.internal.control.main(argv)
```

**Update the attach to nested namespaces section (around line 252):**
```python
alias_lines.append("# ===== attach to nested namespaces =====")
for dotted, dt, dr, ph in MAPPING:
    base = dotted.split(".")[-1]
    alias_lines.append(f"setattr({ph}.{dt}.{dr}, '{base}', {dt}_{dr}_{ph}.{base})")
```

**To:**
```python
alias_lines.append("# ===== attach to nested namespaces =====")
for dotted, dt, dr, ph in MAPPING:
    base = dotted.split(".")[-1]
    alias_lines.append(f"setattr(pipeline.{ph}.{dt}.{dr}, '{base}', {dt}_{dr}_{ph}.{base})")
```

That's it! These 3 changes will nest everything under `pipeline`.

__________

## 4 - Human
*Branch:* Main
*UUID:* `61f794fb-e085-4037-a7e8-e9e60b9edd25`
*Created:* 10/16/2025, 9:54:31 AM

why do you call serialise_to_graph from a core class? this is why i said serialise still belongs in core. whereas individuals_and_arrows obviously below in xml data core because they have to do with individual_cells for example which is  drawioxmltree property. individual_blocks also belongs in core because it produces stuff to feed into serialise which is a core class; these concerns are already separated by belonging to rdf and internal so it's fine to keep them both in core.

Please diligently revise all artifacts.

__________

## 5 - Claude
*Branch:* Main
*UUID:* `6ae7dc60-0517-4ef2-ad50-bc94499c7fcd`
*Created:* 10/16/2025, 9:56:03 AM

 You're absolutely right! I misunderstood the architecture. Let me correct this:

- `serialise_to_graph` is called FROM `_build_graph_from_raw_xml` which is in core, so it belongs in **core**
- `individuals_and_arrows` is a method of `DrawIOXMLTree`, so it belongs in **xml.data.core**
- `individual_blocks` produces the blocks/props tuple that feeds into `serialise_to_graph`, so it belongs in **core**
- The separation between `rdf.control.core` and `internal.control.core` is sufficient - they don't need to be in different phases

*ID:* `drawio_pipeline_flow`
*Command:* `rewrite`
*Version:* 2
*Branch:* branch1 (main) (6ae7dc60...)
*Created:* 10/16/2025, 9:54:57 AM
*Change:* Rewritten

*ID:* `pipeline_ontology`
*Command:* `rewrite`
*Version:* 2
*Branch:* branch1 (main) (6ae7dc60...)
*Created:* 10/16/2025, 9:55:33 AM
*Change:* Rewritten

*ID:* `updated_mapping`
*Command:* `rewrite`
*Version:* 2
*Branch:* branch1 (main) (6ae7dc60...)
*Created:* 10/16/2025, 9:55:56 AM
*Change:* Rewritten

Perfect! Now the classification is correct:

**Key corrections made:**

1. **`individuals_and_arrows`** → `xml.data.core` (it's a method of DrawIOXMLTree that uses individual_cells property)

2. **`individual_blocks`** → `internal.control.core` (produces blocks/props tuple that feeds into `serialise_to_graph`)

3. **`serialise_to_graph`** → `rdf.control.core` (called FROM `_build_graph_from_raw_xml` which is in core)

4. **Removed** `rdf.control.post` entirely from MAPPING since there are currently no post-phase RDF operations

The pipeline now correctly shows:
- **Pre**: Metadata extraction and preparation
- **Core**: XML → Individual/Arrow → blocks/props → DrawIOParserGraph
- **Post**: SDK and CLI wrappers only

