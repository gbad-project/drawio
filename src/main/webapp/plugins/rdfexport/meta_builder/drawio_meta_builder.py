# drawio_meta_builder.py
# Generate a new source file drawio_meta.py by reorganizing real code bodies
# from draw_io_parser across three axes (data_type, data_role, phase).

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import inspect
import os
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Dict, List, Tuple


VALID_TYPES = {"xml", "internal", "rdf"}
VALID_ROLES = {"metadata", "data", "control"}
VALID_PHASES = {"pre", "core", "post"}
MODULE_LEVEL_ALIASES_FOR_NEW = False


@dataclass(frozen=True)
class OverrideSpec:
    data_type: str
    data_role: str
    phase: str


@dataclass(frozen=True)
class OverrideRecord:
    name: str
    spec: OverrideSpec
    obj: object
    module: ModuleType
    source_path: str | None = None

    def normalised_source(self) -> str:
        src = get_source_or_repr(self.name, self.obj)
        return strip_override_decorator(src)

    def origin_label(self) -> str:
        if self.source_path:
            return os.path.basename(self.source_path)
        return getattr(self.module, "__name__", repr(self.module))


@dataclass
class OverrideCollection:
    replacements: Dict[tuple[str, str, str, str], OverrideRecord]
    extras: Dict[tuple[str, str, str], List[OverrideRecord]]
    modules: List[str]
    external_imports: List[str]

    @property
    def replacement_count(self) -> int:
        return len(self.replacements)

    @property
    def addition_count(self) -> int:
        return sum(len(v) for v in self.extras.values())


DEFAULT_OVERRIDES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "legacy", "overrides")
)


def override(*, type: str, role: str, phase: str):
    """Decorator used by override modules to tag replacement callables."""

    if type not in VALID_TYPES:
        raise ValueError(
            f"override invalid type '{type}'. Expected one of: {sorted(VALID_TYPES)}"
        )
    if role not in VALID_ROLES:
        raise ValueError(
            f"override invalid role '{role}'. Expected one of: {sorted(VALID_ROLES)}"
        )
    if phase not in VALID_PHASES:
        raise ValueError(
            f"override invalid phase '{phase}'. Expected one of: {sorted(VALID_PHASES)}"
        )

    spec = OverrideSpec(type, role, phase)

    def decorator(obj):
        if not callable(obj):
            raise TypeError("@override can only be applied to callables")
        setattr(obj, "__drawio_override__", spec)
        return obj

    return decorator


# ---- Load legacy module ----
def load_legacy():
    try:
        return importlib.import_module("legacy.original.draw_io_parser")
    except ModuleNotFoundError:
        here = os.path.dirname(__file__)
        search = [
            os.path.join(here, "..", "legacy", "original", "draw_io_parser.py"),
            os.path.join(here, "draw_io_parser.py"),
        ]
        for path in search:
            norm = os.path.normpath(path)
            if os.path.exists(norm):
                spec = importlib.util.spec_from_file_location("draw_io_parser", norm)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["draw_io_parser"] = mod
                spec.loader.exec_module(mod)  # type: ignore[arg-type]
                return mod
        raise RuntimeError("draw_io_parser source not found")


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


MAPPING_INDEX: Dict[tuple[str, str, str, str], str] = {}
for dotted, dt, dr, ph in MAPPING:
    base = dotted.split(".")[-1]
    MAPPING_INDEX[(dt, dr, ph, base)] = dotted


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


def strip_override_decorator(src: str) -> str:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src

    def is_override_decorator(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id == "override"
        if isinstance(node, ast.Attribute):
            return node.attr == "override"
        if isinstance(node, ast.Call):
            return is_override_decorator(node.func)
        return False

    class _StripOverride(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef):  # type: ignore[override]
            node.decorator_list = [
                d for d in node.decorator_list if not is_override_decorator(d)
            ]
            return self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # type: ignore[override]
            node.decorator_list = [
                d for d in node.decorator_list if not is_override_decorator(d)
            ]
            return self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef):  # type: ignore[override]
            node.decorator_list = [
                d for d in node.decorator_list if not is_override_decorator(d)
            ]
            return self.generic_visit(node)

    new_tree = _StripOverride().visit(tree)
    try:
        return ast.unparse(new_tree)
    except Exception:
        return src


