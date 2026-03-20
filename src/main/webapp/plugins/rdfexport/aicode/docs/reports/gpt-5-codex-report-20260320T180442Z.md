# Help Menu and Title Trace Report (2026-03-20T18:04:42Z)

## Summary
- Located the top menubar `Help` anchor creation path for the rendered `<a class="geItem">Help</a>`.
- Located the draw.io-specific Help popup definition that produces the `Search`, `Keyboard Shortcuts`, `Quick Start Video`, `Support`, and version rows shown in the supplied HTML.
- Located the generic popup renderer that emits the `mxPopupMenu` table, `mxPopupMenuItem` rows, and separator `<hr>` rows.
- Located the runtime browser-title path that turns the app name into `draw.io`, plus additional hardcoded `<title>draw.io</title>` occurrences used in generated HTML strings.
- Implemented a Bun-based post-copy patch script at `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts` that reads `menu.yml` and injects only a marked block into the copied `src/main/webapp/plugins/rdfexport.js`.
- Confirmed the current build wiring now uses `build:script:patch` after the normal TypeScript bundle copy step, and the package also contains targeted script-specific `format`, `lint`, and `check` commands plus a dedicated `tsconfig.patchCopiedPluginMenu.json`.
- Documented the validation work, including a temporary-file patch test, the accidental `bun --check` execution against the live copied artifact, the subsequent rollback performed by the user, and the actual TypeScript nullability fix required for the script.

## Request Scope
- Identify where the rendered `Help` top-menu item is specified.
- Identify where the popup shown after clicking `Help` is specified.
- Identify where `draw.io` can be changed in the browser `<title>`.
- Record the investigation under `src/main/webapp/plugins/rdfexport/aicode/docs/reports`.
- Follow up by implementing a post-copy patcher that reads `src/main/webapp/plugins/rdfexport/menu.yml` and injects only the required title/help-menu overrides into the copied plugin artifact.
- Follow up again by validating the patcher with Bun-based checks and reflecting the final package-command layout in this report.

## Investigation Log
- Inspected the existing report directory first to match naming and formatting conventions already used in this repository.
- Searched the webapp sources for `geItem`, `Help`, `Keyboard Shortcuts`, `Quick Start Video`, `Support`, `mxPopupMenu`, `<title>`, `document.title`, and `draw.io`.
- Narrowed the search to these source areas:
  - `src/main/webapp/js/grapheditor/Menus.js`
  - `src/main/webapp/js/diagramly/Menus.js`
  - `src/main/webapp/mxgraph/src/util/mxPopupMenu.js`
  - `src/main/webapp/js/diagramly/App.js`
  - `src/main/webapp/js/diagramly/Editor.js`
  - `src/main/webapp/js/diagramly/EditorUi.js`
  - `src/main/webapp/resources/dia.txt`
  - `src/main/webapp/index.html`
- Initial read-only shell commands were blocked by the local sandbox with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`, so repository inspection was rerun with elevated access.
- For the implementation follow-up, additionally inspected:
  - `src/main/webapp/plugins/rdfexport/package.json`
  - `src/main/webapp/plugins/rdfexport/menu.yml`
  - `src/main/webapp/plugins/rdfexport.js`
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/build.ts`
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts`
  - `src/main/webapp/plugins/rdfexport/tsconfig.patchCopiedPluginMenu.json`
  - `src/main/webapp/plugins/rdfexport/eslint.config.js`
  - `src/main/webapp/js/grapheditor/Actions.js`

## Findings

### 1. Where `<a class="geItem">Help</a>` comes from
- The top menubar order is defined in `src/main/webapp/js/grapheditor/Menus.js:33`:
  - `Menus.prototype.defaultMenuItems = ['file', 'edit', 'view', 'arrange', 'extras', 'help'];`
- The menubar is populated in `src/main/webapp/js/grapheditor/Menus.js:1795-1814`.
  - That code iterates `defaultMenuItems`.
  - For each menu id, it calls `menubar.addMenu(mxResources.get(menus[i]), ...)`.
- The exact DOM creation point for the clickable anchor is `src/main/webapp/js/grapheditor/Menus.js:1873-1889`.
  - `var elt = document.createElement('a');`
  - `elt.className = 'geItem';`
  - `mxUtils.write(elt, label);`
- The displayed text `Help` comes from the resource bundle via `mxResources.get('help')`.
- The English resource value is defined in `src/main/webapp/resources/dia.txt:395`:
  - `help=Help`

### 2. Where the Help popup contents are defined
- The draw.io application overrides the base Help menu in `src/main/webapp/js/diagramly/Menus.js:1447-1553`.
- This is the section that matches the popup structure shown in the user-provided HTML.

#### Search row
- The first row is created in `src/main/webapp/js/diagramly/Menus.js:1455-1488`.
- The label text is hardcoded there:
  - `menu.addItem('Search:', null, null, parent, null, null, false);`
- The text input is then created and appended into that row:
  - `document.createElement('input')`
  - `type='text'`
  - `size='25'`
  - `marginLeft='8px'`
- Pressing Enter opens:
  - `https://www.drawio.com/search?...`
