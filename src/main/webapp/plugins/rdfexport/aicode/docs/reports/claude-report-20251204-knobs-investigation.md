# Claude Report: RDF Parser Knobs Implementation Investigation & Fixes
**Date:** 2025-12-04
**Session ID:** claude/review-rdf-export-reports-01S2GcjNx9hRsccRaeMim1gk
**Branch:** claude/review-rdf-export-reports-01S2GcjNx9hRsccRaeMim1gk (branched from claude/expose-rdf-parser-knobs-0153ih6xQhDjoPr61F5YTuhW)

## Executive Summary

This session investigated regression issues with the new RDF parser knobs implementation. The investigation revealed that the knobs were not properly propagating, and more fundamentally, that there was no single source of truth for default configuration values. The solution involved creating a centralized YAML configuration file and ensuring both TypeScript and Python read from it dynamically.

**Key Achievement:** Implemented `aicode/integration_tests/config/default.yml` as the single source of truth for all parser defaults, with both Python and TypeScript reading from it at runtime.

## Problem Statement

The new RDF parser knobs (mint_from_literals, mint_from_types, mint_from_arrows, literal_definitions) were causing test regressions. Baseline behavior at commit 5c6cb95 showed:
- **test.log:** 35 pass, 19 skip, 0 fail
- **debug.log:** 42 pass, 6 xfail
- **bun.log:** 35 pass, 19 skip
- **pytest.log:** ~93 pass, 2 xfail

Current state showed massive failures across all test suites, indicating the knobs were not propagating correctly.

## Investigation Findings

### 1. Initial Bug: Empty List Handling in `_style_denotes_literal()`

**File:** `aicode/python_core/src/overrides/core/xml/data/cell_classifier.py:721`

**Original Intent (CORRECT):**
```python
def _style_denotes_literal(self, cell: Element, style: str) -> bool:
    """
    - None: Use DEFAULT_LITERAL_DEFINITIONS
    - []: Return True (treat everything as literal - user's explicit choice)
    - [...]: Use provided definitions
    """
```

**My Initial (INCORRECT) Fix:**
I changed `[] → return False`, thinking empty list meant "no literal definitions". This was wrong!

**Correct Understanding:**
- `None`: Use the default from YAML (e.g., `rounded=1`)
- `[]`: User explicitly removed all definitions → treat EVERYTHING as literal
- `[{...}]`: Use the provided custom definitions

This semantic is important for UI flexibility - users can choose to disable literal detection entirely by providing an empty list.

### 2. Critical Architecture Problem: No Single Source of Truth

**Discovery:** Default values were hardcoded in three different places:
1. `drawio_pipeline.py`: `literal_definitions: None` (intended to default to `rounded=1`)
2. `cell_classifier.py`: `DEFAULT_LITERAL_DEFINITIONS = [{"key": "style", "value": "rounded=1"}]`
3. `rdfexport.ts`: `literalDefinitions: []` (empty!)

These inconsistencies caused:
- TypeScript UI showing different defaults than Python execution
- Test fixtures expecting one behavior, code delivering another
- strip_html defaulting to `true` in TS but `false` needed for tests

## Solution Implemented

### Architecture: Single YAML Source of Truth

Created `aicode/integration_tests/config/default.yml` with vetted defaults:

```yaml
parser_config:
  ontology_iri: null
  infer_type_of_literals: true
  include_preamble: true
  include_label: true
  max_gap: 10
  strict_mode: false
  strip_html: false              # Critical: was true in TS
  mint_from_literals: true
  mint_from_types: false
  mint_from_arrows: true
  metacharacter_substitute:
    - "url"
  literal_definitions:            # Critical: was empty in TS
    - attr_key: style
      attr_value: rounded=1
  capitalisation_scheme: upper-camel
  rml_enabled: null
```

### Python Implementation

**File:** `aicode/python_core/pyodide_pipeline/drawio_pipeline.py`
```python
import yaml

def _load_defaults_from_yaml() -> dict[str, Any]:
    """Load default parser configuration from default.yml."""
    config_path = Path(__file__).resolve().parents[2] / "integration_tests" / "config" / "default.yml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        return config.get('parser_config', {})

_YAML_DEFAULTS = _load_defaults_from_yaml()
DEFAULT_LITERAL_DEFINITIONS = [...]  # Converted from YAML format
```

