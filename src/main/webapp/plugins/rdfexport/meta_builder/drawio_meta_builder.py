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

def override(*, type: str, role: str, phase: str, target: str | None = None):
    def wrap(fn):
        t = target
        if t is None:
            n = fn.__name__
            for suf in ("_new", "_override", "_ovr"):
                if n.endswith(suf):
                    n = n[: -len(suf)]
                    break
            t = n
        fn.__override__ = (type, role, phase)
        fn.__override_target__ = t
        return fn
    return wrap


# ---- Load legacy module ----
def load_legacy():
    try:
        return importlib.import_module("legacy.original.draw_io_parser")
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


# ---- Load overrides if enabled ----
def load_overrides():
    """Load only @override-decorated objects from legacy/overrides/*.py"""
    overrides = {}
    overrides_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "legacy", "overrides"
    )
    if not os.path.isdir(overrides_dir):
        return overrides

    for fn in os.listdir(overrides_dir):
        if not fn.endswith(".py"):
            continue
        name = os.path.splitext(fn)[0]
        path = os.path.join(overrides_dir, fn)
        spec = importlib.util.spec_from_file_location(f"overrides.{name}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"overrides.{name}"] = mod
        # inject override decorator so @override(...) works inside the module
        mod.override = override
        spec.loader.exec_module(mod)  # type: ignore

        for k, v in vars(mod).items():
            if k.startswith("_"):
                continue
            if inspect.ismodule(v):
                continue
            if getattr(v, "__module__", "").startswith("legacy.draw_io_parser"):
                continue  # ignore imports like “from legacy.draw_io_parser import pipeline”

            meta = getattr(v, "__override__", None)
            if not meta:
                continue  # only decorated

            v.__data_type__, v.__data_role__, v.__phase__ = meta
            tgt = getattr(v, "__override_target__", getattr(v, "__name__", k))
            if tgt in overrides:
                raise RuntimeError(f"Duplicate override for target {tgt}")
            overrides[tgt] = v  # keyed by target name
    return overrides


draw = load_legacy()

# ---- Explicit mapping ----
MAPPING: List[Tuple[str, str, str, str]] = [
    # ===== PRE PHASE =====
    # xml.metadata.pre - Extract metadata from XML
    ("_extract_drawio_metadata", "xml", "metadata", "pre"),
    ("_strip_metadata_user_object", "xml", "metadata", "pre"),
    # internal.metadata.pre - Constants, defaults, type aliases, getters
    ("DEFAULT_CAPITALISATION_SCHEME", "internal", "metadata", "pre"),
    ("DEFAULT_INDENTATION", "internal", "metadata", "pre"),
    ("DEFAULT_MAX_GAP", "internal", "metadata", "pre"),
    ("OWL_METACHARACTERS", "internal", "metadata", "pre"),
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
    ("get_prefixes", "internal", "metadata", "pre"),
    ("get_ontology_iri", "internal", "metadata", "pre"),
    ("get_prefix", "internal", "metadata", "pre"),
    ("get_prefix_iri", "internal", "metadata", "pre"),
    ("SerialisationConfig", "internal", "metadata", "pre"),
    # internal.control.pre - User input via CLI
    ("_arguments_parser", "internal", "control", "pre"),
    # rdf.data.pre - String manipulation for RDF compliance
    ("_handle_spaces", "rdf", "data", "pre"),
    ("_replace_metacharacter", "rdf", "data", "pre"),
    ("_replace_metacharacters", "rdf", "data", "pre"),
    # rdf.control.pre - Validation of RDF config
    ("_parse_capitalisation_scheme", "rdf", "control", "pre"),
    # ===== CORE PHASE =====
    # xml.data.core - ALL XML parsing to Individual/Arrow instances
    ("NothingToParseException", "xml", "data", "core"),
    ("NoSourceException", "xml", "data", "core"),
    ("NoTargetException", "xml", "data", "core"),
    ("_NoValueException", "xml", "data", "core"),
    ("_NoCellCloseEnoughException", "xml", "data", "core"),
    ("ParseException", "xml", "data", "core"),
    ("NodeHTMLParser", "xml", "data", "core"),
    ("DrawIOXMLTree", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_with_id", "xml", "data", "core"),
    ("DrawIOXMLTree._value_of", "xml", "data", "core"),
    ("DrawIOXMLTree._parent_of", "xml", "data", "core"),
    ("DrawIOXMLTree._child_of", "xml", "data", "core"),
    ("DrawIOXMLTree._geometry", "xml", "data", "core"),
    ("DrawIOXMLTree._x_and_y_in_geometry", "xml", "data", "core"),
    ("DrawIOXMLTree._has_correct_as_attribute", "xml", "data", "core"),
    ("DrawIOXMLTree._is_locked", "xml", "data", "core"),
    ("DrawIOXMLTree._start_or_end", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_start", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_end", "xml", "data", "core"),
    ("DrawIOXMLTree._dimensions", "xml", "data", "core"),
    ("DrawIOXMLTree._is_possible_literal", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow_label", "xml", "data", "core"),
    ("DrawIOXMLTree._add_arrow_if_find_label", "xml", "data", "core"),
    (
        "DrawIOXMLTree._extract_individual_and_arrow_and_literal_cells",
        "xml",
        "data",
        "core",
    ),
    ("DrawIOXMLTree._close_enough", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_close_to", "xml", "data", "core"),
    ("DrawIOXMLTree._defines_individual", "xml", "data", "core"),
    ("DrawIOXMLTree._cell_is_literal", "xml", "data", "core"),
    ("DrawIOXMLTree._source_or_target", "xml", "data", "core"),
    ("DrawIOXMLTree._arrow", "xml", "data", "core"),
    ("DrawIOXMLTree.individuals_and_arrows", "xml", "data", "core"),
    # internal.data.core - Internal model classes and data operations
    ("Individual", "internal", "data", "core"),
    ("Arrow", "internal", "data", "core"),
    ("_split_curie", "internal", "data", "core"),
    ("_ensure_known_curie", "internal", "data", "core"),
    ("_verify_is_ric_class", "internal", "data", "core"),
    ("_SourceNotIndividualException", "internal", "data", "core"),
    ("ArrowWithoutIndividualAsSourceException", "internal", "data", "core"),
    ("_add_individual_type", "internal", "data", "core"),
    # internal.control.core - Orchestration: couples data with metadata, produces blocks/props
    ("_parse_space_substitute", "internal", "control", "core"),
    ("_parse_metacharacter_substitutes", "internal", "control", "core"),
    ("individual_blocks", "internal", "control", "core"),
    ("_build_graph_from_raw_xml", "internal", "control", "core"),
    # rdf.data.core - RDF-specific exceptions
    ("NotInKnownException", "rdf", "data", "core"),
    ("_MetacharacterSubstituteParseException", "rdf", "data", "core"),
    ("MetacharacterException", "rdf", "data", "core"),
    ("_InvalidCapitalisationSchemeException", "rdf", "data", "core"),
    # rdf.control.core - Graph class and serialization (called from _build_graph_from_raw_xml)
    ("DrawIOParserGraph", "rdf", "control", "core"),
    ("serialise_to_graph", "rdf", "control", "core"),
    # ===== POST PHASE =====
    # internal.control.post - SDK/CLI wrappers
    ("parse_drawio_to_graph", "internal", "control", "post"),
    ("_run", "internal", "control", "post"),
    ("main", "internal", "control", "post"),
]


# ---- Helpers ----
def resolve(name: str):
    base = name.split(".")[-1]
    if OVERRIDES_ENABLED and base in overrides_dict:
        return overrides_dict[base]
    cur = draw
    for part in name.split("."):
        cur = getattr(cur, part)
    return cur


def safe_source(obj) -> str:
    import textwrap

    try:
        src = inspect.getsource(obj)
        return textwrap.dedent(src)
    except Exception:
        return f"# source unavailable for {getattr(obj, '__name__', repr(obj))}\n"
    
def strip_override_decorator(src: str) -> str:
    """Remove any @override(...) decorator lines from a function's source."""
    out_lines = []
    skip = False
    for raw_line in src.splitlines():
        line = raw_line.lstrip()  # ignore indentation
        # start of decorator
        if line.startswith("@override("):
            skip = True
            # if decorator ends on same line, clear skip immediately
            if line.rstrip().endswith(")"):
                skip = False
            continue
        # continuation of decorator across lines
        if skip:
            if line.rstrip().endswith(")"):
                skip = False
            continue
        out_lines.append(raw_line)
    return "\n".join(out_lines)


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

    # ---- dynamically build pipeline tree ----
    def build_pipeline_structure():
        phases, types, roles = set(), set(), set()
        for _, dt, dr, ph in MAPPING:
            phases.add(ph); types.add(dt); roles.add(dr)
        if OVERRIDES_ENABLED and overrides_dict:
            for obj in overrides_dict.values():
                phases.add(getattr(obj, "__phase__", "core"))
                types.add(getattr(obj, "__data_type__", "internal"))
                roles.add(getattr(obj, "__data_role__", "control"))

        lines = ["class pipeline:"]
        for ph in sorted(phases):
            lines.append(f"    class {ph}:")
            for dt in sorted(types):
                lines.append(f"        class {dt}:")
                for dr in sorted(roles):
                    lines.append(f"            class {dr}: pass")
        return "\n".join(lines) + "\n"
    
    out.append(build_pipeline_structure())

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
                        # If this symbol came from an override module, drop the decorator
                        if getattr(obj, "__override__", None):
                            src = strip_override_decorator(src)
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
                    # Inline inject overrides targeting this exact (phase, type, role)
                    injected = False
                    if OVERRIDES_ENABLED and overrides_dict:
                        for target, obj in overrides_dict.items():
                            if (
                                getattr(obj, "__data_type__", None) == dt
                                and getattr(obj, "__data_role__", None) == dr
                                and getattr(obj, "__phase__", None) == ph
                            ):
                                # never include the override decorator definition itself
                                if getattr(obj, "__name__", "") == "override":
                                    continue
                                src = get_source_or_repr(target, obj)
                                src = strip_override_decorator(src)
                                block = indent(
                                    f"# BEGIN override {target}\n{src}\n# END override {target}\n", 4
                                )
                                out.append(block)
                                injected = True
                    if not injected:
                        out.append(indent("pass", 4))
                out.append("")

    orchestrator = """
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
        alias_lines.append(
            f"setattr(pipeline.{ph}.{dt}.{dr}, '{base}', {dt}_{dr}_{ph}.{base})"
        )

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
    parser.add_argument(
        "--overrides",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable overrides (default: enabled)",
    )
    args = parser.parse_args()

    global OVERRIDES_ENABLED, overrides_dict
    OVERRIDES_ENABLED = args.overrides
    overrides_dict = load_overrides() if OVERRIDES_ENABLED else {}

    write_output(args.output)


if __name__ == "__main__":
    main()
