import { LOG_PREFIX, logError, logInfo } from "./logging";
import { invokePyodideMock } from "./pyodideRuntime";

const BLACK_BOX_PREFIX = "[BLACKBOX]";
const BLACK_BOX_SUFFIX = "[/BLACKBOX]";

export async function runMockBlackBox(serializedXml: string): Promise<string> {
  logInfo(
    LOG_PREFIX.BLACKBOX,
    `Received serialized payload (${serializedXml.length} characters)`,
  );

  try {
    const processed = await invokePyodideMock(serializedXml);
    const output = `${BLACK_BOX_PREFIX} len=${serializedXml.length}\n${processed}\n${BLACK_BOX_SUFFIX}`;
    logInfo(LOG_PREFIX.BLACKBOX, "Black box processing completed");
    return output;
  } catch (error) {
    logError(LOG_PREFIX.BLACKBOX, "Black box processing failed", error);
    throw error;
  }
}

export { debugPyodide } from "./pyodideRuntime";