def format_import_node(node: ast.AST) -> str:
    if isinstance(node, ast.Import):
        names = [n.name + (f" as {n.asname}" if n.asname else "") for n in node.names]
        return "import " + ", ".join(names)
    if isinstance(node, ast.ImportFrom):
        module = ("." * node.level) + (node.module or "")
        names = [n.name + (f" as {n.asname}" if n.asname else "") for n in node.names]
        return f"from {module} import " + ", ".join(names)
    raise TypeError(f"Unsupported import node: {ast.dump(node)}")


def collect_overrides(
    enabled: bool = True, overrides_dir: str | None = None
) -> OverrideCollection:
    if not enabled:
        return OverrideCollection({}, {}, [], [])

    directory = os.path.normpath(overrides_dir or DEFAULT_OVERRIDES_DIR)
    if not os.path.isdir(directory):
        return OverrideCollection({}, {}, [], [])

    replacements: Dict[tuple[str, str, str, str], OverrideRecord] = {}
    extras: Dict[tuple[str, str, str], List[OverrideRecord]] = {}
    modules: List[str] = []
    external_imports: List[str] = []
    seen_external_imports: set[str] = set()

    for idx, filename in enumerate(sorted(os.listdir(directory))):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        path = os.path.join(directory, filename)
        module_name = f"drawio_meta_override_{idx}_{os.path.splitext(filename)[0]}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load override module from {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        modules.append(os.path.relpath(path, directory))

        try:
            with open(path, "r", encoding="utf-8") as handle:
                override_src = handle.read()
        except OSError:
            override_src = ""

        try:
            override_tree = ast.parse(override_src or "")
        except SyntaxError:
            override_tree = None

        if override_tree is not None:
            for node in override_tree.body:
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(node, ast.ImportFrom):
                    module_name = ("." * node.level) + (node.module or "")
                    if module_name == "__future__":
                        continue
                    if module_name.startswith("meta_builder"):
                        continue
                    if module_name.startswith("legacy."):
                        continue
                    if module_name.startswith("."):
                        continue
                    formatted = format_import_node(node)
                else:
                    names = [
                        alias
                        for alias in node.names
                        if not alias.name.startswith("meta_builder")
                        and not alias.name.startswith("legacy.")
                    ]
                    if not names:
                        continue
                    formatted = format_import_node(ast.Import(names=names))
                if formatted not in seen_external_imports:
                    seen_external_imports.add(formatted)
                    external_imports.append(formatted)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            spec_attr = getattr(attr, "__drawio_override__", None)
            if spec_attr is None:
                continue
            if not isinstance(spec_attr, OverrideSpec):
                raise TypeError(
                    f"Object {attr_name} in {module.__name__} carries an invalid override"
                )
            record = OverrideRecord(attr.__name__, spec_attr, attr, module, path)
            key = (
                spec_attr.data_type,
                spec_attr.data_role,
                spec_attr.phase,
                record.name,
            )
            if key in MAPPING_INDEX:
                if key in replacements:
                    raise ValueError(
                        f"Duplicate override for {record.name} in {module.__name__}"
                    )
                replacements[key] = record
            else:
                extra_key = (
                    spec_attr.data_type,
                    spec_attr.data_role,
                    spec_attr.phase,
                )
                existing = extras.setdefault(extra_key, [])
                if any(r.name == record.name for r in existing):
                    raise ValueError(
                        f"Duplicate override name {record.name} for {extra_key}"
                    )
                existing.append(record)

    for values in extras.values():
        values.sort(key=lambda r: r.name)

    return OverrideCollection(replacements, extras, modules, external_imports)


