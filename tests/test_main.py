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
    mock_assignment_request_table = MagicMock()
    mock_user_table = MagicMock()
    mock_default_table = MagicMock()

    def table_side_effect(name):
        if name == "bookings": return mock_booking_table
        if name == "service": return mock_service_table
        if name == "technician": return mock_tech_table
        if name == "assignment_request": return mock_assignment_request_table
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
        
        # 3b. History check (empty)
        mock_assignment_request_table.select.return_value.eq.return_value.execute.return_value.data = []

        # 4. Assignment Request Insert
        mock_request = {"id": 500, "techie_id": tech_uuid, "booking_id": 100, "status": "pending"}
        mock_assignment_request_table.insert.return_value.execute.return_value.data = [mock_request]

        # 5. Booking Update (status assigned)
        mock_booking_table.update.return_value.eq.return_value.execute.return_value.data = [{"id": 100, "status": "assigned"}]
        
        with patch("smtplib.SMTP"): 
             response = client.post("/api/funcs/service.bookService", json=payload)

        assert response.status_code == 200
        res_json = response.json()
        
        assert res_json["booking"]["id"] == 100
        assert res_json["assignment"]["techie_id"] == tech_uuid  # This now refers to the request object returned by assign_technician

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
    # Mocking chain: select(...).eq("techie_id", ...).neq("status", "completed").neq("status", "cancelled").execute()
    mock_select = mock_supabase.table.return_value.select.return_value
    mock_eq_tech = mock_select.eq.return_value
    mock_neq_completed = mock_eq_tech.neq.return_value
    mock_neq_cancelled = mock_neq_completed.neq.return_value
    mock_neq_cancelled.execute.return_value.data = mock_data

    app.dependency_overrides[verify_technician] = lambda: tech_uuid

    response = client.post("/api/funcs/technician.viewAssignedBookings", json={})
    app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == mock_data
    
    # Verify chain calls (optional but good for regression)
    mock_select.eq.assert_called_with("techie_id", tech_uuid)
    mock_eq_tech.neq.assert_called_with("status", "completed")
    mock_neq_completed.neq.assert_called_with("status", "cancelled")

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
    
    # 2. Update Booking Status
    mock_booking_table.update.return_value.eq.return_value.execute.return_value.data = [{"id": 100, "status": "completed"}]

    # 3. Update Assignment Status
    mock_assignment_table.update.return_value.eq.return_value.execute.return_value.data = [{"id": 100, "status": "completed"}]

    app.dependency_overrides[verify_technician] = lambda: tech_uuid
    
    response = client.post("/api/funcs/service.updateStatus", json=payload)
    
    app.dependency_overrides = {}
    
    assert response.status_code == 200
    assert response.json()[0]["status"] == "completed"
    
    # Verify mapping calls
    mock_booking_table.update.assert_called_with({"status": "completed"})
    mock_assignment_table.update.assert_called_with({"status": "completed"})


def test_view_assignment_requests(client, mock_supabase):
    tech_uuid = str(uuid4())
    mock_data = [{"id": 1, "booking_id": 100, "status": "pending"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = mock_data
    
    app.dependency_overrides[verify_technician] = lambda: tech_uuid
    
    response = client.post("/api/funcs/technician.viewAssignmentRequests", json={})
    
    app.dependency_overrides = {}
    
    assert response.status_code == 200
    assert response.json() == mock_data

def test_accept_assignment(client, mock_supabase):
    tech_uuid = str(uuid4())
    payload = {"request_id": 1}
    
    # 1. Verify Request
    mock_request = {"id": 1, "booking_id": 100, "status": "pending", "techie_id": tech_uuid}
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_request]
    
    # 2. Get Booking
    mock_booking = {"id": 100, "status": "assigned", "service_id": 1, "scheduled_at": "2023-01-01"}
    # Note: mocking subsequent call. Supabase mock usage with chain is tricky if not careful with side_effect.
    # Let's assume the mock object returns a new mock on method call, so we inspect calls or set up side effect for different tables if needed.
    # But here we are using a simple mock that returns the SAME thing unless changed.
    # So we need side_effects or specialized mocks.
    
    mock_req_table = MagicMock()
    mock_book_table = MagicMock()
    mock_assign_table = MagicMock()
    mock_default = MagicMock()
    
    def side_effect(name):
        if name == "assignment_request": return mock_req_table
        if name == "bookings": return mock_book_table
        if name == "assignment": return mock_assign_table
        return mock_default

    mock_supabase.table.side_effect = side_effect
    
    mock_req_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_request]
    mock_book_table.select.return_value.eq.return_value.execute.return_value.data = [mock_booking]
    
    # 3. Insert Assignment
    mock_assignment = {"id": 55, "techie_id": tech_uuid, "booking_id": 100, "status": "active"}
    mock_assign_table.insert.return_value.execute.return_value.data = [mock_assignment]
    
    app.dependency_overrides[verify_technician] = lambda: tech_uuid
    
    response = client.post("/api/funcs/technician.acceptAssignment", json=payload)
    
    app.dependency_overrides = {}
    
    assert response.status_code == 200
    assert response.json()["assignment"]["id"] == 55
    # Check updates
    mock_req_table.update.assert_called_with({"status": "accepted"})
    mock_book_table.update.assert_called_with({"status": "confirmed", "assignment_id": 55})


