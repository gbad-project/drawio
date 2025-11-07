import pytest
from rmlmapper_workflows import RMLMapperEnvironment


@pytest.fixture(scope="session")
def rmlmapper_env() -> RMLMapperEnvironment:
    return RMLMapperEnvironment.from_manifest()
