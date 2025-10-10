    *,
    base_uri: str | None = None,
        fallback_base_uri = base_uri or prefix_iri or PREFIX_IRI

            individual_uri = URIRef(f"{fallback_base_uri}{individual_id}")
                        target_uri = URIRef(f"{fallback_base_uri}{value}")
        base_uri=base_uri,
