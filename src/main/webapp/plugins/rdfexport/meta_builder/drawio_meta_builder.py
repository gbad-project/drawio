# drawio_meta_builder.py
# Generate a new source file drawio_meta.py by reorganizing real code bodies
# from draw_io_parser across three axes (data_type, data_role, phase).

from __future__ import annotations
import importlib, importlib.util, inspect, os, sys, ast
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
    ("DEFAULT_CAPITALISATION_SCHEME","internal","metadata","pre"),
    ("DEFAULT_INDENTATION",          "internal","metadata","pre"),
    ("DEFAULT_MAX_GAP",              "internal","metadata","pre"),
    ("OWL_METACHARACTERS",           "internal","metadata","pre"),
    # type aliases
    ("Blocks","internal","metadata","pre"),
    ("CellID","internal","metadata","pre"),
    ("XCoordinate","internal","metadata","pre"),
    ("YCoordinate","internal","metadata","pre"),
    ("Width","internal","metadata","pre"),
    ("Height","internal","metadata","pre"),
    ("ArrowStart","internal","metadata","pre"),
    ("ArrowEnd","internal","metadata","pre"),
    ("Label","internal","metadata","pre"),
    ("ArrowData","internal","metadata","pre"),
    ("Dimensions","internal","metadata","pre"),
    ("Paragraph","internal","metadata","pre"),
    ("Metacharacter","internal","metadata","pre"),
    ("Replacement","internal","metadata","pre"),
    # exceptions
    ("NothingToParseException","xml","data","core"),
    ("NotInKnownException","internal","metadata","core"),
    ("_NoCellCloseEnoughException","xml","data","core"),
    ("NoSourceException","xml","data","core"),
    ("NoTargetException","xml","data","core"),
    ("_NoValueException","xml","data","core"),
    ("_SourceNotIndividualException","internal","data","core"),
    ("ArrowWithoutIndividualAsSourceException","internal","data","core"),
    ("_MetacharacterSubstituteParseException","internal","metadata","core"),
    ("MetacharacterException","internal","metadata","core"),
    ("_InvalidCapitalisationSchemeException","internal","metadata","core"),
    ("ParseException","xml","data","core"),
    # metadata getters
    ("get_prefixes","internal","metadata","pre"),
    ("get_ontology_iri","internal","metadata","pre"),
    ("get_prefix","internal","metadata","pre"),
    ("get_prefix_iri","internal","metadata","pre"),
    # xml + curie helpers
    ("_extract_drawio_metadata","xml","metadata","pre"),
    ("_strip_metadata_user_object","xml","metadata","pre"),
    ("_split_curie","internal","metadata","core"),
    ("_ensure_known_curie","internal","metadata","core"),
    ("_verify_is_ric_class","internal","metadata","core"),
    # internal model
    ("Individual","internal","data","core"),
    ("Arrow","internal","data","core"),
    # html/xml text parser
    ("NodeHTMLParser","xml","data","pre"),
    # rdf config
    ("SerialisationConfig","rdf","metadata","pre"),
    # xml tree + all key methods
    ("DrawIOXMLTree","xml","data","core"),
    ("DrawIOXMLTree._geometry","xml","data","core"),
    ("DrawIOXMLTree._x_and_y_in_geometry","xml","data","core"),
    ("DrawIOXMLTree._has_correct_as_attribute","xml","metadata","core"),
    ("DrawIOXMLTree._is_locked","xml","metadata","core"),
    ("DrawIOXMLTree._dimensions","xml","data","core"),
    ("DrawIOXMLTree._close_enough","xml","data","core"),
    ("DrawIOXMLTree._cell_with_id","xml","data","core"),
    ("DrawIOXMLTree._value_of","xml","data","core"),
    ("DrawIOXMLTree._parent_of","xml","data","core"),
    ("DrawIOXMLTree._child_of","xml","data","core"),
    ("DrawIOXMLTree._start_or_end","xml","data","core"),
    ("DrawIOXMLTree._arrow_start","xml","data","core"),
    ("DrawIOXMLTree._arrow_end","xml","data","core"),
    ("DrawIOXMLTree._is_possible_literal","xml","data","core"),
    ("DrawIOXMLTree._arrow_label","xml","data","core"),
    ("DrawIOXMLTree._add_arrow_if_find_label","xml","data","core"),
    ("DrawIOXMLTree._extract_individual_and_arrow_and_literal_cells","xml","data","core"),
    ("DrawIOXMLTree._cell_close_to","xml","data","core"),
    ("DrawIOXMLTree._defines_individual","xml","data","core"),
    ("DrawIOXMLTree._cell_is_literal","xml","data","core"),
    ("DrawIOXMLTree._source_or_target","xml","data","core"),
    ("DrawIOXMLTree._arrow","xml","data","core"),
    ("DrawIOXMLTree.individuals_and_arrows","xml","data","core"),
    # model processing
    ("_handle_spaces","internal","metadata","core"),
    ("_replace_metacharacter","internal","metadata","core"),
    ("_replace_metacharacters","internal","metadata","core"),
    ("_add_individual_type","internal","data","core"),
    ("individual_blocks","internal","data","post"),
    # rdf graph
    ("DrawioParserGraph","rdf","data","core"),
    ("serialise_to_graph","rdf","data","post"),
    # cli / sdk
    ("_parse_space_substitute","internal","metadata","pre"),
    ("_parse_metacharacter_substitutes","internal","metadata","pre"),
    ("_parse_capitalisation_scheme","internal","metadata","pre"),
    ("_build_graph_from_raw_xml","internal","data","core"),
    ("parse_drawio_to_graph","internal","data","post"),
    ("_arguments_parser","internal","metadata","pre"),
    ("_run","internal","metadata","post"),
    ("main","internal","metadata","post"),
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
        return f"# source unavailable for {getattr(obj,'__name__',repr(obj))}\n"

