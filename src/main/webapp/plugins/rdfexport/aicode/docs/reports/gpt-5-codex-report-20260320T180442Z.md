# Help Menu and Title Trace Report (2026-03-20T18:04:42Z)

## Summary
- Located the top menubar `Help` anchor creation path for the rendered `<a class="geItem">Help</a>`.
- Located the draw.io-specific Help popup definition that produces the `Search`, `Keyboard Shortcuts`, `Quick Start Video`, `Support`, and version rows shown in the supplied HTML.
- Located the generic popup renderer that emits the `mxPopupMenu` table, `mxPopupMenuItem` rows, and separator `<hr>` rows.
- Located the runtime browser-title path that turns the app name into `draw.io`, plus additional hardcoded `<title>draw.io</title>` occurrences used in generated HTML strings.
- Per request, no application code was changed. Only this report was added.

## Request Scope
- Identify where the rendered `Help` top-menu item is specified.
- Identify where the popup shown after clicking `Help` is specified.
- Identify where `draw.io` can be changed in the browser `<title>`.
- Record the investigation under `src/main/webapp/plugins/rdfexport/aicode/docs/reports`.

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

## Files Inspected
- `src/main/webapp/js/grapheditor/Menus.js`
- `src/main/webapp/js/diagramly/Menus.js`
- `src/main/webapp/mxgraph/src/util/mxPopupMenu.js`
- `src/main/webapp/js/diagramly/App.js`
- `src/main/webapp/js/diagramly/Editor.js`
- `src/main/webapp/js/diagramly/EditorUi.js`
- `src/main/webapp/resources/dia.txt`
- `src/main/webapp/index.html`
- `src/main/webapp/plugins/rdfexport/aicode/docs/reports/*`

## Conclusion
- The top-level `Help` anchor is created by the shared menubar implementation in `grapheditor/Menus.js`.
- The popup contents shown after clicking `Help` are defined by the draw.io-specific `diagramly/Menus.js` Help menu override.
- The popup HTML shape itself is rendered by the generic `mxPopupMenu` class.
- The main runtime browser title branding comes from `Editor.prototype.appName = 'draw.io'`, not from `index.html`.

## Testing
- Repository inspection only; no build or runtime tests were needed for this trace.
