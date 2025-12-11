from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import MagicMock
from datetime import datetime

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
    
    # Mock insert response for Booking
    mock_booking = {
        "id": 100, 
        "user_id": user_id, 
        "service_id": 1,
        "scheduled_at": "2023-01-01T10:00:00",
        "status": "pending",
        "assignment_id": None
    }
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [mock_booking]
    
    response = client.post("/api/funcs/service.bookService", json=payload)
    assert response.status_code == 200
    # Expected response structure from new logic: {"booking": ...}
    assert response.json() == {"booking": mock_booking}

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
