import { loadPyodide, type PyodideInterface } from "pyodide";
import { LOG_PREFIX, logError, logInfo } from "./logging";

const PROCESS_BOOTSTRAP_SOURCE = `
def process(text: str) -> str:
    """Return a mock transformation result for the DrawIO pipeline."""
    return "mock:" + text
`;

const CDN_FALLBACK_INDEX_URL = "https://cdn.pyodide.org/v0.26.4/full/";

let pyodideInstancePromise: Promise<PyodideInterface> | null = null;
let processBootstrapPromise: Promise<void> | null = null;

function resolveIndexURL(): string {
  const override = (globalThis as { __rdfexportPyodideIndexURL?: unknown })
    .__rdfexportPyodideIndexURL;

  if (typeof override === "string" && override.trim().length > 0) {
    return override;
  }

  if (typeof window === "undefined") {
    const nodeModulesUrl = new URL("../node_modules/pyodide/", import.meta.url);
    if (nodeModulesUrl.protocol === "file:") {
      return decodeURIComponent(nodeModulesUrl.pathname);
    }
    return nodeModulesUrl.toString();
  }

  return CDN_FALLBACK_INDEX_URL;
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

async function ensureProcessBootstrap(): Promise<void> {
  if (processBootstrapPromise != null) {
    return processBootstrapPromise;
  }

  processBootstrapPromise = (async () => {
    const pyodide = await ensurePyodideInstance();
    logInfo(LOG_PREFIX.PIPELINE, "Loading Pyodide mock process module");

    try {
      await pyodide.runPythonAsync(PROCESS_BOOTSTRAP_SOURCE);
      logInfo(LOG_PREFIX.PIPELINE, "Pyodide mock process module loaded");
    } catch (error) {
      logError(
        LOG_PREFIX.PIPELINE,
        "Failed to bootstrap Pyodide mock process",
        error,
      );
      throw error;
    }
  })().catch((error) => {
    processBootstrapPromise = null;
    throw error;
  });

  return processBootstrapPromise;
}

export async function invokePyodideMock(
  serializedXml: string,
): Promise<string> {
  await ensureProcessBootstrap();
  const pyodide = await ensurePyodideInstance();

  logInfo(
    LOG_PREFIX.PIPELINE,
    `Invoking Pyodide mock process (input length ${serializedXml.length})`,
  );

  try {
    const quoted = JSON.stringify(serializedXml);
    const result = await pyodide.runPythonAsync(`process(${quoted})`);
    logInfo(
      LOG_PREFIX.PIPELINE,
      `Pyodide mock process produced ${String(result).length} characters`,
    );
    return result as string;
  } catch (error) {
    logError(
      LOG_PREFIX.PIPELINE,
      "Pyodide mock process invocation failed",
      error,
    );
    throw error;
  }
}

export async function debugPyodide(expression: string): Promise<unknown> {
  const pyodide = await ensurePyodideInstance();
  logInfo(LOG_PREFIX.PIPELINE, `Debugging Pyodide expression: ${expression}`);
  return pyodide.runPythonAsync(expression);
}
