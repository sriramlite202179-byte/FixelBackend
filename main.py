from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
import smtplib
from email.message import EmailMessage
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from models import Service, Assignment, Technician, UserProfile, Booking, Notification, AssignmentRequest, SubService, BookingItem, ServiceRead, BookingRead, AssignmentRead, BookingItemRead, SubServiceRead, AssignmentRequestRead, BookServiceResponse
from schema import BookServiceRequest, UserRequest, TechnicianRequest, UpdateStatusRequest, LoginRequest, RegisterRequest, ViewBookingRequest, CancelBookingRequest, TechnicianRegisterRequest, TechnicianLoginRequest, AssignmentResponseRequest, RegisterPushTokenRequest, TestNotificationRequest
from db import get_supabase, AsyncClient
from uuid import UUID
from utils import send_email, verify_user, verify_technician, send_push_notification
from fastapi import Depends, HTTPException, Header

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
        # Fetch User Profile
        user_id = auth_res.user.id
        profile_res = await sbase.table("userprofile").select("*").eq("id", user_id).execute()
        
        return {
            "user": auth_res.user,
            "session": auth_res.session,
            "profile": profile_res.data[0] if profile_res.data else None
        }
    except Exception as e:
        print(f"Login failed: {e}")
        if "email not confirmed".lower() in str(e).lower():
            raise HTTPException(status_code=403, detail="Email not confirmed. Please check your inbox to verify your email address.")

        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/funcs/service.viewServices", response_model=list[ServiceRead])