def indent(text: str, n: int = 8) -> str:
    pad = " " * n
    return "\n".join(pad + line if line.strip() else "" for line in text.splitlines())

def legacy_imports():
    src = inspect.getsource(draw)
    imps = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("import ") or (s.startswith("from ") and not s.startswith("from __future__")):
            imps.append(line)
    seen = set(); ordered = []
    for l in imps:
        if l not in seen:
            seen.add(l); ordered.append(l)
    return ("\n".join(ordered) + "\n") if ordered else ""

def get_source_or_repr(name: str, obj) -> str:
    import inspect, textwrap
    try:
        if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
            return textwrap.dedent(inspect.getsource(obj))
    except Exception:
        pass
    # fallback for constants, aliases, etc.
    if isinstance(obj, type) or isinstance(obj, type(str)) or callable(obj):
        return f"{name} = {getattr(obj, '__name__', repr(obj))}\n"
    return f"{name} = {repr(obj)}\n"

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
            if isinstance(node, ast.ImportFrom) and getattr(node, "module", "") == "__future__":
                continue
            if isinstance(node, ast.Import):
                names = [n.name + (f" as {n.asname}" if n.asname else "") for n in node.names]
                import_lines.append("import " + ", ".join(names))
            else:
                module = ("." * node.level) + (node.module or "")
                names = [n.name + (f" as {n.asname}" if n.asname else "") for n in node.names]
                import_lines.append(f"from {module} import " + ", ".join(names))
    seen = set(); ordered = []
    for line in import_lines:
        if line not in seen:
            seen.add(line); ordered.append(line)
    out = ["\n".join(header) + ("\n" + "\n".join(ordered) + "\n" if ordered else "\n")]

    # Predeclare namespaces
    out.append("class xml:\n    class data:\n        class pre: pass\n        class core: pass\n        class post: pass\n    class metadata:\n        class pre: pass\n        class core: pass\n        class post: pass\n")
    out.append("class internal:\n    class data:\n        class pre: pass\n        class core: pass\n        class post: pass\n    class metadata:\n        class pre: pass\n        class core: pass\n        class post: pass\n")
    out.append("class rdf:\n    class data:\n        class pre: pass\n        class core: pass\n        class post: pass\n    class metadata:\n        class pre: pass\n        class core: pass\n        class post: pass\n")

    grouped = {}
    for dotted, dt, dr, ph in MAPPING:
        grouped.setdefault((dt, dr, ph), []).append(dotted)

    for (dt, dr, ph), names in grouped.items():
        out.append(f"\n# ===== {dt}.{dr}.{ph} =====\n")
        out.append(f"class {dt}_{dr}_{ph}:")
        for name in names:
            obj = resolve(name)
            src = get_source_or_repr(name, obj)
            block = indent(f"# BEGIN {name}\n{src}\n# END {name}\n", 4)
            out.append(block)
        out.append("")

    orchestrator = """
# ===== orchestrator =====
class DrawioParser:
    __data_type__ = "internal"
    __data_role__ = "metadata"
    __phase__ = "core"
    def __init__(self):
        self.xml = xml
        self.internal = internal
        self.rdf = rdf
    def to_graph_from_file(self, path, **kw):
        return internal_data_post.parse_drawio_to_graph(path, **kw)
    def run_cli(self, argv=None):
        return internal_metadata_post.main(argv)
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
        "-o", "--output",
        default="drawio_meta.py",
        help="Path to the generated file (default: drawio_meta.py)"
    )
    args = parser.parse_args()

    write_output(args.output)

if __name__ == "__main__":
    main()
