"""
Shared environment loading for Clinical Guidelines modules.

Consolidates the _load_env() function that was duplicated across
guidelines_vector_store.py, guidelines_graphiti_client.py,
guidelines_migrations.py, and graph_data_provider.py.
"""

import pathlib

from dotenv import load_dotenv


def load_guidelines_env():
    """Load .env from multiple possible locations.

    Searches in order:
    1. AppData / Application Support (platform data folder)
    2. Project root .env
    3. Current working directory .env
    4. Default dotenv search
    """
    paths = []
    try:
        from managers.data_folder_manager import data_folder_manager
        paths.append(data_folder_manager.env_file_path)
    except Exception:
        pass
    paths.extend([
        pathlib.Path(__file__).parent.parent.parent / '.env',
        pathlib.Path.cwd() / '.env',
    ])

    for p in paths:
        try:
            if p.exists():
                load_dotenv(dotenv_path=str(p))
                return
        except Exception:
            pass
    load_dotenv()
