#!/usr/bin/env bun

import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import * as yaml from "js-yaml";

interface RawMenuConfig {
  title?: unknown;
  "quick-start-video"?: unknown;
  support?: unknown;
}

interface MenuConfig {
  title: string;
  quickStartVideo: string;
  support: string;
}

const PATCH_START = "/* RDFEXPORT_MENU_PATCH_START */";
const PATCH_END = "/* RDFEXPORT_MENU_PATCH_END */";
const LOAD_PLUGIN_PATTERN = /Draw\.loadPlugin\(function\(editorUi\)\s*\{/g;

const scriptDir = dirname(fileURLToPath(import.meta.url));
const pluginRoot = resolve(scriptDir, "../../..");
const defaultConfigPath = resolve(pluginRoot, "menu.yml");
const defaultTargetPath = resolve(pluginRoot, "../rdfexport.js");

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

function parseArgs(argv: string[]): { configPath: string; targetPath: string } {
  let configPath = defaultConfigPath;
  let targetPath = defaultTargetPath;

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

    throw new Error(`Unknown argument: ${arg}`);
  }

  return { configPath, targetPath };
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
  };
}

function createPatchBlock(config: MenuConfig, newline: string): string {
  const configLiteral = JSON.stringify(config);

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

async function main(): Promise<void> {
  const { configPath, targetPath } = parseArgs(process.argv.slice(2));
  const config = await loadMenuConfig(configPath);
  const original = await Bun.file(targetPath).text();
  const patched = patchCopiedPlugin(original, config);

  if (patched === original) {
    console.log(`No menu patch changes were needed for ${targetPath}`);
    return;
  }

  await Bun.write(targetPath, patched);
  console.log(`Patched copied plugin menu in ${targetPath}`);
}

await main();
