import { LOG_PREFIX, logError, logInfo } from "./logging";
import {
  invokeDrawioParser,
  type DrawioParserResult,
  debugPyodide,
} from "./pyodideRuntime";

const BLACK_BOX_PREFIX = "[BLACKBOX]";
const BLACK_BOX_SUFFIX = "[/BLACKBOX]";

function formatParserResult(result: DrawioParserResult): string {
  return JSON.stringify(result, null, 2);
}

export async function runMockBlackBox(serializedXml: string): Promise<string> {
  logInfo(
    LOG_PREFIX.BLACKBOX,
    `Received serialized payload (${serializedXml.length} characters)`,
  );

  try {
    const processed = await invokeDrawioParser(serializedXml);
    logInfo(
      LOG_PREFIX.BLACKBOX,
      `Parsed DrawIO graph ${processed.graphId} with ${processed.tripleCount} triples`,
    );
    const summary = formatParserResult(processed);
    let output = `${BLACK_BOX_PREFIX} len=${serializedXml.length}\n${summary}\n${BLACK_BOX_SUFFIX}`;
    // Override black box summary to show actual graph
    output = processed.rawTurtle
      ? processed.rawTurtle
          .replace(/^"(.*)"$/, "$1")        // strip leading/trailing quote pair
          .replace(/\\n/g, "\n")            // unescape newlines
          .replace(/\\"/g, '"')             // unescape quotes
      : "";
    logInfo(LOG_PREFIX.BLACKBOX, "Black box processing completed");
    return output;
  } catch (error) {
    logError(LOG_PREFIX.BLACKBOX, "Black box processing failed", error);
    throw error;
  }
}

export { debugPyodide };
export type { DrawioParserResult } from "./pyodideRuntime";
