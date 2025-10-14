import { loadPyodide, type PyodideInterface } from "pyodide";

import drawIoParserSource from "../legacy/draw_io_parser.py?raw";
import pipelineInitSource from "../pyodide_pipeline/__init__.py?raw";
import drawioPipelineSource from "../pyodide_pipeline/drawio_pipeline.py?raw";
import rdflibWheelBase64 from "../pyodide/wheels/rdflib-7.2.1-py3-none-any.whl.base64?raw";
import { LOG_PREFIX, logError, logInfo } from "./logging";

export interface DrawioParserResult {
  graphId: string;
  tripleCount: number;
  csvPath: string | null;
  baseUri: string | null;
  namespaces: Array<{ prefix: string; iri: string }>;
  rawTurtle: string | null;
}

type RawGraphSummary = {
  graph_id: string;
  triple_count: number;
  csv_path: string | null;
  base_uri: string | null;
  namespaces: Array<{ prefix: string; iri: string }>;
  raw_turtle: string | null;
};

const CDN_FALLBACK_INDEX_URL = "https://cdn.pyodide.org/v0.28.3/full/";
const LOCAL_RELATIVE_PYODIDE_PATH = "../plugins/rdfexport/pyodide/";
const PYODIDE_APP_ROOT = "/app";

const PYTHON_MODULES: Array<{ path: string; source: string }> = [
  {
    path: `${PYODIDE_APP_ROOT}/legacy/draw_io_parser.py`,
    source: drawIoParserSource,
  },
  {
    path: `${PYODIDE_APP_ROOT}/pyodide_pipeline/__init__.py`,
    source: pipelineInitSource,
  },
  {
    path: `${PYODIDE_APP_ROOT}/pyodide_pipeline/drawio_pipeline.py`,
    source: drawioPipelineSource,
  },
];

function normalizeBase64(value: string): string {
  return value.replace(/\s+/g, "");
}

function decodeBase64ToUint8Array(base64: string): Uint8Array {
  const normalized = normalizeBase64(base64);
  const atobFn = (globalThis as { atob?: (data: string) => string }).atob;

  if (typeof atobFn === "function") {
    const binary = atobFn(normalized);
    const bytes = new Uint8Array(binary.length);

    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }

    return bytes;
  }

  const bufferCtor = (
    globalThis as {
      Buffer?: {
        from: (input: string, encoding: string) => ArrayBuffer | Uint8Array;
      };
    }
  ).Buffer;

  if (bufferCtor?.from) {
    const bufferOutput = bufferCtor.from(normalized, "base64");
    if (bufferOutput instanceof Uint8Array) {
      return new Uint8Array(bufferOutput);
    }

    return new Uint8Array(bufferOutput);
  }

  throw new Error("Unable to decode base64 content in this environment");
}

const rdflibWheelBytes = decodeBase64ToUint8Array(rdflibWheelBase64);

const PYTHON_WHEELS: Array<{ path: string; data: Uint8Array }> = [
  {
    path: `${PYODIDE_APP_ROOT}/wheels/rdflib-7.2.1-py3-none-any.whl`,
    data: rdflibWheelBytes,
  },
];

let pyodideInstancePromise: Promise<PyodideInterface> | null = null;
let pythonEnvironmentPromise: Promise<void> | null = null;

function ensureTrailingSlash(value: string): string {
  return value.endsWith("/") ? value : `${value}/`;
}

function resolveFromBrowserContext(): string | null {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return null;
  }

  const currentScript = document.currentScript as HTMLScriptElement | null;

  if (currentScript?.src) {
    try {
      const scriptUrl = new URL(currentScript.src, window.location.href);
      const pluginDir = new URL("./rdfexport/", scriptUrl);
      const pyodideUrl = new URL("./pyodide/", pluginDir).toString();
      return ensureTrailingSlash(pyodideUrl);
    } catch (error) {
      logError(
        LOG_PREFIX.PIPELINE,
        "Failed to derive Pyodide index URL from current script",
        error,
      );
    }
  }

  const mxBasePath = (globalThis as { mxBasePath?: unknown }).mxBasePath;

  if (typeof mxBasePath === "string" && mxBasePath.trim().length > 0) {
    const normalizedBase = ensureTrailingSlash(mxBasePath.trim());
    return ensureTrailingSlash(
      `${normalizedBase}${LOCAL_RELATIVE_PYODIDE_PATH}`,
    );
  }

  if (typeof window.location?.href === "string") {
    const derived = new URL(
      `./${LOCAL_RELATIVE_PYODIDE_PATH}`,
      window.location.href,
    );
    return ensureTrailingSlash(derived.toString());
  }

  return null;
}

