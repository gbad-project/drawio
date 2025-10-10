# Pytest Dependency Bootstrap Fix

## Summary
- Added a pytest bootstrapper that decodes the vendored rdflib and pyparsing wheels so legacy parser tests run without manual setup.
- Updated regression coverage to remap expected graphs when metadata changes the minted base URI.
- Stored the required wheels under the Pyodide assets directory and ignored generated vendor artifacts.

## Testing
- `pytest`