**File:** `aicode/python_core/src/overrides/core/xml/data/cell_classifier.py`
```python
# Load at module import time
try:
    _config_path = Path(__file__).resolve().parents[5] / "integration_tests" / "config" / "default.yml"
    with open(_config_path, 'r') as _f:
        _config = yaml.safe_load(_f)
        _yaml_defs = _config.get('parser_config', {}).get('literal_definitions', [])
        _DEFAULT_LITERAL_DEFINITIONS = [
            {"key": item['attr_key'], "value": item['attr_value']}
            for item in _yaml_defs
        ]
except Exception:
    _DEFAULT_LITERAL_DEFINITIONS = [{"key": "style", "value": "rounded=1"}]

class DrawIOCellClassifier:
    DEFAULT_LITERAL_DEFINITIONS = _DEFAULT_LITERAL_DEFINITIONS
```

### TypeScript Implementation

**File:** `aicode/typescript_plugin/src/rdfexport.ts`

Added minimal YAML parser:
```typescript
function parseDefaultYaml(yamlText: string): any {
  // Parses YAML structure to extract parser_config values
  // Handles scalars (bool, number, null, string)
  // Handles arrays (simple strings and key/value objects)
}

import defaultConfigYamlRaw from "../../../aicode/integration_tests/config/default.yml?raw";
const YAML_DEFAULTS = parseDefaultYaml(defaultConfigYamlRaw).parser_config;

function createDefaultParserSettings(): ParserSettings {
  return {
    stripHtml: YAML_DEFAULTS.strip_html ?? false,
    literalDefinitions: (YAML_DEFAULTS.literal_definitions || []).map(...),
    // ... all other values read dynamically from YAML
  };
}
```

### Pyodide Integration

**File:** `aicode/typescript_plugin/src/pyodideRuntime.ts`

1. Added default.yml to virtual filesystem:
```typescript
import defaultConfigYaml from "../../../aicode/integration_tests/config/default.yml?raw";

const PYTHON_MODULES = [
  // ...
  {
    path: `${PYODIDE_APP_ROOT}/integration_tests/config/default.yml`,
    source: defaultConfigYaml,
  },
];
```

2. Added PyYAML wheel:
```typescript
import pyyamlWheelBase64 from "../../../.pyodide/wheels/PyYAML-6.0.2-py3-none-any.whl.base64?raw";

const PYTHON_WHEELS = [
  { path: `${PYODIDE_APP_ROOT}/wheels/rdflib-7.4.0-py3-none-any.whl`, ... },
  { path: `${PYODIDE_APP_ROOT}/wheels/PyYAML-6.0.2-py3-none-any.whl`, ... },
];
```

3. Updated bootstrap script to extract PyYAML:
```python
if importlib.util.find_spec("yaml") is None:
    import zipfile
    with zipfile.ZipFile("${PYODIDE_APP_ROOT}/wheels/PyYAML-6.0.2-py3-none-any.whl") as archive:
        archive.extractall(target)
```

**File:** `aicode/integration_tests/scripts/download_pyodide_assets.sh`

Added PyYAML download:
```bash
PYYAML_WHEEL_FILE="PyYAML-6.0.2-py3-none-any.whl"
PYYAML_WHEEL_URL="https://files.pythonhosted.org/packages/7d/39/..."
# Downloads and converts to base64
```

### Critical Fix: Pure Python Wheel

**Issue:** Initially used platform-specific PyYAML wheel:
```
PyYAML-6.0.3-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
```
This caused `BadZipFile: File is not a zip file` errors in Pyodide.

**Solution:** Use pure Python wheel:
```
PyYAML-6.0.2-py3-none-any.whl
```
Pure Python wheels work in WASM/Pyodide environment.

## Commits Made

### Commit 638f7ba: Initial Fix Attempt (PARTIALLY INCORRECT)
```
fix: correct literal_definitions empty list handling and default

- Fixed _style_denotes_literal() logic (BUT INCORRECTLY!)
- Changed default literal_definitions from None to []
```
**Status:** Reverted the _style_denotes_literal() change in next commit.