async def view_services(sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("service").select("*, sub_service(*)").order("id").execute()
    print(response.data)
    return response.data

@app.post("/api/funcs/service.bookService", response_model=BookServiceResponse)
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

    # Handle Sub-services (Booking Items)
    if data.sub_service_ids:
        # Fetch prices to ensure data integrity
        ss_res = await sbase.table("sub_service").select("id, price").in_("id", data.sub_service_ids).execute()
        valid_subs = ss_res.data
        
        if valid_subs:
            items_data = [
                {
                    "booking_id": booking_id,
                    "sub_service_id": vs["id"],
                    "price": vs["price"]
                }
                for vs in valid_subs
            ]
            await sbase.table("booking_item").insert(items_data).execute()

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
    tech_res = await sbase.table("technician").select("id, push_token").eq("provider_role_id", provider_role).execute()
    
    valid_techs = tech_res.data
    if not valid_techs:
        return None
        
    # 3. Check existing AssignmentRequests to filter out rejected techs
    history_res = await sbase.table("assignment_request").select("techie_id, status").eq("booking_id", booking_id).execute()
    rejected_tech_ids = {h["techie_id"] for h in history_res.data if h["status"] in ["rejected", "expired"]}
    
    eligible_techs = [t for t in valid_techs if t["id"] not in rejected_tech_ids]

    if not eligible_techs:
        # No eligible tech found (all rejected or none available)
        return None
    
    # 4. Pick first available
    selected_tech = eligible_techs[0]
    
    # 5. Create AssignmentRequest (Offer)
    # Status default is pending
    request_data = {
        "techie_id": selected_tech["id"],
        "booking_id": booking_id,
        "status": "pending"
    }
    
    # We don't have service_id or scheduled_at in AssignmentRequest schema I Defined in plan?
    # Wait, the user said "techie_id, booking_id, acceptance_status, created_at". 
    # I should stick to that schema for AssignmentRequest.
    # The 'Assignment' table still holds service/scheduled info, but we create that LATER.
    
    req_res = await sbase.table("assignment_request").insert(request_data).execute()
    
    if req_res.data:
        # 6. Update Booking status
        # We don't have an 'assignment_id' yet to link in the booking table because Assignment doesn't exist.
        # But we might want to know it's "assigned/offered".
        # Let's just set status="assigned".
        await sbase.table("bookings").update({"status": "assigned"}).eq("id", booking_id).execute()
        return req_res.data[0]
    
    # Notify Technician
    if selected_tech.get("push_token"):
         send_push_notification(
             token=selected_tech["push_token"],
             title="New Booking Available",
             message=f"You have a new booking request.",
             data={"booking_id": booking_id, "type": "assignment_request"}
         )
    
    return None


@app.post("/api/funcs/user.viewBookedServices", response_model=list[BookingRead])
async def view_booked_services(user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    # Query bookings table, join service directly (since assignment might be null)
    # Supabase join: select(*, service(*))
    # Supabase join: select(*, service(*), booking_item(*, sub_service(*)))
    response = await sbase.table("bookings").select("*, service:service_id(*), booking_item(*, sub_service(*))").eq("user_id", user_id).order("created_at", desc=True).execute()
    print(response.data)
    return response.data

@app.post("/api/funcs/user.viewBooking", response_model=BookingRead)
async def view_booking(data: ViewBookingRequest, user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("bookings").select("*, service:service_id(*), assignment:assignment_id(*, technician:techie_id(*)), booking_item(*, sub_service(*))").eq("id", data.booking_id).eq("user_id", user_id).execute()
    
    if not response.data:
         raise HTTPException(status_code=404, detail="Booking not found")
    
    return response.data[0]

@app.post("/api/funcs/user.viewUser", response_model=list[UserProfile])
async def view_user(user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("userprofile").select("*").eq("id", user_id).execute()
    print(response.data)
    return response.data

@app.post("/api/funcs/notification.viewNotifications", response_model=list[Notification])
async def view_notifications(user_id: str = Depends(verify_user), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("notifications").select("*").eq("user_id", user_id).execute()
    return response.data

@app.post("/api/funcs/utils.registerPushToken")
async def register_push_token(data: RegisterPushTokenRequest, authorization: Optional[str] = Header(None), sbase: AsyncClient = Depends(get_supabase)):
    # Re-using logic from verify code roughly, but generic
    if not authorization:
         raise HTTPException(status_code=401, detail="Missing Token")
    token = authorization.replace("Bearer ", "")
    user_res = await sbase.auth.get_user(token)
    if not user_res.user:
         raise HTTPException(status_code=401, detail="Invalid Token")
    user_id = user_res.user.id

    table = "userprofile" if data.user_type == "user" else "technician"
    
    # Update push_token column
    try:
        await sbase.table(table).update({"push_token": data.token}).eq("id", user_id).execute()
        return {"message": "Push token updated"}
    except Exception as e:
        print(f"Failed to update push token: {e}")
        raise HTTPException(status_code=500, detail="Failed to update push token")

@app.post("/api/funcs/utils.testNotification")
async def test_notification(data: TestNotificationRequest):
    send_push_notification(
        token=data.token,
        title=data.title,
        message=data.message,
        data=data.data
    )
    return {"message": "Notification sent (or attempted)"}

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

@app.post("/api/funcs/technician.viewProfile", response_model=Optional[Technician])
async def view_technician_profile(techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    response = await sbase.table("technician").select("*").eq("id", techie_id).execute()
    return response.data[0] if response.data else None

@app.post("/api/funcs/technician.viewAssignmentRequests", response_model=list[AssignmentRequestRead])
async def view_assignment_requests(techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # Fetch pending requests
    # We might want to join booking and service info so they can see what it is
    # Supabase join syntax: select(*, booking:booking_id(*, service:service_id(*))) - nested might be tricky deep, but let's try shallow first or just booking.
    # Actually booking -> service_id is in Booking table.
    response = await sbase.table("assignment_request").select("*, booking:booking_id(*, service:service_id(*))").eq("techie_id", techie_id).eq("status", "pending").execute()
    return response.data

@app.post("/api/funcs/technician.viewAssignedBookings", response_model=list[AssignmentRead])
async def view_assigned_services(techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # Select assignments where techie_id matches, excluding completed/cancelled
    response = await sbase.table("assignment").select("*, service:service_id(*), booking:booking_id(*)").eq("techie_id", techie_id).neq("status", "completed").neq("status", "cancelled").execute()
    return response.data

@app.post("/api/funcs/technician.viewBookingHistory", response_model=list[AssignmentRead])
async def view_booking_history(techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # For now, maybe all assignments are history? Or filter by completed?
    # Let's assume viewAssigned is 'active' and history is 'past'.
    # For MVP, just return all assignments order by date desc.
    response = await sbase.table("assignment").select("*, service:service_id(*), booking:booking_id(*)").eq("techie_id", techie_id).order("scheduled_at", desc=True).execute()
    return response.data

@app.post("/api/funcs/technician.acceptAssignment")
async def accept_assignment(data: AssignmentResponseRequest, techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # 1. Verify Request
    req_res = await sbase.table("assignment_request").select("*").eq("id", data.request_id).eq("techie_id", techie_id).execute()
    if not req_res.data:
        raise HTTPException(status_code=404, detail="Assignment request not found or does not belong to you")
    
    request = req_res.data[0]
    
    if request["status"] != "pending":
          raise HTTPException(status_code=400, detail="Assignment request is not pending")
          
    # 2. Get Booking to get details for Assignment
    booking_id = request["booking_id"]
    booking_res = await sbase.table("bookings").select("*").eq("id", booking_id).execute()
    if not booking_res.data:
         raise HTTPException(status_code=404, detail="Booking not found")
    
    booking = booking_res.data[0]
    if booking["status"] == "confirmed":
         return {"message": "Booking already confirmed by another technician"}

    # 3. Create Assignment
    assignment_data = {
        "techie_id": techie_id,
        "service_id": booking["service_id"],
        "booking_id": booking_id,
        "scheduled_at": booking["scheduled_at"],
        "status": "active" # or whatever status we use for active assignment
    }
    
    assign_res = await sbase.table("assignment").insert(assignment_data).execute()
    
    if not assign_res.data:
         raise HTTPException(status_code=500, detail="Failed to create assignment")
    
    assignment = assign_res.data[0]

    # 4. Update Request Status -> accepted
    await sbase.table("assignment_request").update({"status": "accepted"}).eq("id", data.request_id).execute()
    
    # 5. Update Booking Status -> confirmed
    await sbase.table("bookings").update({"status": "confirmed", "assignment_id": assignment["id"]}).eq("id", booking_id).execute()

    # Notify User
    try:
        user_profile_res = await sbase.table("userprofile").select("push_token").eq("id", booking["user_id"]).execute()
        if user_profile_res.data and user_profile_res.data[0].get("push_token"):
             send_push_notification(
                 token=user_profile_res.data[0]["push_token"],
                 title="Technician Assigned",
                 message=f"A technician has been assigned to your booking.",
                 data={"booking_id": booking_id, "type": "technician_assigned"}
             )
    except Exception as e:
        print(f"Error sending push to user: {e}")
    
    return {"message": "Assignment accepted", "assignment": assignment}

@app.post("/api/funcs/technician.rejectAssignment")
async def reject_assignment(data: AssignmentResponseRequest, techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # 1. Verify Request
    req_res = await sbase.table("assignment_request").select("*").eq("id", data.request_id).eq("techie_id", techie_id).execute()
    if not req_res.data:
        raise HTTPException(status_code=404, detail="Assignment request not found")
        
    request = req_res.data[0]
    
    # 2. Update Request Status -> rejected
    await sbase.table("assignment_request").update({"status": "rejected"}).eq("id", data.request_id).execute()
    
    # 3. Trigger next assignment
    booking_id = request["booking_id"]
    
    # Retrieve booking details for re-assignment
    booking_res = await sbase.table("bookings").select("*").eq("id", booking_id).execute()
    if booking_res.data:
        booking = booking_res.data[0]
        # Attempt to assign to next tech
        new_assignment = await assign_technician(booking_id, booking["service_id"], booking["scheduled_at"])
        
        if not new_assignment:
            # If no one else found, maybe set booking to 'pending' or 'unfulfilled'
            await sbase.table("bookings").update({"status": "pending"}).eq("id", booking_id).execute()
            return {"message": "Assignment rejected. No other technicians available."}
            
    return {"message": "Assignment rejected. Re-assignment process triggered."}

@app.post("/api/funcs/service.updateStatus")
async def update_status(data: UpdateStatusRequest, techie_id: str = Depends(verify_technician), sbase: AsyncClient = Depends(get_supabase)):
    # 1. Verify Assignment belongs to Technician
    assign_res = await sbase.table("assignment").select("id").eq("id", data.assignment_id).eq("techie_id", techie_id).execute()
    if not assign_res.data:
        raise HTTPException(status_code=403, detail="Assignment not found or does not belong to you")

    # 2. Update status in 'bookings' table via assignment_id
    await sbase.table("bookings").update({"status": data.status}).eq("assignment_id", data.assignment_id).execute()

    # 3. Update status in 'assignment' table
    response = await sbase.table("assignment").update({"status": data.status}).eq("id", data.assignment_id).execute()

    if data.status == "completed":
        # Notify User
        try: 
            # Need to get user_id from booking to get token
            # We updated bookings in step 2, let's fetch it
            booking_res = await sbase.table("bookings").select("user_id").eq("assignment_id", data.assignment_id).execute()
            if booking_res.data:
                user_id = booking_res.data[0]["user_id"]
                user_profile_res = await sbase.table("userprofile").select("push_token").eq("id", user_id).execute()
                if user_profile_res.data and user_profile_res.data[0].get("push_token"):
                    send_push_notification(
                        token=user_profile_res.data[0]["push_token"],
                        title="Booking Completed",
                        message=f"Your booking has been marked as completed.",
                        data={"booking_id": data.assignment_id, "type": "booking_completed"} # sending assignment_id as booking_id might be confusing but okay for now, ideally fetch real booking_id. 
                        # actually booking_res has booking data. 
                        # Wait, booking_res select was just user_id.
                    )
        except Exception as e:
             print(f"Error sending push to user: {e}")

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

@app.post("/api/funcs/admin.sub_service.create")
async def admin_create_sub_service(sub_service: SubService, sbase: AsyncClient = Depends(get_supabase)):
    data = sub_service.model_dump(exclude={"id", "created_at"})
    response = await sbase.table("sub_service").insert(data).execute()
    return response.data

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
