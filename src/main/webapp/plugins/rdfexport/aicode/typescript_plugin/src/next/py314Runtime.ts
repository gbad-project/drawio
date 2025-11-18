import drawIoParserSource from "../legacy/draw_io_parser.py?raw";
import pipelineInitSource from "../pyodide_pipeline/__init__.py?raw";
import drawioPipelineSource from "../pyodide_pipeline/drawio_pipeline.py?raw";
import { LOG_PREFIX, logError, logInfo } from "../aicode/src/logging";

// Type definitions
export interface DrawioParserResult {
  graphId: string;
  tripleCount: number;
  csvPath: string | null;
  baseUri: string | null;
  namespaces: Array<{ prefix: string; iri: string }>;
  rawTurtle: string | null;
}

export interface DrawioParserConfigPayload {
  infer_type_of_literals: boolean;
  include_preamble: boolean;
  ontology_iri: string | null;
  prefix: string | null;
  prefix_iri: string | null;
  indentation: number;
  include_label: boolean;
  max_gap: number;
  strict_mode: boolean;
  strip_html: boolean;
  metacharacter_substitute: string[];
  capitalisation_scheme: string;
  rml_enabled: boolean;
}

type RawGraphSummary = {
  graph_id: string;
  triple_count: number;
  csv_path: string | null;
  base_uri: string | null;
  namespaces: Array<{ prefix: string; iri: string }>;
  raw_turtle: string | null;
};

// Paths inside the virtual FS
const PYTHON_APP_ROOT = "/app";

const PYTHON_MODULES: Array<{ path: string; source: string }> = [
  { path: `${PYTHON_APP_ROOT}/legacy/draw_io_parser.py`, source: drawIoParserSource },
  { path: `${PYTHON_APP_ROOT}/pyodide_pipeline/__init__.py`, source: pipelineInitSource },
  { path: `${PYTHON_APP_ROOT}/pyodide_pipeline/drawio_pipeline.py`, source: drawioPipelineSource },
];

// Load the Emscripten-built Python 3.14
import initPython from "../plugins/rdfexport/py314_wasm/python.mjs?url";

let pythonInstancePromise: Promise<any> | null = null;
let pythonEnvironmentPromise: Promise<void> | null = null;

export function ensurePythonInstance(): Promise<any> {
  if (!pythonInstancePromise) {
    pythonInstancePromise = (async () => {
      const py = await initPython({
        print: (text: string) => logInfo(LOG_PREFIX.PYTHON, text),
        printErr: (text: string) => logError(LOG_PREFIX.PYTHON, text),
      });
      logInfo(LOG_PREFIX.PIPELINE, "Emscripten Python runtime ready");
      return py;
    })();
  }
  return pythonInstancePromise;
}

// Write Python scripts into virtual FS
async function writePythonModules(py: any) {
  const FS = py.FS as any;
  for (const module of PYTHON_MODULES) {
    const dir = module.path.split("/").slice(0, -1).join("/") || "/";
    try { FS.mkdirTree(dir); } catch (e) { /* ignore EEXIST */ }
    FS.writeFile(module.path, module.source);
    logInfo(LOG_PREFIX.PIPELINE, `Injected Python module: ${module.path}`);
  }
}

// Bootstrap environment: add /app to sys.path and reset pipeline
async function ensurePythonEnvironment(): Promise<void> {
  if (pythonEnvironmentPromise) return pythonEnvironmentPromise;

  pythonEnvironmentPromise = (async () => {
    const py = await ensurePythonInstance();
    await writePythonModules(py);

    const bootstrap = `
import sys
if "${PYTHON_APP_ROOT}" not in sys.path:
    sys.path.insert(0, "${PYTHON_APP_ROOT}")
from pyodide_pipeline import reset_graph_store
reset_graph_store()
`;
    try {
      await py.runPythonAsync(bootstrap);
      logInfo(LOG_PREFIX.PIPELINE, "Python environment bootstrapped");
    } catch (error) {
      logError(LOG_PREFIX.PIPELINE, "Failed to bootstrap Python environment", error);
      throw error;
    }
  })();

  return pythonEnvironmentPromise;
}

function decodeRawTurtle(raw: string | null): string | null {
  if (!raw) return null;
  try { return JSON.parse(raw) as string; } catch { return raw; }
}

function mapRawSummary(raw: RawGraphSummary): DrawioParserResult {
  return {
    graphId: raw.graph_id,
    tripleCount: raw.triple_count,
    csvPath: raw.csv_path,
    baseUri: raw.base_uri,
    namespaces: raw.namespaces.map((n) => ({ prefix: n.prefix, iri: n.iri })),
    rawTurtle: decodeRawTurtle(raw.raw_turtle),
  };
}

// Main parser invocation
export async function invokeDrawioParser(
  serializedXml: string,
  config?: DrawioParserConfigPayload | null
): Promise<DrawioParserResult> {
  await ensurePythonEnvironment();
  const py = await ensurePythonInstance();

  logInfo(LOG_PREFIX.PIPELINE, `Invoking DrawIO parser (input length ${serializedXml.length})`);

  try {
    const quoted = JSON.stringify(serializedXml);
    const configJson = JSON.stringify(config ?? null);

    const jsonResult = await py.runPythonAsync(`
from pyodide_pipeline.drawio_pipeline import parse_drawio_xml_to_json
import json
parse_drawio_xml_to_json(${quoted}, json.loads(${JSON.stringify(configJson)}))
`);
    const rawSummary = JSON.parse(jsonResult) as RawGraphSummary;
    const mapped = mapRawSummary(rawSummary);
    logInfo(LOG_PREFIX.PIPELINE, `Parser produced graph ${mapped.graphId} with ${mapped.tripleCount} triples`);
    return mapped;
  } catch (error) {
    logError(LOG_PREFIX.PIPELINE, "DrawIO parser invocation failed", error);
    throw error;
  }
}

// Debug helper
export async function debugPython(expression: string): Promise<unknown> {
  const py = await ensurePythonInstance();
  return py.runPythonAsync(expression);
}