function normaliseIndexURL(raw: string): string {
  const trimmed = raw.trim();

  if (trimmed.startsWith("file://")) {
    if (typeof window === "undefined") {
      try {
        const parsed = new URL(trimmed);
        const pathname = decodeURIComponent(parsed.pathname);
        return ensureTrailingSlash(pathname);
      } catch (error) {
        logError(
          LOG_PREFIX.PIPELINE,
          "Failed to normalise file URL for Pyodide index",
          error,
        );
      }
    }

    return ensureTrailingSlash(trimmed);
  }

  return ensureTrailingSlash(trimmed);
}

function resolveIndexURL(): string {
  const override = (globalThis as { __rdfexportPyodideIndexURL?: unknown })
    .__rdfexportPyodideIndexURL;

  if (typeof override === "string" && override.trim().length > 0) {
    return normaliseIndexURL(override);
  }

  const browserResolved = resolveFromBrowserContext();
  if (browserResolved) {
    return normaliseIndexURL(browserResolved);
  }

  return normaliseIndexURL(CDN_FALLBACK_INDEX_URL);
}

async function initializePyodide(): Promise<PyodideInterface> {
  const indexURL = resolveIndexURL();
  logInfo(LOG_PREFIX.PIPELINE, `Initializing Pyodide runtime from ${indexURL}`);

  try {
    const pyodide = await loadPyodide({
      indexURL,
      stdout: (text: string) => {
        logInfo(LOG_PREFIX.PYODIDE, text);
      },
      stderr: (text: string) => {
        logError(LOG_PREFIX.PYODIDE, text);
      },
    });

    logInfo(LOG_PREFIX.PIPELINE, "Pyodide runtime ready");
    return pyodide;
  } catch (error) {
    logError(LOG_PREFIX.PIPELINE, "Pyodide initialization failed", error);
    throw error;
  }
}

export function ensurePyodideInstance(): Promise<PyodideInterface> {
  if (pyodideInstancePromise == null) {
    pyodideInstancePromise = initializePyodide().catch((error) => {
      pyodideInstancePromise = null;
      throw error;
    });
  }

  return pyodideInstancePromise;
}

function writePythonModule(
  pyodide: PyodideInterface,
  path: string,
  source: string,
): void {
  const fs = pyodide.FS as unknown as {
    mkdirTree: (dir: string) => void;
    analyzePath: (target: string) => { exists: boolean };
    readFile: (target: string, options: { encoding: "utf8" }) => string;
    writeFile: (
      target: string,
      data: string,
      options: { encoding: "utf8" },
    ) => void;
  };
  const directory = path.split("/").slice(0, -1).join("/") || "/";
  try {
    fs.mkdirTree(directory);
  } catch (error: unknown) {
    // Ignore EEXIST errors from mkdirTree; rethrow anything else.
    const fsError = error as { code?: string };
    if (fsError?.code !== "EEXIST") {
      throw error;
    }
  }

  const existing = fs.analyzePath(path).exists
    ? fs.readFile(path, { encoding: "utf8" })
    : null;

  if (existing !== source) {
    fs.writeFile(path, source, { encoding: "utf8" });
  }
}

function writeBinaryFile(
  pyodide: PyodideInterface,
  path: string,
  data: Uint8Array,
): void {
  const fs = pyodide.FS as unknown as {
    mkdirTree: (dir: string) => void;
    analyzePath: (target: string) => { exists: boolean };
    readFile: (target: string) => Uint8Array;
    writeFile: (target: string, content: ArrayBuffer) => void;
  };

  const directory = path.split("/").slice(0, -1).join("/") || "/";
  try {
    fs.mkdirTree(directory);
  } catch (error: unknown) {
    const fsError = error as { code?: string };
    if (fsError?.code !== "EEXIST") {
      throw error;
    }
  }

  const existing = fs.analyzePath(path).exists ? fs.readFile(path) : null;

  if (
    existing == null ||
    existing.length !== data.length ||
    !existing.every((value, index) => value === data[index])
  ) {
    fs.writeFile(path, data);
  }
}

