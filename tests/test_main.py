from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import MagicMock, patch
import unittest
from datetime import datetime
from main import app
from utils import verify_user, verify_technician

# --- User Auth Tests ---

def test_register_user(client, mock_supabase):
    payload = {
        "email": "test@example.com",
        "password": "password123",
        "name": "Test User",
        "mob_no": "1234567890",
        "address": "123 Test St"
    }
    
    # Mocking supabase.auth.sign_up
    mock_auth_response = MagicMock()
    mock_auth_response.user.id = "user_uuid_123"
    mock_auth_response.session = "session_token_123"
    mock_supabase.auth.sign_up.return_value = mock_auth_response

    # Mocking userprofile upsert
    mock_profile_data = [{"id": "user_uuid_123", "name": "Test User"}]
    mock_supabase.table.return_value.upsert.return_value.execute.return_value.data = mock_profile_data

    response = client.post("/api/funcs/user.register", json=payload)
    
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["user"]["id"] == "user_uuid_123"

def test_login_user(client, mock_supabase):
    payload = {
        "email": "test@example.com",
        "password": "password123"
    }

    # Mocking supabase.auth.sign_in_with_password
    mock_auth_response = MagicMock()
    mock_auth_response.user.id = "user_uuid_123"
    mock_auth_response.session = "session_token_123"
    mock_supabase.auth.sign_in_with_password.return_value = mock_auth_response

    response = client.post("/api/funcs/user.login", json=payload)

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["user"]["id"] == "user_uuid_123"

# --- User Function Tests ---

def test_view_services(client, mock_supabase):
    mock_data = [{"id": 1, "name": "AC Repair", "price": 500}]
    mock_supabase.table.return_value.select.return_value.execute.return_value.data = mock_data
    
    response = client.post("/api/funcs/service.viewServices")
    assert response.status_code == 200
    assert response.json() == mock_data

def test_book_service(client, mock_supabase):
    user_id = str(uuid4())
    payload = {
        "service_id": 1,
        "user_id": user_id,
        "scheduled_at": "2023-01-01T10:00:00"
    }
    
    # Mocks for different tables
    mock_booking_table = MagicMock()
    mock_service_table = MagicMock()
    mock_tech_table = MagicMock()
    mock_assignment_table = MagicMock()
    mock_user_table = MagicMock()
    mock_default_table = MagicMock()

    def table_side_effect(name):
        if name == "bookings": return mock_booking_table
        if name == "service": return mock_service_table
        if name == "technician": return mock_tech_table
        if name == "assignment": return mock_assignment_table
        if name == "userprofile": return mock_user_table
        return mock_default_table

    # Temporarily set side_effect
    original_side_effect = mock_supabase.table.side_effect
    mock_supabase.table.side_effect = table_side_effect
    
    # Override Auth
    app.dependency_overrides[verify_user] = lambda: user_id

    try:
        # 1. Booking Insert
        mock_booking = {
            "id": 100, 
            "user_id": user_id, 
            "service_id": 1,
            "scheduled_at": "2023-01-01T10:00:00",
            "status": "pending"
        }
        mock_booking_table.insert.return_value.execute.return_value.data = [mock_booking]
        
        # 2. Service Select (for assignment)
        mock_service_table.select.return_value.eq.return_value.execute.return_value.data = [{"provider_role_id": "plumber"}]

        # 3. Technician Select
        tech_uuid = str(uuid4())
        mock_tech_table.select.return_value.eq.return_value.execute.return_value.data = [{"id": tech_uuid}]

        # 4. Assignment Insert
        mock_assignment = {"id": 200, "techie_id": tech_uuid, "service_id": 1}
        mock_assignment_table.insert.return_value.execute.return_value.data = [mock_assignment]

        # 5. Booking Update (status assigned)
        mock_booking_table.update.return_value.eq.return_value.execute.return_value.data = [{"id": 100, "status": "assigned", "assignment_id": 200}]
        
        with patch("smtplib.SMTP"): 
             response = client.post("/api/funcs/service.bookService", json=payload)

        assert response.status_code == 200
        res_json = response.json()
        
        assert res_json["booking"]["id"] == 100
        assert res_json["assignment"]["techie_id"] == tech_uuid

    finally:
        mock_supabase.table.side_effect = original_side_effect
        app.dependency_overrides = {}

