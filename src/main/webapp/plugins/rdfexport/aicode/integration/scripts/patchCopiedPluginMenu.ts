#!/usr/bin/env bun

import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import * as yaml from "js-yaml";

interface RawMenuConfig {
  title?: unknown;
  "quick-start-video"?: unknown;
  support?: unknown;
  gtag?: unknown;
  canonical?: unknown;
}

interface MenuConfig {
  title: string;
  quickStartVideo: string;
  support: string;
  gtag: string | null;
  canonical: string | null;
}

interface ParsedArgs {
  configPath: string;
  targetPath: string;
  htmlSourcePath: string;
  htmlTargetPath: string;
}

const PATCH_START = "/* RDFEXPORT_MENU_PATCH_START */";
const PATCH_END = "/* RDFEXPORT_MENU_PATCH_END */";
const LOAD_PLUGIN_PATTERN = /Draw\.loadPlugin\(function\(editorUi\)\s*\{/g;
const HEAD_TAG_PATTERN = /<head>/g;
const GOOGLE_TAG_PATTERN =
  /<!-- Google tag \(gtag\.js\) -->\r?\n<script async src="https:\/\/www\.googletagmanager\.com\/gtag\/js\?id=[^"\r\n]+"><\/script>\r?\n<script>\r?\n  window\.dataLayer = window\.dataLayer \|\| \[\];\r?\n  function gtag\(\)\{dataLayer\.push\(arguments\);\}\r?\n  gtag\('js', new Date\(\)\);\r?\n\r?\n  gtag\('config', '[^'\r\n]+'\);\r?\n<\/script>/g;
const CANONICAL_TAG_PATTERN = /<link rel="canonical" href="[^"]*"\s*\/?>/i;

const scriptDir = dirname(fileURLToPath(import.meta.url));
const pluginRoot = resolve(scriptDir, "../../..");
const defaultConfigPath = resolve(pluginRoot, "menu.yml");
const defaultTargetPath = resolve(pluginRoot, "../rdfexport.js");
const defaultHtmlSourcePath = resolve(pluginRoot, "assets/index.html");
const defaultHtmlTargetPath = resolve(pluginRoot, "../../index.html");

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function requireString(value: unknown, key: string): string {
  if (typeof value !== "string") {
    throw new Error(`Expected menu.yml key "${key}" to be a string`);
  }

  const trimmed = value.trim();

  if (trimmed.length === 0) {
    throw new Error(`Expected menu.yml key "${key}" to be non-empty`);
  }

  return trimmed;
}

function readOptionalString(value: unknown, key: string): string | null {
  if (value == null) {
    return null;
  }

  return requireString(value, key);
}

