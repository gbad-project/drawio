import pytest
from aicode.integration_tests.rmlmapper_workflows.src import RMLMapperEnvironment


@pytest.fixture(scope="session")
def rmlmapper_env() -> RMLMapperEnvironment:
    return RMLMapperEnvironment.from_manifest()
