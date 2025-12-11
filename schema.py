from pydantic import BaseModel
from uuid import UUID

class BookServiceRequest(BaseModel):
    service_id: int
    user_id: UUID
    scheduled_at: str

class UserRequest(BaseModel):
    user_id: UUID

class TechnicianRequest(BaseModel):
    tech_id: int

class UpdateStatusRequest(BaseModel):
    assignment_id: int
    status: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    mob_no: str | None = None
    address: str | None = None

class ViewBookingRequest(BaseModel):
    user_id: UUID
    booking_id: int