function parseArgs(argv: string[]): ParsedArgs {
  let configPath = defaultConfigPath;
  let targetPath = defaultTargetPath;
  let htmlSourcePath = defaultHtmlSourcePath;
  let htmlTargetPath = defaultHtmlTargetPath;

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const nextArg = argv[index + 1];

    if (arg === "--config") {
      if (!nextArg) {
        throw new Error("Missing value for --config");
      }

      configPath = resolve(process.cwd(), nextArg);
      index += 1;
      continue;
    }

    if (arg === "--target") {
      if (!nextArg) {
        throw new Error("Missing value for --target");
      }

      targetPath = resolve(process.cwd(), nextArg);
      index += 1;
      continue;
    }

    if (arg === "--html-source") {
      if (!nextArg) {
        throw new Error("Missing value for --html-source");
      }

      htmlSourcePath = resolve(process.cwd(), nextArg);
      index += 1;
      continue;
    }

    if (arg === "--html-target") {
      if (!nextArg) {
        throw new Error("Missing value for --html-target");
      }

      htmlTargetPath = resolve(process.cwd(), nextArg);
      index += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return {
    configPath,
    targetPath,
    htmlSourcePath,
    htmlTargetPath,
  };
}

async function loadMenuConfig(configPath: string): Promise<MenuConfig> {
  const rawContents = await Bun.file(configPath).text();
  const loaded = yaml.load(rawContents);

  if (loaded == null || typeof loaded !== "object" || Array.isArray(loaded)) {
    throw new Error(`Expected ${configPath} to contain a YAML object`);
  }

  const config = loaded as RawMenuConfig;

  return {
    title: requireString(config.title, "title"),
    quickStartVideo: requireString(
      config["quick-start-video"],
      "quick-start-video",
    ),
    support: requireString(config.support, "support"),
    gtag: readOptionalString(config.gtag, "gtag"),
    canonical: readOptionalString(config.canonical, "canonical"),
  };
}

function createPatchBlock(config: MenuConfig, newline: string): string {
  const configLiteral = JSON.stringify({
    title: config.title,
    quickStartVideo: config.quickStartVideo,
    support: config.support,
  });

  return [
    `  ${PATCH_START}`,
    `  var __rdfexportMenuConfig = ${configLiteral};`,
    "  var __rdfexportOpenConfiguredLink = function(url) {",
    '    if (typeof editorUi.openLink === "function") {',
    "      editorUi.openLink(url);",
    '    } else if (typeof window !== "undefined" && typeof window.open === "function") {',
    "      window.open(url);",
    "    }",
    "  };",
    '  if (editorUi != null && editorUi.actions != null && typeof editorUi.actions.get === "function") {',
    '    var __rdfexportAboutAction = editorUi.actions.get("about");',
    '    if (__rdfexportAboutAction != null && typeof __rdfexportAboutAction.label === "string" && __rdfexportAboutAction.label.indexOf("draw.io ") !== 0) {',
    '      __rdfexportAboutAction.label = "draw.io " + __rdfexportAboutAction.label;',
    "    }",
    "  }",
    "  if (__rdfexportMenuConfig.title) {",
    "    if (editorUi != null && editorUi.editor != null) {",
    "      editorUi.editor.appName = __rdfexportMenuConfig.title;",
    "    }",
    '    if (typeof editorUi.updateDocumentTitle === "function") {',
    "      editorUi.updateDocumentTitle();",
    '    } else if (typeof document !== "undefined") {',
    "      document.title = __rdfexportMenuConfig.title;",
    "    }",
    "  }",
    '  if (__rdfexportMenuConfig.quickStartVideo && editorUi != null && editorUi.actions != null && typeof editorUi.actions.addAction === "function") {',
    '    editorUi.actions.addAction("quickStart...", function() {',
    "      __rdfexportOpenConfiguredLink(__rdfexportMenuConfig.quickStartVideo);",
    "    });",
    "  }",
    '  if (__rdfexportMenuConfig.support && editorUi != null && editorUi.actions != null && typeof editorUi.actions.addAction === "function") {',
    '    editorUi.actions.addAction("support...", function() {',
    "      __rdfexportOpenConfiguredLink(__rdfexportMenuConfig.support);",
    "    });",
    "  }",
    `  ${PATCH_END}`,
  ].join(newline);
}

function replaceExistingPatch(
  content: string,
  patchBlock: string,
): string | null {
  const hasStartMarker = content.includes(PATCH_START);
  const hasEndMarker = content.includes(PATCH_END);

  if (!hasStartMarker && !hasEndMarker) {
    return null;
  }

  if (!hasStartMarker || !hasEndMarker) {
    throw new Error("Found an incomplete existing menu patch block");
  }

  const patchPattern = new RegExp(
    `${escapeRegExp(PATCH_START)}[\\s\\S]*?${escapeRegExp(PATCH_END)}`,
  );

  if (!patchPattern.test(content)) {
    throw new Error("Unable to locate the existing menu patch block");
  }

  return content.replace(patchPattern, patchBlock.trim());
}

function injectNewPatch(content: string, patchBlock: string): string {
  const matches = [...content.matchAll(LOAD_PLUGIN_PATTERN)];

  if (matches.length !== 1) {
    throw new Error(
      `Expected exactly one Draw.loadPlugin bootstrap in target file, found ${matches.length}`,
    );
  }

  const match = matches[0];

  if (match == null || match.index == null) {
    throw new Error("Unable to determine Draw.loadPlugin insertion point");
  }

  const insertionIndex = match.index + match[0].length;

  return (
    content.slice(0, insertionIndex) +
    "\n" +
    patchBlock +
    content.slice(insertionIndex)
  );
}

function patchCopiedPlugin(content: string, config: MenuConfig): string {
  const newline = content.includes("\r\n") ? "\r\n" : "\n";
  const patchBlock = createPatchBlock(config, newline);

  return (
    replaceExistingPatch(content, patchBlock) ??
    injectNewPatch(content, patchBlock)
  );
}

function escapeHtmlAttribute(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll('"', "&quot;");
}

function escapeJsSingleQuotedString(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll("'", "\\'");
}

function createGoogleTagSnippet(gtag: string, newline: string): string {
  const escapedAttributeValue = escapeHtmlAttribute(gtag);
  const escapedJsValue = escapeJsSingleQuotedString(gtag);

  return [
    "<!-- Google tag (gtag.js) -->",
    `<script async src="https://www.googletagmanager.com/gtag/js?id=${escapedAttributeValue}"></script>`,
    "<script>",
    "  window.dataLayer = window.dataLayer || [];",
    "  function gtag(){dataLayer.push(arguments);}",
    "  gtag('js', new Date());",
    "",
    `  gtag('config', '${escapedJsValue}');`,
    "</script>",
  ].join(newline);
}

function stripExistingGoogleTag(content: string): string {
  const matches = [...content.matchAll(GOOGLE_TAG_PATTERN)];

  if (matches.length > 1) {
    throw new Error("Found multiple Google tag snippets in HTML target");
  }

  if (matches.length === 0) {
    return content;
  }

  const match = matches[0];

  if (match == null || match.index == null) {
    throw new Error("Unable to determine Google tag snippet location");
  }

  const start = match.index;
  let end = start + match[0].length;
  const after = content.slice(end);

  if (after.startsWith("\r\n")) {
    end += 2;
  } else if (after.startsWith("\n")) {
    end += 1;
  }

  return content.slice(0, start) + content.slice(end);
}

function replaceCanonicalTag(
  content: string,
  canonical: string | null,
): string {
  if (canonical == null) {
    return content;
  }

  const replacement = `<link rel="canonical" href="${escapeHtmlAttribute(canonical)}">`;

  if (CANONICAL_TAG_PATTERN.test(content)) {
    return content.replace(CANONICAL_TAG_PATTERN, replacement);
  }

  return content;
}

function patchHtmlHead(
  content: string,
  gtag: string | null,
  canonical: string | null,
): string {
  const newline = content.includes("\r\n") ? "\r\n" : "\n";
  let updated = stripExistingGoogleTag(content);
  updated = replaceCanonicalTag(updated, canonical);

  if (gtag == null) {
    return updated;
  }

  const matches = [...updated.matchAll(HEAD_TAG_PATTERN)];

  if (matches.length !== 1) {
    throw new Error(
      `Expected exactly one <head> tag in HTML target, found ${matches.length}`,
    );
  }

  const match = matches[0];

  if (match == null || match.index == null) {
    throw new Error("Unable to determine <head> insertion point");
  }

  const insertionIndex = match.index + match[0].length;
  const snippet = createGoogleTagSnippet(gtag, newline);

  return (
    updated.slice(0, insertionIndex) +
    newline +
    snippet +
    updated.slice(insertionIndex)
  );
}

async function patchFile(
  filePath: string,
  patcher: (content: string) => string,
): Promise<boolean> {
  const original = await Bun.file(filePath).text();
  const patched = patcher(original);

  if (patched === original) {
    return false;
  }

  await Bun.write(filePath, patched);
  return true;
}

function isEnoentError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error != null &&
    (error as { code?: unknown }).code === "ENOENT"
  );
}

