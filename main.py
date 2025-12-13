from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
import smtplib
from email.message import EmailMessage
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from models import Service, Assignment, Technician, UserProfile, Booking, Notification
from schema import BookServiceRequest, UserRequest, TechnicianRequest, UpdateStatusRequest, LoginRequest, RegisterRequest, ViewBookingRequest, CancelBookingRequest, TechnicianRegisterRequest, TechnicianLoginRequest
from db import get_supabase, AsyncClient
from uuid import UUID
from utils import send_email, verify_user, verify_technician
from fastapi import Depends, HTTPException

app = FastAPI(title="Fixel Backend", docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")

# --- User Functions ---

@app.post("/api/funcs/user.register")
async def register_user(data: RegisterRequest, sbase: AsyncClient = Depends(get_supabase)):
    # 1. Sign up with Supabase Auth
    try:
        auth_res = await sbase.auth.sign_up({
            "email": data.email,
            "password": data.password,
        })
    except Exception as e:
        print("Error: ", e)
        raise HTTPException(status_code=400, detail=str(e))

    if not auth_res.user:
        print("Error: User not found")
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
    profile_res = await sbase.table("userprofile").upsert(profile_data).execute()
    
    if not profile_res.data:
        print("Error: Profile not found")
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
async def login_user(data: LoginRequest, sbase: AsyncClient = Depends(get_supabase)):
    try:
        auth_res = await sbase.auth.sign_in_with_password({
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
async def view_services(sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("service").select("*").execute()
    print(response.data)
    return response.data

@app.post("/api/funcs/service.bookService")
async def book_service(data: BookServiceRequest, sbase: AsyncClient = Depends(get_supabase)):
    # Create Booking directly (Assignment decoupled)
    booking_data = {
        "user_id": str(data.user_id),
        "service_id": data.service_id,
        "scheduled_at": data.scheduled_at,
        "status": "pending"
    }
    booking_res = await sbase.table("bookings").insert(booking_data).execute()
    
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
async def cancel_booking(data: CancelBookingRequest, user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    # 1. Verify booking exists and belongs to user
    booking_res = await sbase.table("bookings").select("*").eq("id", data.booking_id).eq("user_id", user_id).execute()
    
    if not booking_res.data:
        raise HTTPException(status_code=404, detail="Booking not found or does not belong to user")
    
    booking = booking_res.data[0]
    
    if booking["status"] == "cancelled":
        return {"message": "Booking is already cancelled"}

    # 2. Update status
    update_res = await sbase.table("bookings").update({"status": "cancelled"}).eq("id", data.booking_id).execute()
    
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to cancel booking")

    return {"message": "Booking cancelled successfully", "booking": update_res.data[0]}

async def assign_technician(booking_id: int, service_id: int, scheduled_at: str):
    sbase = await get_supabase()
    # 1. Get Service to find provider_role_id
    service_res = await sbase.table("service").select("provider_role_id").eq("id", service_id).execute()
    if not service_res.data:
        return None
    provider_role = service_res.data[0]["provider_role_id"]

    # 2. Find Technicians with matching provider_role
    # Using 'like' or 'eq' depending on exact match. Assuming exact match for now.
    tech_res = await sbase.table("technician").select("id").eq("provider_role_id", provider_role).execute()
    
    valid_techs = tech_res.data
    if not valid_techs:
        # No tech found
        return None
    
    # 3. Simple Algorithm: Pick first available (or just first one for MVP)
    # Ideally check overlaps, but user said "pick a technician... I let you handle implementation"
    selected_tech = valid_techs[0]
    
    # 4. Create Assignment
    assignment_data = {
        "techie_id": selected_tech["id"],
        "service_id": service_id,
        "booking_id": booking_id,
        "scheduled_at": scheduled_at
    }
    assign_res = await sbase.table("assignment").insert(assignment_data).execute()
    
    if assign_res.data:
        assignment = assign_res.data[0]
        # 5. Update Booking status
        await sbase.table("bookings").update({"status": "assigned", "assignment_id": assignment["id"]}).eq("id", booking_id).execute()
        return assignment
    
    return None


@app.post("/api/funcs/user.viewBookedServices")
async def view_booked_services(user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    # Query bookings table, join service directly (since assignment might be null)
    # Supabase join: select(*, service(*))
    response = await sbase.table("bookings").select("*, service:service_id(*)").eq("user_id", user_id).execute()
    print(response.data)
    return response.data

@app.post("/api/funcs/user.viewBooking")
async def view_booking(data: ViewBookingRequest, user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("bookings").select("*, service:service_id(*), assignment:assignment_id(*, technician:techie_id(*))").eq("id", data.booking_id).eq("user_id", user_id).execute()
    
    if not response.data:
         raise HTTPException(status_code=404, detail="Booking not found")
    
    return response.data[0]

@app.post("/api/funcs/user.viewUser")
async def view_user(user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("userprofile").select("*").eq("id", user_id).execute()
    print(response.data)
    return response.data

@app.post("/api/funcs/notification.viewNotifications")
async def view_notifications(user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("notifications").select("*").eq("user_id", user_id).execute()
    return response.data

# --- Technician Functions ---

@app.post("/api/funcs/technician.register")
async def register_technician(data: TechnicianRegisterRequest, sbase: AsyncClient = Depends(get_supabase)):
    # 1. Sign up with Supabase Auth
    try:
        auth_res = await sbase.auth.sign_up({
            "email": data.email,
            "password": data.password,
        })
    except Exception as e:
        print("Error: ", e)
        raise HTTPException(status_code=400, detail=str(e))

    if not auth_res.user:
        raise HTTPException(status_code=400, detail="Registration failed")

    user_id = auth_res.user.id

    # 2. Create Technician
    tech_data = {
        "id": user_id,
        "name": data.name,
        "phone": data.phone,
        "provider_role_id": data.provider_role_id
    }
    
    # Use upsert=True just in case
    tech_res = await sbase.table("technician").upsert(tech_data).execute()
    
    if not tech_res.data:
        pass # Handle error or assume success if no exception

    return {
        "user": auth_res.user,
        "session": auth_res.session,
        "technician": tech_res.data[0] if tech_res.data else None
    }

@app.post("/api/funcs/technician.login")
async def login_technician(data: TechnicianLoginRequest, sbase: AsyncClient = Depends(get_supabase)):

    try:
        auth_res = await sbase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

    

        # Check if actually a technician
        tech_res = await sbase.table("technician").select("id").eq("id", auth_res.user.id).execute()
        print(tech_res.data, auth_res.user.id)
        if not tech_res.data:
             raise HTTPException(status_code=403, detail="User is not a technician")

        return {
            "user": auth_res.user,
            "session": auth_res.session
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(e)
        if "email not confirmed" in str(e):
             raise HTTPException(status_code=403, detail="Email not confirmed.")
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/funcs/technician.viewProfile")
async def view_technician_profile(techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("technician").select("*").eq("id", techie_id).execute()
    return response.data[0] if response.data else None

@app.post("/api/funcs/technician.viewAssignedBookings")
async def view_assigned_services(techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # Select assignments where techie_id matches
    response = await sbase.table("assignment").select("*, service:service_id(*), booking:booking_id(*)").eq("techie_id", techie_id).execute()
    return response.data

@app.post("/api/funcs/technician.viewBookingHistory")
async def view_booking_history(techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # For now, maybe all assignments are history? Or filter by completed?
    # Let's assume viewAssigned is 'active' and history is 'past'.
    # For MVP, just return all assignments order by date desc.
    response = await sbase.table("assignment").select("*, service:service_id(*), booking:booking_id(*)").eq("techie_id", techie_id).order("scheduled_at", desc=True).execute()
    return response.data

@app.post("/api/funcs/service.updateStatus")
async def update_status(data: UpdateStatusRequest, techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # 1. Verify Assignment belongs to Technician
    assign_res = await sbase.table("assignment").select("id").eq("id", data.assignment_id).eq("techie_id", techie_id).execute()
    if not assign_res.data:
        raise HTTPException(status_code=403, detail="Assignment not found or does not belong to you")

    # 2. Update status in 'bookings' table via assignment_id
    response = await sbase.table("bookings").update({"status": data.status}).eq("assignment_id", data.assignment_id).execute()
    return response.data

# --- Admin Functions (CRUD) ---

# Service CRUD
@app.post("/api/funcs/admin.service.create")
async def admin_create_service(service: Service, sbase: AsyncClient = Depends(get_supabase)):
    data = service.model_dump(exclude={"id", "created_at", "updated_at"})
    response = await sbase.table("service").insert(data).execute()
    return response.data

@app.post("/api/funcs/admin.service.update")
async def admin_update_service(id: int, updates: Dict[str, Any], sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("service").update(updates).eq("id", id).execute()
    return response.data

@app.post("/api/funcs/admin.service.delete")
async def admin_delete_service(id: int, sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("service").delete().eq("id", id).execute()
    return response.data

# Technician CRUD
@app.post("/api/funcs/admin.technician.create")
async def admin_create_technician(tech: Technician, sbase: AsyncClient = Depends(get_supabase)):
    data = tech.model_dump(exclude={"id", "created_at"})
    response = await sbase.table("technician").insert(data).execute()
    return response.data

@app.post("/api/funcs/admin.technician.delete")
async def admin_delete_technician(id: int, sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("technician").delete().eq("id", id).execute()
    return response.data

# Assignment CRUD (Admin)
@app.post("/api/funcs/admin.assignment.create")
async def admin_create_assignment(assignment: Assignment, sbase: AsyncClient = Depends(get_supabase)):
    data = assignment.model_dump(exclude={"id", "created_at"})
    response = await sbase.table("assignment").insert(data).execute()
    return response.data

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