- Pressing Escape clears the field.

#### Non-Electron web popup item order
- For the normal web build, the item order is assembled in `src/main/webapp/js/diagramly/Menus.js:1551-1552`:
  - `keyboardShortcuts`
  - `quickStart`
  - `support`
  - separator
  - `about`
- That directly matches the popup shape the user supplied:
  - `Keyboard Shortcuts...`
  - `Quick Start Video...`
  - `Support...`
  - separator
  - `v24.7.5` style version row

#### Action definitions for those rows
- `about` version row:
  - `src/main/webapp/js/diagramly/Menus.js:794-797`
  - Label is dynamic: `'v' + EditorUi.VERSION`
- `support...`:
  - `src/main/webapp/js/diagramly/Menus.js:799-809`
  - Opens GitHub support wiki
- `keyboardShortcuts...`:
  - `src/main/webapp/js/diagramly/Menus.js:817-827`
  - Opens `shortcuts.svg` or the hosted viewer fallback
- `quickStart...`:
  - `src/main/webapp/js/diagramly/Menus.js:836-846`
  - Opens a YouTube quick-start video

#### Resource-backed labels used by the popup
- `src/main/webapp/resources/dia.txt:448`
  - `keyboardShortcuts=Keyboard Shortcuts`
- `src/main/webapp/resources/dia.txt:628`
  - `quickStart=Quick Start Video`
- `src/main/webapp/resources/dia.txt:758`
  - `support=Support`

### 3. Where the `mxPopupMenu` HTML is rendered
- The popup contents in `diagramly/Menus.js` do not directly hardcode the full `<table>` HTML shown by the browser.
- The generic popup DOM structure is rendered by `src/main/webapp/mxgraph/src/util/mxPopupMenu.js`.

#### Popup container and table
- `src/main/webapp/mxgraph/src/util/mxPopupMenu.js:119-137`
  - creates `this.table = document.createElement('table')`
  - assigns `this.table.className = 'mxPopupMenu'`
  - creates `this.tbody = document.createElement('tbody')`
  - creates `this.div = document.createElement('div')`
  - assigns `this.div.className = 'mxPopupMenu'`

#### Popup item rows
- `src/main/webapp/mxgraph/src/util/mxPopupMenu.js:197-259`
  - creates `tr.className = 'mxPopupMenuItem'`
  - creates `td` cells with classes `mxPopupMenuIcon` and `mxPopupMenuItem`
  - writes the visible item label text into the second cell

#### Separator rows
- `src/main/webapp/mxgraph/src/util/mxPopupMenu.js:464-485`
  - creates the separator `<tr>`
  - adds the icon spacer cell
  - creates the spanning content cell used for the `<hr>` row visible in the popup

### 4. Where to change `draw.io` in the browser title

#### Main app HTML seed title
- The main app entry page is `src/main/webapp/index.html`.
- Its static HTML title is not `draw.io`.
- The initial title there is at `src/main/webapp/index.html:5`:
  - `<title>Flowchart Maker &amp; Online Diagram Software</title>`

#### Runtime title logic actually used by the app
- The active browser-tab title is updated at runtime by `src/main/webapp/js/diagramly/App.js:2436-2460`.
- That function:
  - starts from `this.editor.appName`
  - may prefix the current filename
  - may append ` app` in offline mode
  - finally writes `document.title = title`
- The default app name is hardcoded in `src/main/webapp/js/diagramly/Editor.js:2558`:
  - `Editor.prototype.appName = 'draw.io';`

#### Practical effect
- No open file:
  - title resolves to `draw.io`
- Open file:
  - title resolves to `<filename> - draw.io`
- Offline app:
  - title resolves to `<filename> - draw.io app`

