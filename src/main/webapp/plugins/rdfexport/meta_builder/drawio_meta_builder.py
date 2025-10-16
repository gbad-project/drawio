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
    ("NotInKnownException", "internal", "metadata", "core"),
    ("_NoCellCloseEnoughException", "xml", "data", "core"),
    ("NoSourceException", "xml", "data", "core"),
    ("NoTargetException", "xml", "data", "core"),
    ("_NoValueException", "xml", "data", "core"),
    ("_SourceNotIndividualException", "internal", "data", "core"),
    ("ArrowWithoutIndividualAsSourceException", "internal", "data", "core"),
    ("_MetacharacterSubstituteParseException", "internal", "metadata", "core"),
    ("MetacharacterException", "internal", "metadata", "core"),
    ("_InvalidCapitalisationSchemeException", "internal", "metadata", "core"),
    ("ParseException", "xml", "data", "core"),
    # metadata getters
    ("get_prefixes", "internal", "metadata", "pre"),
    ("get_ontology_iri", "internal", "metadata", "pre"),
    ("get_prefix", "internal", "metadata", "pre"),
    ("get_prefix_iri", "internal", "metadata", "pre"),
    # xml + curie helpers
    ("_extract_drawio_metadata", "xml", "metadata", "pre"),
    ("_strip_metadata_user_object", "xml", "metadata", "pre"),
    ("_split_curie", "internal", "metadata", "core"),
    ("_ensure_known_curie", "internal", "metadata", "core"),
    ("_verify_is_ric_class", "internal", "metadata", "core"),
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
    ("DrawIOXMLTree.individuals_and_arrows", "xml", "data", "core"),
    # model processing
    ("_handle_spaces", "internal", "metadata", "core"),
    ("_replace_metacharacter", "internal", "metadata", "core"),
    ("_replace_metacharacters", "internal", "metadata", "core"),
    ("_add_individual_type", "internal", "data", "core"),
    ("individual_blocks", "internal", "data", "post"),
    # rdf graph
    ("DrawIOParserGraph", "rdf", "control", "core"),
    ("serialise_to_graph", "rdf", "control", "post"),
    # cli / sdk
    ("_parse_space_substitute", "internal", "data", "core"),
    ("_parse_metacharacter_substitutes", "internal", "data", "core"),
    ("_parse_capitalisation_scheme", "internal", "data", "core"),
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
