export const LOG_PREFIX = {
  PYODIDE: "[PYODIDE]",
  BLACKBOX: "[BLACKBOX]",
  PIPELINE: "[PIPELINE]",
  TEST: "[TEST]",
} as const;

export type LogPrefix = (typeof LOG_PREFIX)[keyof typeof LOG_PREFIX];

export function logInfo(
  prefix: LogPrefix,
  message: string,
  ...args: unknown[]
): void {
  console.info(`${prefix} ${message}`, ...args);
}

export function logWarn(
  prefix: LogPrefix,
  message: string,
  ...args: unknown[]
): void {
  console.warn(`${prefix} ${message}`, ...args);
}

export function logError(
  prefix: LogPrefix,
  message: string,
  error?: unknown,
): void {
  if (typeof error === "undefined") {
    console.error(`${prefix} ${message}`);
    return;
  }

  console.error(`${prefix} ${message}`, error);
}