# ---- Code generator ----
def build_pipeline_namespace(overrides: OverrideCollection) -> str:
    lines: List[str] = ["class pipeline:"]
    for ph in ["pre", "core", "post"]:
        lines.append(f"    class {ph}:")
        for dt in ["xml", "internal", "rdf"]:
            lines.append(f"        class {dt}:")
            for dr in ["metadata", "data", "control"]:
                lines.append(f"            class {dr}:")
                extra_records = overrides.extras.get((dt, dr, ph), [])
                if extra_records:
                    for record in extra_records:
                        label = f"{record.origin_label()}.{record.name}"
                        block = (
                            f"# BEGIN override {label}\n"
                            f"{record.normalised_source()}\n"
                            f"# END override {label}\n"
                        )
                        lines.append(indent(block, 16))
                else:
                    lines.append(" " * 16 + "pass")
                lines.append("")
    return "\n".join(lines)


def build_output(
    *, use_overrides: bool = True, overrides_dir: str | None = None
) -> tuple[str, OverrideCollection]:
    overrides = collect_overrides(enabled=use_overrides, overrides_dir=overrides_dir)

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
            module_name = ""
            if isinstance(node, ast.ImportFrom):
                module_name = ("." * node.level) + (node.module or "")
            if module_name == "__future__":
                continue
            import_lines.append(format_import_node(node))
    import_lines.extend(overrides.external_imports)
    seen = set()
    ordered = []
    for line in import_lines:
        if line not in seen:
            seen.add(line)
            ordered.append(line)
    out = ["\n".join(header) + ("\n" + "\n".join(ordered) + "\n" if ordered else "\n")]

    out.append(build_pipeline_namespace(overrides))

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
                        base = name.split(".")[-1]
                        override_record = overrides.replacements.get((dt, dr, ph, base))
                        if override_record:
                            obj = override_record.obj
                            src = override_record.normalised_source()
                            src = (
                                f"# override from {override_record.origin_label()}\n"
                                + src
                            )
                        else:
                            obj = resolve(name)
                            src = get_source_or_repr(name, obj)
                        if not override_record and inspect.isclass(obj):
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

    if MODULE_LEVEL_ALIASES_FOR_NEW:
        for (dt, dr, ph), records in overrides.extras.items():
            for record in records:
                alias_lines.append(
                    f"{record.name} = pipeline.{ph}.{dt}.{dr}.{record.name}"
                )

    src += "\n" + "\n".join(alias_lines) + "\n"

    return src, overrides


def write_output(
    path: str = "drawio_meta.py",
    *,
    use_overrides: bool = True,
    overrides_dir: str | None = None,
) -> tuple[str, OverrideCollection]:
    src, overrides = build_output(
        use_overrides=use_overrides, overrides_dir=overrides_dir
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return path, overrides


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
        help="Enable discovery of legacy/overrides modules (default: enabled)",
    )
    parser.add_argument(
        "--overrides-dir",
        default=None,
        help="Custom directory to search for overrides (defaults to legacy/overrides)",
    )
    args = parser.parse_args()

    path, overrides = write_output(
        args.output,
        use_overrides=args.overrides,
        overrides_dir=args.overrides_dir,
    )

    directory = os.path.normpath(args.overrides_dir or DEFAULT_OVERRIDES_DIR)
    status = "on" if args.overrides else "off"

    def format_override_summary(overrides, path, status):
        replaced = sorted(r.name for r in overrides.replacements.values())
        added = sorted(r.name for records in overrides.extras.values() for r in records)
        parts = [
            f"[metabuilder] Wrote {path} ( overrides {status}; "
            f"replacements={len(replaced)}"
            + (f" [{', '.join(replaced)}]" if replaced else ""),
            f"additions={len(added)}" + (f" [{', '.join(added)}]" if added else ""),
            ")",
        ]
        return " ".join(parts)

    print(format_override_summary(overrides, path, status))
    if args.overrides:
        if overrides.modules:
            modules = ", ".join(overrides.modules)
            print(f"[metabuilder] Loaded override modules from {directory}: {modules}")
        else:
            print(f"[metabuilder] No override modules discovered in {directory}.")
    else:
        print("[metabuilder] Override discovery disabled via --no-overrides.")


if __name__ == "__main__":
    main()
