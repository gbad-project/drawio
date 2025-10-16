# Produce reliable, original draw io parser output artifacts
cd ../../../../.. && bash src/main/webapp/plugins/rdfexport/legacy/scripts/run_regeneration.sh
# Test draw io parser patches applied for rdfexport plugin integration
cd src/main/webapp/plugins/rdfexport && pytest legacy/tests/