#### Additional literal `<title>draw.io</title>` occurrences
- There are also two hardcoded generated HTML strings in `src/main/webapp/js/diagramly/EditorUi.js`:
  - `src/main/webapp/js/diagramly/EditorUi.js:2032`
  - `src/main/webapp/js/diagramly/EditorUi.js:2071`
- In both places, the fallback generated title is:
  - `<title>draw.io</title>`
- These appear to be for generated/redirected HTML payloads, not the main live editor tab.

## Recommended Edit Points
- To change the top-level menubar label text `Help`:
  - start with `src/main/webapp/resources/dia.txt:395`
  - also update localized `dia_*.txt` files if multilingual consistency matters
- To change the popup items shown under `Help`:
  - edit `src/main/webapp/js/diagramly/Menus.js:1447-1553`
- To change what each Help popup item does:
  - edit the action handlers in `src/main/webapp/js/diagramly/Menus.js:794-846`
- To change the app/browser title brand from `draw.io` to something else:
  - edit `src/main/webapp/js/diagramly/Editor.js:2558`
- To change literal generated `<title>draw.io</title>` fallbacks:
  - edit `src/main/webapp/js/diagramly/EditorUi.js:2032`
  - edit `src/main/webapp/js/diagramly/EditorUi.js:2071`

## Follow-Up Implementation

### Goal
- The follow-up implementation work was to avoid editing draw.io core sources directly and instead patch the copied plugin artifact after `dist/rdfexport.js` is copied up one level for serving.
- The source of truth for the injected values is `src/main/webapp/plugins/rdfexport/menu.yml`.
- The specific runtime behaviors targeted by the follow-up were:
  - the browser title/app name
  - the `quickStart...` Help action URL
  - the `support...` Help action URL

### Final Patch Script
- The current patcher is `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts`.
- Path and argument handling:
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:24-27`
  - Defaults to `menu.yml` inside the plugin root and `../rdfexport.js` as the copied target
  - Supports `--config` and `--target` overrides for validation against alternate files
- YAML loading and validation:
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:33-99`
  - Enforces non-empty string values for:
    - `title`
    - `quick-start-video`
    - `support`
- Injected runtime behavior:
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:101-135`
  - Builds one marked block between:
    - `/* RDFEXPORT_MENU_PATCH_START */`
    - `/* RDFEXPORT_MENU_PATCH_END */`
  - The injected block:
    - sets `editorUi.editor.appName`
    - calls `editorUi.updateDocumentTitle()` when available
    - overrides `quickStart...` through `editorUi.actions.addAction(...)`
    - overrides `support...` through `editorUi.actions.addAction(...)`
- Surgical patching behavior:
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:138-196`
  - If the marker block already exists, only that exact block is replaced
  - If it does not exist, the script injects immediately after the single `Draw.loadPlugin(function(editorUi) {` bootstrap match
  - The script throws if the bootstrap match is missing or ambiguous, rather than editing broadly
