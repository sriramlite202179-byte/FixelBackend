from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import MagicMock, patch
import unittest
from datetime import datetime


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
    assert res_json["session"] == "session_token_123"
    assert res_json["profile"]["name"] == "Test User"

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
    assert res_json["session"] == "session_token_123"

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
    
    # Default mocks for other tables if needed
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
        mock_tech_table.select.return_value.eq.return_value.execute.return_value.data = [{"id": 55}]

        # 4. User Select (email)
        mock_user_table.select.return_value.eq.return_value.execute.return_value.data = [{"email": "test@example.com"}]

        # 5. Assignment Insert
        mock_assignment = {"id": 200, "tech_id": 55, "service_id": 1}
        mock_assignment_table.insert.return_value.execute.return_value.data = [mock_assignment]

        # 6. Booking Update (status assigned)
        mock_booking_table.update.return_value.eq.return_value.execute.return_value.data = [{"id": 100, "status": "assigned", "assignment_id": 200}]
        
        
        with patch("smtplib.SMTP") as mock_smtp: # Block actual network Calls
             response = client.post("/api/funcs/service.bookService", json=payload)

        assert response.status_code == 200
        res_json = response.json()
        
        # Verify Booking
        assert res_json["booking"]["id"] == 100
        
        # Verify Assignment
        assert res_json["assignment"]["id"] == 200
        assert res_json["assignment"]["tech_id"] == 55

    finally:
        # Restore side_effect to avoid breaking other tests
        mock_supabase.table.side_effect = original_side_effect

def test_view_booked_services(client, mock_supabase):
    user_id = str(uuid4())
    payload = {"user_id": user_id}
    mock_data = [{"id": 100, "service": {"name": "AC Repair"}}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data
    
    response = client.post("/api/funcs/user.viewBookedServices", json=payload)
    assert response.status_code == 200
    assert response.json() == mock_data

def test_view_user(client, mock_supabase):
    user_id = str(uuid4())
    payload = {"user_id": user_id}
    mock_data = [{"id": user_id, "name": "John Doe"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data

    response = client.post("/api/funcs/user.viewUser", json=payload)
    assert response.status_code == 200
    assert response.json() == mock_data

def test_view_notifications(client, mock_supabase):
    user_id = str(uuid4())
    payload = {"user_id": user_id}
    mock_data = [{"id": 1, "message": "Service Confirmed"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data

    response = client.post("/api/funcs/notification.viewNotifications", json=payload)
    assert response.status_code == 200
    assert response.json() == mock_data

# --- Technician Function Tests ---

def test_view_assigned_services(client, mock_supabase):
    payload = {"tech_id": 1}
    mock_data = [{"id": 50, "service": {"name": "AC Repair"}}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data

    response = client.post("/api/funcs/technician.viewAssignedServices", json=payload)
    assert response.status_code == 200
    assert response.json() == mock_data

def test_update_status(client, mock_supabase):
    payload = {"assignment_id": 100, "status": "completed"}
    mock_data = [{"id": 100, "status": "completed"}] # Mock successful update
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = mock_data
    
    response = client.post("/api/funcs/service.updateStatus", json=payload)
    assert response.status_code == 200
    assert response.json() == mock_data

# --- Admin Tests (Sample) ---
def test_admin_create_service(client, mock_supabase):
    payload = {
        "name": "New Service",
        "price": 999,
        "description": "Test Service",
        "id": 1, # Passed but should be excluded in logic
        "created_at": "2023-01-01T00:00:00"
    }
    mock_data = [{"id": 5, "name": "New Service"}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = mock_data

    response = client.post("/api/funcs/admin.service.create", json=payload)
    assert response.status_code == 200
    assert response.json() == mock_data
