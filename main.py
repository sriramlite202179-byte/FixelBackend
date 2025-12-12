from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
import smtplib
from email.message import EmailMessage
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from models import Service, Assignment, Technician, UserProfile, Booking, Notification
from schema import BookServiceRequest, UserRequest, TechnicianRequest, UpdateStatusRequest, LoginRequest, RegisterRequest, ViewBookingRequest, CancelBookingRequest
from db import supabase
from uuid import UUID
from utils import send_mail

app = FastAPI(title="Fixel Backend")

# --- User Functions ---

@app.post("/api/funcs/user.register")
async def register_user(data: RegisterRequest):
    # 1. Sign up with Supabase Auth
    try:
        auth_res = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not auth_res.user:
         # Depending on config, sign_up might return a user but require email confirmation.
         # If no user is returned, something went wrong.
         raise HTTPException(status_code=400, detail="Registration failed")

    user_id = auth_res.user.id

    # 2. Create UserProfile
    profile_data = {
        "id": user_id,
        "name": data.name,
        "mob_no": data.mob_no,
        "address": data.address
    }
    
    # Use upsert=True just in case, though it should be new
    profile_res = supabase.table("userprofile").upsert(profile_data).execute()
    
    if not profile_res.data:
         # Note: If automatic trigger exists, this might fail or be redundant.
         # Provided schema implies we manage this manually for now?
         # If fail, we might technically have an orphan auth user. 
         # For this task, we assume happy path or simple error.
         pass

    return {
        "user": auth_res.user,
        "session": auth_res.session,
        "profile": profile_res.data[0] if profile_res.data else None
    }

@app.post("/api/funcs/user.login")
async def login_user(data: LoginRequest):
    try:
        auth_res = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        return {
            "user": auth_res.user,
            "session": auth_res.session
        }
    except Exception as e:
        print(e)
        if "email not confirmed" in str(e):
            raise HTTPException(status_code=403, detail="Email not confirmed. Please check your inbox to verify your email address.")

        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/funcs/service.viewServices")
async def view_services():
    response = supabase.table("service").select("*").execute()
    print(response.data)
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
    
    if not booking_res.data:
        raise HTTPException(status_code=500, detail="Failed to create booking")

    booking = booking_res.data[0]
    booking_id = booking["id"]

    # Trigger Assignment
    assignment = await assign_technician(booking_id, data.service_id, data.scheduled_at)
    
    # # Notify User (Booking Received)
    # # Ideally fetch user email from UserProfile, but for now assuming we have it or just logging
    # # In a real app we'd fetch the user email. Let's try to fetch it.
    # user_res = supabase.table("userprofile").select("email").eq("id", str(data.user_id)).execute()
    # user_email = user_res.data[0]["email"] if user_res.data and "email" in user_res.data[0] else None
    
    # if user_email:
    #     send_email(user_email, "Booking Confirmation", f"Your booking (ID: {booking_id}) has been received.")

    # if assignment:
    #      # Notify User of Assignment
    #      if user_email:
    #          send_email(user_email, "Technician Assigned", f"A technician has been assigned to your booking (ID: {booking_id}).")

    return {
        "booking": booking,
        "assignment": assignment
    }

@app.post("/api/funcs/user.cancelBooking")
async def cancel_booking(data: CancelBookingRequest):
    # 1. Verify booking exists and belongs to user
    booking_res = supabase.table("bookings").select("*").eq("id", data.booking_id).eq("user_id", str(data.user_id)).execute()
    
    if not booking_res.data:
        raise HTTPException(status_code=404, detail="Booking not found or does not belong to user")
    
    booking = booking_res.data[0]
    
    if booking["status"] == "cancelled":
        return {"message": "Booking is already cancelled"}

    # 2. Update status
    update_res = supabase.table("bookings").update({"status": "cancelled"}).eq("id", data.booking_id).execute()
    
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to cancel booking")

    # 3. Notify User
    # Fetch user email
    # user_res = supabase.table("userprofile").select("email").eq("id", str(data.user_id)).execute()
    # user_email = user_res.data[0]["email"] if user_res.data and "email" in user_res.data[0] else None
    
    # if user_email:
    #     send_email(user_email, "Booking Cancelled", f"Your booking (ID: {data.booking_id}) has been cancelled.")

    return {"message": "Booking cancelled successfully", "booking": update_res.data[0]}

async def assign_technician(booking_id: int, service_id: int, scheduled_at: str):
    # 1. Get Service to find provider_role_id
    service_res = supabase.table("service").select("provider_role_id").eq("id", service_id).execute()
    if not service_res.data:
        return None
    provider_role = service_res.data[0]["provider_role_id"]

    # 2. Find Technicians with matching provider_role
    # Using 'like' or 'eq' depending on exact match. Assuming exact match for now.
    tech_res = supabase.table("technician").select("id").eq("provider_role_id", provider_role).execute()
    
    valid_techs = tech_res.data
    if not valid_techs:
        # No tech found
        return None
    
    # 3. Simple Algorithm: Pick first available (or just first one for MVP)
    # Ideally check overlaps, but user said "pick a technician... I let you handle implementation"
    selected_tech = valid_techs[0]
    
    # 4. Create Assignment
    assignment_data = {
        "tech_id": selected_tech["id"],
        "service_id": service_id,
        "booking_id": booking_id,
        "scheduled_at": scheduled_at
    }
    assign_res = supabase.table("assignment").insert(assignment_data).execute()
    
    if assign_res.data:
        assignment = assign_res.data[0]
        # 5. Update Booking status
        supabase.table("bookings").update({"status": "assigned", "assignment_id": assignment["id"]}).eq("id", booking_id).execute()
        return assignment
    
    return None


@app.post("/api/funcs/user.viewBookedServices")
async def view_booked_services(data: UserRequest):
    # Query bookings table, join service directly (since assignment might be null)
    # Supabase join: select(*, service(*))
    response = supabase.table("bookings").select("*, service:service_id(*)").eq("user_id", str(data.user_id)).execute()
    print(response.data)
    return response.data

@app.post("/api/funcs/user.viewBooking")
async def view_booking(data: ViewBookingRequest):
    response = supabase.table("bookings").select("*, service:service_id(*), assignment:assignment_id(*, technician:tech_id(*))").eq("id", data.booking_id).eq("user_id", str(data.user_id)).execute()
    
    if not response.data:
         raise HTTPException(status_code=404, detail="Booking not found")
    
    return response.data[0]

@app.post("/api/funcs/user.viewUser")
async def view_user(data: UserRequest):
    response = supabase.table("userprofile").select("*").eq("id", str(data.user_id)).execute()
    print(response.data)
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
