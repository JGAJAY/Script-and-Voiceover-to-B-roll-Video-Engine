import os
import sys
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure test environment
os.environ["APP_ENV"] = "test"
os.environ["STORAGE_DIR"] = str(Path(__file__).parent / "test_storage")
os.environ["ENABLE_MOCK_SOURCES"] = "true"

from src.config import settings
from src.main import app

@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown_test_env():
    test_storage = Path(settings.STORAGE_DIR)
    test_storage.mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup test storage
    if test_storage.exists():
        try:
            shutil.rmtree(test_storage)
        except Exception:
            pass

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