def test_reject_assignment(client, mock_supabase):
    tech_uuid = str(uuid4())
    payload = {"request_id": 1}
    
    # Create specific mocks for each table
    mock_req_table = MagicMock()
    mock_book_table = MagicMock()
    mock_service_table = MagicMock()
    mock_tech_table = MagicMock()
    mock_default = MagicMock()
    
    # Define side effect to return these mocks
    def side_effect(name):
        if name == "assignment_request": return mock_req_table
        if name == "bookings": return mock_book_table
        if name == "service": return mock_service_table
        if name == "technician": return mock_tech_table
        return mock_default

    mock_supabase.table.side_effect = side_effect

    # 1. Verify Request logic
    # First call is to verify the request: select(...).eq(...).eq(...)
    mock_request = {"id": 1, "booking_id": 100, "status": "pending", "techie_id": tech_uuid}
    mock_req_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_request]
    
    # 2. Get Booking (inside reject_assignment)
    mock_booking = {"id": 100, "status": "assigned", "service_id": 1, "scheduled_at": "2023-01-01"}
    mock_book_table.select.return_value.eq.return_value.execute.return_value.data = [mock_booking]
    
    # 3. assign_technician Logic Mocks
    # Service query
    mock_service_table.select.return_value.eq.return_value.execute.return_value.data = [{"provider_role_id": "plumber"}]
    
    # Technician query (Find all plumbers)
    # The logic is: tech_res = await sbase.table("technician").select("id").eq("provider_role_id", provider_role).execute()
    mock_tech_table.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": tech_uuid}, 
        {"id": "new_tech_id"}
    ]
    
    # History Check (in assign_technician)
    # history_res = await sbase.table("assignment_request").select("techie_id, status").eq("booking_id", booking_id).execute()
    # It should return the tech we just rejected (status=rejected).
    # Since we reused mock_req_table, we need to be careful. usage: .select(...).eq(...)
    # The verify request uses: .select("*").eq("id", 1).eq("techie_id", ...)
    # The history check uses: .select("techie_id, status").eq("booking_id", 100)
    
    # We can rely on different call signatures or queue return values if they are same signature.
    # But here signatures are slightly different (double .eq vs single .eq).
    # Verify req: eq().eq()
    # History check: eq()
    
    # So:
    # double eq (verify)
    mock_req_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_request]
    
    # single eq (history)
    # Note: assign_technician calls .eq("booking_id", booking_id).execute()
    # BUT, reject_assignment also calls .update(...).eq("id", request_id).execute()
    # The update call comes BEFORE assign_technician.
    
    # Sequence of calls on mock_req_table:
    # 1. select().eq().eq() -> verify
    # 2. update().eq() -> reject status update
    # 3. select().eq() -> history check (inside assign_technician)
    # 4. insert() -> new offer (inside assign_technician)
    
    # Let's configure the mock to handle this.
    
    # For select().eq().execute():
    # It catches both history check? No, history check is select().eq()
    # Is there any other select().eq()? 
    # Yes, if we are not careful.
    
    # Let's just set the return value for the generic chain (select().eq().execute()) to be the history list.
    # because verify uses select().eq().eq(), which is lengthier chain.
    mock_req_table.select.return_value.eq.return_value.execute.return_value.data = [{"techie_id": tech_uuid, "status": "rejected"}]
    
    # New request insert for second tech
    mock_req_table.insert.return_value.execute.return_value.data = [{"id": 2}]

    app.dependency_overrides[verify_technician] = lambda: tech_uuid
    
    try:
        response = client.post("/api/funcs/technician.rejectAssignment", json=payload)
    except Exception as e:
        print(f"Test Exception: {e}")
        raise e
    
    app.dependency_overrides = {}
    
    assert response.status_code == 200
    # If the message fails, it means new_assignment returned None (re-assign failed)
    assert response.json()["message"] == "Assignment rejected. Re-assignment process triggered."
    mock_req_table.update.assert_called_with({"status": "rejected"})