- Main execution path:
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:199-214`
  - Reads config, patches the target content, writes only when the resulting content differs

### Current Package Wiring
- The current package wiring is now:
  - `src/main/webapp/plugins/rdfexport/package.json:31-33`
  - `build:ts` still builds and copies the bundle
  - `build:script:patch` runs the patcher explicitly against `../rdfexport.js`
  - `build` now chains `build:py`, `build:ts`, and `build:script:patch`
- The current script-specific developer commands are:
  - `src/main/webapp/plugins/rdfexport/package.json:59`
    - `format:script:patch`
  - `src/main/webapp/plugins/rdfexport/package.json:66`
    - `lint:script:patch`
  - `src/main/webapp/plugins/rdfexport/package.json:71`
    - `check:script:patch`
- The current targeted typecheck command uses:
  - `src/main/webapp/plugins/rdfexport/package.json:66`
  - `bun x tsc --noEmit -p tsconfig.patchCopiedPluginMenu.json`
- The dedicated script-only TypeScript project is:
  - `src/main/webapp/plugins/rdfexport/tsconfig.patchCopiedPluginMenu.json:1-4`
  - It extends the main plugin `tsconfig.json`
  - It includes only `./aicode/integration/scripts/patchCopiedPluginMenu.ts`

### Validation Timeline
- A temporary copy of the copied plugin was created at `/tmp/rdfexport-menu-test.js` for safe validation.
- The patcher was run against the temporary file and successfully inserted one marked block containing only the three `menu.yml`-driven values.
- The same patcher was then rerun against that same temporary file and reported no changes needed, confirming idempotent replacement behavior.
- The new script was formatted with Prettier.
- An attempt to use `bun --check aicode/integration/scripts/patchCopiedPluginMenu.ts` for typechecking was misleading:
  - it executed the script entrypoint instead of acting as a safe standalone compiler pass
  - this caused the live copied `src/main/webapp/plugins/rdfexport.js` to be patched unintentionally during validation
  - the user later rolled that accidental artifact change back manually
- After that, the actual targeted compiler pass used for the script was:
  - `bun x tsc --noEmit --pretty false --target ESNext --module Preserve --moduleResolution bundler --allowImportingTsExtensions true --verbatimModuleSyntax true --strict --skipLibCheck --noFallthroughCasesInSwitch true --noUncheckedIndexedAccess true --noImplicitOverride true aicode/integration/scripts/patchCopiedPluginMenu.ts`
- That compiler pass surfaced real script-local errors:
  - `patchCopiedPluginMenu.ts(175,7): error TS18048: 'match' is possibly 'undefined'`
  - `patchCopiedPluginMenu.ts(179,26): error TS18048: 'match' is possibly 'undefined'`
  - `patchCopiedPluginMenu.ts(179,40): error TS18048: 'match' is possibly 'undefined'`
- Those errors were fixed by explicitly narrowing the `matchAll` result before using `match.index`:
  - `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:173-179`
- The targeted compiler pass was rerun after the fix and completed cleanly.
- A full project-level `bun x tsc --noEmit --pretty false -p tsconfig.json` was also run.
  - That project-wide pass still reports unrelated pre-existing errors elsewhere in the repository
  - those errors were not caused by the new patch script
  - this is why the current package uses a script-only `tsconfig.patchCopiedPluginMenu.json` for targeted validation

### Linting Note
- The plugin’s ESLint flat config currently does not provide actual TypeScript-aware linting for this standalone `.ts` integration script:
  - `src/main/webapp/plugins/rdfexport/eslint.config.js`
- A direct `bun x eslint aicode/integration/scripts/patchCopiedPluginMenu.ts` reported that the file had no matching configuration.
- In practice, the current `lint:script:patch` command is compiler-backed and uses `tsc` via the dedicated script tsconfig.
- This means the current targeted workflow is:
  - format with Prettier
  - validate with script-only `tsc`
  - use `check:script:patch` as the combined targeted verification entrypoint

## Files Inspected
- `src/main/webapp/js/grapheditor/Menus.js`
- `src/main/webapp/js/diagramly/Menus.js`
- `src/main/webapp/mxgraph/src/util/mxPopupMenu.js`
- `src/main/webapp/js/diagramly/App.js`
- `src/main/webapp/js/diagramly/Editor.js`
- `src/main/webapp/js/diagramly/EditorUi.js`
- `src/main/webapp/resources/dia.txt`
- `src/main/webapp/index.html`
- `src/main/webapp/teams.html`
- `src/main/webapp/plugins/rdfexport/package.json`
- `src/main/webapp/plugins/rdfexport/menu.yml`
- `src/main/webapp/plugins/rdfexport.js`
- `src/main/webapp/plugins/rdfexport/assets/index.html`
- `src/main/webapp/plugins/rdfexport/tsconfig.patchCopiedPluginMenu.json`
- `src/main/webapp/plugins/rdfexport/eslint.config.js`
- `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/build.ts`
- `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts`
- `src/main/webapp/plugins/rdfexport/aicode/docs/reports/*`

## Conclusion
- The top-level `Help` anchor is created by the shared menubar implementation in `grapheditor/Menus.js`.
- The popup contents shown after clicking `Help` are defined by the draw.io-specific `diagramly/Menus.js` Help menu override.
- The popup HTML shape itself is rendered by the generic `mxPopupMenu` class.
- The main runtime browser title branding comes from `Editor.prototype.appName = 'draw.io'`, not from `index.html`.
- The follow-up implementation now patches the copied plugin artifact rather than editing draw.io core sources directly.
- The current build/package wiring performs the patch as a post-copy step and exposes targeted developer commands for formatting and validating the patch script.

## Testing
- Temporary artifact validation:
  - copied `src/main/webapp/plugins/rdfexport.js` to `/tmp/rdfexport-menu-test.js`
  - ran the patch script against the temporary file
  - reran it to confirm idempotency
- Formatting:
  - `node_modules/.bin/prettier --write aicode/integration/scripts/patchCopiedPluginMenu.ts package.json`
- Targeted script typecheck:
  - `bun x tsc --noEmit --pretty false --target ESNext --module Preserve --moduleResolution bundler --allowImportingTsExtensions true --verbatimModuleSyntax true --strict --skipLibCheck --noFallthroughCasesInSwitch true --noUncheckedIndexedAccess true --noImplicitOverride true aicode/integration/scripts/patchCopiedPluginMenu.ts`
- Project-wide compiler check:
  - `bun x tsc --noEmit --pretty false -p tsconfig.json`
  - still reports unrelated pre-existing repository errors outside the new patch script

## Additional Follow-Up: Version Prefix and Google Tag Blueprint Patch

### Request Refinement
- The next round of work added two new requirements on top of the existing post-copy patcher:
  - preserve the existing Help-menu version item exactly as draw.io computes it, but prefix it with `draw.io `
  - inject the provided Google tag snippet immediately after `<head>`, with `{{ gtag }}` populated from `src/main/webapp/plugins/rdfexport/menu.yml`
- The version row in the rendered popup was traced back to the `about` action label in `src/main/webapp/js/diagramly/Menus.js:794-797`.
- The menu renderer uses the current action label at render time in `src/main/webapp/js/grapheditor/Menus.js:1450-1457`, so the safest non-core-source change was to adjust that existing action label inside the plugin patch block rather than replacing draw.io’s own version computation.
- The Google-tag requirement initially pointed at the live editor shell HTML.
- After clarifying scope, the final requirement became:
  - `src/main/webapp/plugins/rdfexport/assets/index.html` must remain the untouched static blueprint
  - the patcher should render from that blueprint and write the patched output to the real served `src/main/webapp/index.html`

### Final Script Behavior
- `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:22-41`
  - the argument model now includes:
    - `--config`
    - `--target` for the copied `rdfexport.js`
    - `--html-source` for the static HTML blueprint
    - `--html-target` for the served HTML output location
  - the defaults are now:
    - `menu.yml`
    - `../rdfexport.js`
    - `assets/index.html`
    - `../../index.html`
- `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:130-148`
  - `menu.yml` loading now also accepts an optional `gtag` key in addition to:
    - `title`
    - `quick-start-video`
    - `support`
- `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:151-195`
  - the injected runtime patch block still remains bounded by the existing marker comments
  - that block now also reads the live `about` action and prefixes its label with `draw.io ` only if it is not already prefixed
  - this preserves the original draw.io-managed version text, so `v24.7.5` becomes `draw.io v24.7.5` without hardcoding or recomputing the version
- `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:267-345`
  - the Google tag HTML generation uses the exact snippet body requested by the user
  - the patcher:
    - builds the snippet with the configured `gtag`
    - removes any existing matching Google tag block first
    - reinserts the configured snippet immediately after the single `<head>` tag
  - this keeps reruns idempotent and limits HTML edits to the intended snippet area
- `src/main/webapp/plugins/rdfexport/aicode/integration/scripts/patchCopiedPluginMenu.ts:362-417`
  - HTML handling now uses blueprint-to-target synchronization instead of in-place editing
  - the patcher reads `assets/index.html`, applies the Google tag transform to that source content, compares it with the current served `index.html`, and writes only when the rendered output differs
  - this satisfies the final requirement that the asset copy stays static while the served file is regenerated on demand

### Validation and Tooling Notes
- An attempt was made to use the existing package command exactly as written:
  - `bun run check:script:patch`
- That failed before running the real checks because the script chain resolves a local macOS-specific `node_modules/.bin/bun` binary in this environment:
  - `/usr/bin/bash: line 1: /Volumes/home/aicode/drawrdf/src/main/webapp/plugins/rdfexport/node_modules/.bin/bun: cannot execute binary file: Exec format error`
- After the user clarified that `package.json` is intentionally macOS-configured, the package scripts were left unchanged.
- The direct command equivalents were used instead, per user instruction:
  - `./node_modules/.bin/tsc --noEmit -p tsconfig.patchCopiedPluginMenu.json`
  - `./node_modules/.bin/prettier --write aicode/integration/scripts/patchCopiedPluginMenu.ts`
  - `./node_modules/.bin/tsc --noEmit -p tsconfig.patchCopiedPluginMenu.json`
- All three direct validation commands completed successfully.
- No production HTML or copied plugin artifact was patched during validation in this round.
  - only the patch script itself and this report were changed
  - the new blueprint-to-target behavior is implemented and ready for the normal patch flow to invoke later
