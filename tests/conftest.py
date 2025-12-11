import pytest
import sys
import os
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Ensure we can import from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Aggressively mock the 'db' module to prevent it from running create_client
# This bypasses the need for SUPABASE_URL/KEY environment variables during testing
mock_db_module = MagicMock()
mock_supabase_client = MagicMock()
mock_db_module.supabase = mock_supabase_client
sys.modules["db"] = mock_db_module

# Now import app (which converts 'from db import supabase' to using our mock)
from main import app

@pytest.fixture
def mock_supabase():
    return mock_supabase_client

@pytest.fixture
def client():
    return TestClient(app)
