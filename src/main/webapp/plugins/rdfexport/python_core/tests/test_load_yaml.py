from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from python_core.src.overrides.pre.internal.metadata.load_yaml import _load_config_yml

PYODIDE_PATH = "/app/config/default.yml"
DRAW_IO_PARSER_FILENAME = "draw_io_parser.py"

# Fully qualified path for patching yaml.safe_load
YAML_PATCH_PATH = 'python_core.src.overrides.pre.internal.metadata.load_yaml.yaml.safe_load'

def test_load_default_yml():
    config, context = _load_config_yml()
    assert config
    assert context == "standalone"
    print(context, config)

# --- 2. Pyodide Context Test (Refactored) ---
@patch("builtins.open", new_callable=mock_open, read_data="key: mocked_value")
@patch(YAML_PATCH_PATH, return_value={'key': 'mocked_value'})
def test_load_config_pyodide(mock_safe_load, mock_file):
    # 1. Patch Path.resolve to intercept 'current_file' creation WITHOUT breaking Path class constants
    with patch("pathlib.Path.resolve") as mock_resolve:
        mock_current_path = MagicMock(spec=Path)
        mock_resolve.return_value = mock_current_path
        
        # Ensure is_relative_to("/app") returns True
        mock_current_path.is_relative_to.return_value = True

        # 2. Mock Path.exists globally. 
        #    In this flow, candidate_path is a REAL Path object (derived from unmocked Path("/app")),
        #    so we must patch the real Path.exists method to catch it.
        def exists_side_effect(self):
            return self.as_posix() == PYODIDE_PATH

        with patch.object(Path, 'exists', autospec=True, side_effect=exists_side_effect):
            config, context = _load_config_yml()
            assert context == "pyodide"
            assert config == {'key': 'mocked_value'}

# --- 3. Metabuilder Context Test (Refactored) ---
@patch("builtins.open", new_callable=mock_open, read_data="key: mocked_value")
@patch(YAML_PATCH_PATH, return_value={'key': 'mocked_value'})
def test_load_config_metabuilder(mock_safe_load, mock_file):
    # 1. Patch Path.resolve to intercept 'current_file'
    with patch("pathlib.Path.resolve") as mock_resolve:
        mock_current_path = MagicMock()
        mock_resolve.return_value = mock_current_path
        
        # Ensure is_relative_to("/app") returns False
        mock_current_path.is_relative_to.return_value = False
        # Set filename to trigger 'metabuilder' context
        mock_current_path.name = DRAW_IO_PARSER_FILENAME
    
        # 2. Setup mock parents for the search loop
        mock_parent = MagicMock()
        mock_current_path.parent = mock_parent
        mock_current_path.parents = [mock_parent]

        # 3. Handle path division chaining: parent / dir / filename
        #    Since 'parent' is a Mock, the division operations return Mocks.
        #    We capture the final resulting mock and force .exists() to True.
        mock_config_path = MagicMock()
        mock_config_path.exists.return_value = True
        
        # Chain: mock_parent / ... / ... -> mock_config_path
        mock_parent.__truediv__.return_value.__truediv__.return_value = mock_config_path

        config, context = _load_config_yml()
            
        assert context == "metabuilder"
        assert config == {'key': 'mocked_value'}