async function readTextIfExists(filePath: string): Promise<string | null> {
  try {
    return await Bun.file(filePath).text();
  } catch (error: unknown) {
    if (isEnoentError(error)) {
      return null;
    }

    throw error;
  }
}

async function patchBlueprintToTarget(
  sourcePath: string,
  targetPath: string,
  patcher: (content: string) => string,
): Promise<boolean> {
  const source = await Bun.file(sourcePath).text();
  const patched = patcher(source);
  const currentTarget = await readTextIfExists(targetPath);

  if (currentTarget === patched) {
    return false;
  }

  await Bun.write(targetPath, patched);
  return true;
}

async function main(): Promise<void> {
  const { configPath, targetPath, htmlSourcePath, htmlTargetPath } = parseArgs(
    process.argv.slice(2),
  );
  const config = await loadMenuConfig(configPath);
  const changedPaths: string[] = [];

  if (
    await patchFile(targetPath, (content) => patchCopiedPlugin(content, config))
  ) {
    changedPaths.push(targetPath);
  }

  if (
    await patchBlueprintToTarget(htmlSourcePath, htmlTargetPath, (content) =>
      patchHtmlHead(content, config.gtag, config.canonical),
    )
  ) {
    changedPaths.push(htmlTargetPath);
  }

  if (changedPaths.length === 0) {
    console.log("No menu patch changes were needed");
    return;
  }

  console.log("Patched configured menu assets:");

  for (const changedPath of changedPaths) {
    console.log(changedPath);
  }
}

await main();