def test_view_booked_services(client, mock_supabase):
    user_id = str(uuid4())
    payload = {"user_id": user_id}
    mock_data = [{"id": 100, "service": {"name": "AC Repair"}}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data
    
    app.dependency_overrides[verify_user] = lambda: user_id
    
    # Note: user_id in payload is technically ignored by endpoint now, it uses token
    response = client.post("/api/funcs/user.viewBookedServices", json={})
    
    app.dependency_overrides = {}
    
    assert response.status_code == 200
    assert response.json() == mock_data

def test_view_user(client, mock_supabase):
    user_id = str(uuid4())
    mock_data = [{"id": user_id, "name": "John Doe"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data

    app.dependency_overrides[verify_user] = lambda: user_id

    response = client.post("/api/funcs/user.viewUser", json={"user_id": user_id})
    app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == mock_data

def test_view_notifications(client, mock_supabase):
    user_id = str(uuid4())
    mock_data = [{"id": 1, "message": "Service Confirmed"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data

    app.dependency_overrides[verify_user] = lambda: user_id

    response = client.post("/api/funcs/notification.viewNotifications", json={"user_id": user_id})
    app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == mock_data

# --- Technician Function Tests ---

def test_register_technician(client, mock_supabase):
    payload = {
        "email": "tech@example.com",
        "password": "password123",
        "name": "Tech Guy",
        "phone": "9876543210",
        "provider_role_id": "plumber"
    }

    mock_auth_response = MagicMock()
    mock_auth_response.user.id = "tech_uuid_123"
    mock_auth_response.session = "session_token_tech"
    mock_supabase.auth.sign_up.return_value = mock_auth_response

    mock_tech_data = [{"id": "tech_uuid_123", "name": "Tech Guy"}]
    mock_supabase.table.return_value.upsert.return_value.execute.return_value.data = mock_tech_data

    response = client.post("/api/funcs/technician.register", json=payload)

    assert response.status_code == 200
    assert response.json()["technician"]["id"] == "tech_uuid_123"

def test_login_technician(client, mock_supabase):
    payload = {
        "email": "tech@example.com",
        "password": "password123"
    }

    mock_auth_response = MagicMock()
    mock_auth_response.user.id = "tech_uuid_123"
    mock_supabase.auth.sign_in_with_password.return_value = mock_auth_response

    # Mock verifying tech in db
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "tech_uuid_123"}]

    response = client.post("/api/funcs/technician.login", json=payload)
    assert response.status_code == 200

def test_view_assigned_services(client, mock_supabase):
    tech_uuid = str(uuid4())
    mock_data = [{"id": 50, "service": {"name": "AC Repair"}}]
    # Mocking chain: select(...).eq("techie_id", ...).execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data

    app.dependency_overrides[verify_technician] = lambda: tech_uuid

    response = client.post("/api/funcs/technician.viewAssignedBookings", json={})
    app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == mock_data

def test_update_status(client, mock_supabase):
    tech_uuid = str(uuid4())
    payload = {"assignment_id": 100, "status": "completed"}
    
    mock_assignment_table = MagicMock()
    mock_booking_table = MagicMock()
    mock_default = MagicMock()

    def side_effect(name):
        if name == "assignment": return mock_assignment_table
        if name == "bookings": return mock_booking_table
        return mock_default

    mock_supabase.table.side_effect = side_effect
    
    # 1. Verify Assignment Ownership
    mock_assignment_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": 100}]
    
    # 2. Update Status
    mock_booking_table.update.return_value.eq.return_value.execute.return_value.data = [{"id": 100, "status": "completed"}]

    app.dependency_overrides[verify_technician] = lambda: tech_uuid
    
    response = client.post("/api/funcs/service.updateStatus", json=payload)
    
    app.dependency_overrides = {}
    
    assert response.status_code == 200
    assert response.json()[0]["status"] == "completed"

