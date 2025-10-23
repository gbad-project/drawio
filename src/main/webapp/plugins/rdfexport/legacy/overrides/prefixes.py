from __future__ import annotations

import os

from legacy.draw_io_parser import *  # type: ignore=imported-unused
from meta_builder.drawio_meta_builder import override

# ruff: noqa: F403, F405


@override(phase="core", type="internal", role="data")
def get_prefixes() -> dict[str, str]:
    """Derive prefix mappings while preserving BASE_URI compatibility."""
    base_uri = os.getenv("BASE_URI", "https://data.archives.gov.on.test.gbad.ca")
    base_uri = base_uri.rstrip("/")

    return {
        "rico": "https://www.ica.org/standards/RiC/ontology#",
        "add": f"{base_uri}/Schema/Description-Listings/",
        "auth": f"{base_uri}/Schema/Authority/",
        "gbad": f"{base_uri}/Schema/",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
    }