async function ensurePythonEnvironment(): Promise<void> {
  if (pythonEnvironmentPromise != null) {
    return pythonEnvironmentPromise;
  }

  pythonEnvironmentPromise = (async () => {
    const pyodide = await ensurePyodideInstance();
    logInfo(LOG_PREFIX.PIPELINE, "Preparing Pyodide Python environment");

    for (const module of PYTHON_MODULES) {
      logInfo(
        LOG_PREFIX.PIPELINE,
        `Syncing Python module to virtual FS: ${module.path}`,
      );
      writePythonModule(pyodide, module.path, module.source);
    }

    for (const wheel of PYTHON_WHEELS) {
      logInfo(
        LOG_PREFIX.PIPELINE,
        `Syncing Python wheel to virtual FS: ${wheel.path}`,
      );
      writeBinaryFile(pyodide, wheel.path, wheel.data);
    }

    const bootstrapScript = `
import sys
from pathlib import Path
import importlib.util
if "${PYODIDE_APP_ROOT}" not in sys.path:
    sys.path.insert(0, "${PYODIDE_APP_ROOT}")
if importlib.util.find_spec("rdflib") is None:
    import zipfile
    target = Path("${PYODIDE_APP_ROOT}/packages")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile("${PYODIDE_APP_ROOT}/wheels/rdflib-7.2.1-py3-none-any.whl") as archive:
        archive.extractall(target)
    if str(target) not in sys.path:
        sys.path.insert(0, str(target))
from pyodide_pipeline import reset_graph_store
reset_graph_store()
`;

    try {
      await pyodide.runPythonAsync(bootstrapScript);
      logInfo(LOG_PREFIX.PIPELINE, "Pyodide Python environment ready");
    } catch (error) {
      logError(
        LOG_PREFIX.PIPELINE,
        "Failed to bootstrap Pyodide Python environment",
        error,
      );
      throw error;
    }
  })().catch((error) => {
    pythonEnvironmentPromise = null;
    throw error;
  });

  return pythonEnvironmentPromise;
}

function decodeRawTurtle(raw: string | null): string | null {
  if (raw == null) {
    return null;
  }

  try {
    return JSON.parse(raw) as string;
  } catch (error) {
    logError(LOG_PREFIX.PIPELINE, "Failed to decode raw Turtle payload", error);
    return raw;
  }
}

function mapRawSummary(raw: RawGraphSummary): DrawioParserResult {
  return {
    graphId: raw.graph_id,
    tripleCount: raw.triple_count,
    csvPath: raw.csv_path,
    baseUri: raw.base_uri,
    namespaces: raw.namespaces.map((entry) => ({
      prefix: entry.prefix,
      iri: entry.iri,
    })),
    rawTurtle: decodeRawTurtle(raw.raw_turtle),
  };
}

export async function invokeDrawioParser(
  serializedXml: string,
): Promise<DrawioParserResult> {
  await ensurePythonEnvironment();
  const pyodide = await ensurePyodideInstance();

  logInfo(
    LOG_PREFIX.PIPELINE,
    `Invoking DrawIO parser via Pyodide (input length ${serializedXml.length})`,
  );

  try {
    const quoted = JSON.stringify(serializedXml);
    const jsonResult = (await pyodide.runPythonAsync(
      `from pyodide_pipeline.drawio_pipeline import parse_drawio_xml_to_json\nparse_drawio_xml_to_json(${quoted})`,
    )) as string;

    const rawSummary = JSON.parse(jsonResult) as RawGraphSummary;
    const mapped = mapRawSummary(rawSummary);

    logInfo(
      LOG_PREFIX.PIPELINE,
      `DrawIO parser produced graph ${mapped.graphId} with ${mapped.tripleCount} triples`,
    );
    return mapped;
  } catch (error) {
    logError(
      LOG_PREFIX.PIPELINE,
      "Pyodide DrawIO parser invocation failed",
      error,
    );
    throw error;
  }
}

export async function debugPyodide(expression: string): Promise<unknown> {
  const pyodide = await ensurePyodideInstance();
  // AICODE-NOTE: never remove the below commented out line! It must stay. Signed-off: human
  //logInfo(LOG_PREFIX.PIPELINE, `Debugging Pyodide expression: ${expression}`);
  return pyodide.runPythonAsync(expression);
}
