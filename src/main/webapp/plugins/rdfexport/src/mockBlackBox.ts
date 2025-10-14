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

async function parseSerializedXml(
  serializedXml: string,
): Promise<DrawioParserResult> {
  const processed = await invokeDrawioParser(serializedXml);
  logInfo(
    LOG_PREFIX.BLACKBOX,
    `Parsed DrawIO graph ${processed.graphId} with ${processed.tripleCount} triples`,
  );
  return processed;
}

const RELATIVE_IRI_PATTERN = /<([^>\s]+)>/g;

function isAbsoluteIri(candidate: string): boolean {
  if (candidate.length === 0) {
    return true;
  }

  if (candidate.startsWith("//") || candidate.startsWith("#")) {
    return true;
  }

  return /^[a-zA-Z][\w+.-]*:/.test(candidate);
}

function applyBaseUriToRelativeIris(
  turtle: string,
  baseUri: string | null,
): string {
  if (baseUri == null || baseUri.trim().length === 0) {
    return turtle;
  }

  const trimmedBase = baseUri.trim();

  return turtle.replace(RELATIVE_IRI_PATTERN, (match, iri) => {
    if (isAbsoluteIri(iri) || iri.startsWith(trimmedBase)) {
      return match;
    }

    return `<${trimmedBase}${iri}>`;
  });
}

export async function runMockBlackBox(serializedXml: string): Promise<string> {
  logInfo(
    LOG_PREFIX.BLACKBOX,
    `Received serialized payload (${serializedXml.length} characters)`,
  );

  try {
    const processed = await parseSerializedXml(serializedXml);
    const summary = formatParserResult(processed);
    const output = `${BLACK_BOX_PREFIX} len=${serializedXml.length}\n${summary}\n${BLACK_BOX_SUFFIX}`;
    logInfo(LOG_PREFIX.BLACKBOX, "Black box processing completed");
    return output;
  } catch (error) {
    logError(LOG_PREFIX.BLACKBOX, "Black box processing failed", error);
    throw error;
  }
}

export async function runDrawioPipeline(
  serializedXml: string,
): Promise<string> {
  logInfo(
    LOG_PREFIX.BLACKBOX,
    `Generating Turtle payload for serialized input (${serializedXml.length} characters)`,
  );

  const processed = await parseSerializedXml(serializedXml);

  if (processed.rawTurtle == null || processed.rawTurtle.length === 0) {
    throw new Error("DrawIO parser did not return Turtle serialization");
  }

  logInfo(
    LOG_PREFIX.BLACKBOX,
    `Returning Turtle payload for graph ${processed.graphId} (${processed.rawTurtle.length} characters)`,
  );
  return applyBaseUriToRelativeIris(processed.rawTurtle, processed.baseUri);
}

export { debugPyodide };
export type { DrawioParserResult } from "./pyodideRuntime";
