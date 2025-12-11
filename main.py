from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from models import Service, Assignment, Technician, UserProfile, Booking, Notification
from schema import BookServiceRequest, UserRequest, TechnicianRequest, UpdateStatusRequest
from db import supabase
from uuid import UUID

app = FastAPI(title="Fixel Backend")

# --- User Functions ---

@app.post("/api/funcs/service.viewServices")
async def view_services():
    response = supabase.table("service").select("*").execute()
    return response.data

@app.post("/api/funcs/service.bookService")
async def book_service(data: BookServiceRequest):
    # Create Booking directly (Assignment decoupled)
    booking_data = {
        "user_id": str(data.user_id),
        "service_id": data.service_id,
        "scheduled_at": data.scheduled_at,
        "status": "pending"
    }
    booking_res = supabase.table("bookings").insert(booking_data).execute()
    
    return {
        "booking": booking_res.data[0] if booking_res.data else None
    }

@app.post("/api/funcs/user.viewBookedServices")
async def view_booked_services(data: UserRequest):
    # Query bookings table, join service directly (since assignment might be null)
    # Supabase join: select(*, service(*))
    response = supabase.table("bookings").select("*, service:service_id(*)").eq("user_id", str(data.user_id)).execute()
    return response.data

@app.post("/api/funcs/user.viewUser")
async def view_user(data: UserRequest):
    response = supabase.table("userprofile").select("*").eq("id", str(data.user_id)).execute()
    return response.data

@app.post("/api/funcs/notification.viewNotifications")
async def view_notifications(data: UserRequest):
    response = supabase.table("notifications").select("*").eq("user_id", str(data.user_id)).execute()
    return response.data

# --- Technician Functions ---

@app.post("/api/funcs/technician.viewAssignedServices")
async def view_assigned_services(data: TechnicianRequest):
    # Select assignments where tech_id matches
    response = supabase.table("assignment").select("*, service:service_id(*)").eq("tech_id", data.tech_id).execute()
    return response.data

@app.post("/api/funcs/service.updateStatus")
async def update_status(data: UpdateStatusRequest):
    # Update status in 'bookings' table via assignment_id
    response = supabase.table("bookings").update({"status": data.status}).eq("assignment_id", data.assignment_id).execute()
    return response.data

# --- Admin Functions (CRUD) ---

# Service CRUD
@app.post("/api/funcs/admin.service.create")
async def admin_create_service(service: Service):
    data = service.model_dump(exclude={"id", "created_at", "updated_at"})
    response = supabase.table("service").insert(data).execute()
    return response.data

@app.post("/api/funcs/admin.service.update")
async def admin_update_service(id: int, updates: Dict[str, Any]):
    response = supabase.table("service").update(updates).eq("id", id).execute()
    return response.data

@app.post("/api/funcs/admin.service.delete")
async def admin_delete_service(id: int):
    response = supabase.table("service").delete().eq("id", id).execute()
    return response.data

# Technician CRUD
@app.post("/api/funcs/admin.technician.create")
async def admin_create_technician(tech: Technician):
    data = tech.model_dump(exclude={"id", "created_at"})
    response = supabase.table("technician").insert(data).execute()
    return response.data

@app.post("/api/funcs/admin.technician.delete")
async def admin_delete_technician(id: int):
    response = supabase.table("technician").delete().eq("id", id).execute()
    return response.data

# Assignment CRUD (Admin)
@app.post("/api/funcs/admin.assignment.create")
async def admin_create_assignment(assignment: Assignment):
    data = assignment.model_dump(exclude={"id", "created_at"})
    response = supabase.table("assignment").insert(data).execute()
    return response.data

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
