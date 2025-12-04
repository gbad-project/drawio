#!/bin/bash
PYTHONPATH=. uv run python aicode/python_core/scripts/regenerate_baselines.py --commit cf8f84bb84ff83843b6726ac96aff3a2055f4275 --max-commits 1 --force-overwrite --skip-tests