### Commit 5d05eea: YAML Configuration Implementation
```
feat: implement centralized default.yml configuration for RDF parser knobs

- Created aicode/integration_tests/config/default.yml
- Python reads from YAML (drawio_pipeline.py, cell_classifier.py)
- TypeScript hardcoded values matching YAML (WRONG APPROACH!)
- Fixed _style_denotes_literal() to correct logic ([] → True)
```
**Status:** Good architecture, but TypeScript not reading YAML dynamically.

### Commit ea43758: Fix TypeScript to Read YAML Dynamically
```
fix: make TypeScript actually read YAML dynamically + add PyYAML to Pyodide

- Added parseDefaultYaml() function for TypeScript
- TypeScript now reads from YAML at module load time
- Added PyYAML wheel to Pyodide
```
**Status:** Good, but wrong wheel format.

### Commit 67d16b1: Fix PyYAML Wheel for Pyodide
```
fix: use pure Python PyYAML wheel for Pyodide compatibility

- Changed from platform-specific to pure Python wheel
- PyYAML-6.0.2-py3-none-any.whl works in WASM/Pyodide
```
**Status:** Latest commit, addresses wheel compatibility.

## Current Test Status

**Status as of commit 67d16b1:**

Tests are still showing failures. The PyYAML integration appears to have resolved the `BadZipFile` error, but other test failures persist.

**Remaining Issues to Investigate:**
1. Test baseline expectations may need updating for new YAML defaults
2. Possible issues with how literal_definitions are being passed through the pipeline
3. stripHtml default change from `true` to `false` may affect baselines
4. Need to verify the full propagation chain:
   - YAML → TypeScript UI → Pyodide → Python parser → Graph output

## Files Modified

### Configuration
- `aicode/integration_tests/config/default.yml` (NEW)
- `aicode/integration_tests/scripts/download_pyodide_assets.sh`

### Python
- `aicode/python_core/pyodide_pipeline/drawio_pipeline.py`
- `aicode/python_core/src/overrides/core/xml/data/cell_classifier.py`
- `python_core/src/draw_io_parser.py` (regenerated)

### TypeScript
- `aicode/typescript_plugin/src/rdfexport.ts`
- `aicode/typescript_plugin/src/pyodideRuntime.ts`
- `rdfexport.js` (rebuilt)

## Lessons Learned

1. **Single Source of Truth is Critical:** Having defaults scattered across files leads to inconsistencies and bugs.

2. **Semantic Intent Matters:** The `[] → everything is literal` semantic is important for UI flexibility, even if counterintuitive at first.

3. **Pyodide Wheel Compatibility:** Pyodide requires pure Python wheels (py3-none-any) or Emscripten-built wheels. Platform-specific wheels (manylinux, win32, etc.) don't work.

4. **Test Baselines:** When changing defaults, all test baselines need review and potential regeneration.

5. **Format Conversions:** The chain YAML (attr_key/attr_value) → TypeScript (attrKey/attrVal) → Python (key/value) needs careful handling.

## Next Steps

1. **Run Full Test Suite:** Execute all 4 test logs to get complete picture
2. **Analyze Specific Failures:** Identify patterns in failing tests
3. **Update Baselines if Needed:** If new defaults are correct, update test expectations
4. **Verify Propagation Chain:** Add debug logging to trace values through entire pipeline
5. **Consider Test Migration:** Some tests may need adjusting for the new architecture

## Recommendations

1. **Keep YAML as Single Source:** Don't add any more hardcoded defaults
2. **Add Validation:** Consider adding YAML schema validation on load
3. **Document Format:** Add comments in default.yml explaining each setting
4. **Consider Dynamic Reload:** Future enhancement could reload YAML without restart
5. **Test Coverage:** Add specific tests for YAML loading and parsing

## References

- Baseline commit: `5c6cb95` ("test all pass/xfail")
- Source branch: `claude/expose-rdf-parser-knobs-0153ih6xQhDjoPr61F5YTuhW`
- Working branch: `claude/review-rdf-export-reports-01S2GcjNx9hRsccRaeMim1gk`
- Previous reports:
  - `claude-report-20251204-update.md`
  - `claude-report-20251203-182603.md`
