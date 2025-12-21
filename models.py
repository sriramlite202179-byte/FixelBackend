from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class UserProfile(BaseModel):
    id: UUID
    name: str
    mob_no: Optional[str] = None # Assuming snake_case consistency
    address: Optional[str] = None

class Technician(BaseModel):
    id: UUID
    created_at: datetime
    name: str
    phone: Optional[str] = None
    provider_role_id: Optional[str] = None # Snake_case

class Service(BaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    name: str
    price: int
    description: Optional[str] = None
    provider_role_id: Optional[str] = None # Snake_case

class Assignment(BaseModel):
    id: int
    created_at: datetime
    techie_id: UUID # Snake_case
    service_id: int # Snake_case
    booking_id: int # Add booking_id
    scheduled_at: Optional[datetime] = None # Snake_case
    status: Optional[str] = "active"

class Booking(BaseModel):
    id: int
    created_at: datetime
    user_id: UUID
    service_id: int
    scheduled_at: datetime
    assignment_id: Optional[int] = None
    status: Optional[str] = "pending"


class AssignmentRequest(BaseModel):
    id: int
    created_at: datetime
    booking_id: int
    techie_id: UUID
    status: Optional[str] = "pending" # pending, accepted, rejected, expired

class Notification(BaseModel):
    id: int
    created_at: datetime
    user_id: UUID
    title: str
    content: Optional[str] = None

class SubService(BaseModel):
    id: int
    created_at: datetime
    service_id: int
    name: str
    price: int
    description: Optional[str] = None

class BookingItem(BaseModel):
    id: int
    created_at: datetime
    booking_id: int
    sub_service_id: int
    price: int

# --- Read/Response Models ---

class SubServiceRead(SubService):
    pass

class ServiceRead(Service):
    sub_service: list[SubService] = []

class BookingItemRead(BookingItem):
    sub_service: Optional[SubService] = None

class AssignmentRead(Assignment):
    technician: Optional[Technician] = None
    service: Optional[Service] = None
    booking: Optional[Booking] = None

class BookingRead(Booking):
    service: Optional[Service] = None
    assignment: Optional[AssignmentRead] = None
    booking_item: list[BookingItemRead] = []

class AssignmentRequestRead(AssignmentRequest):
    booking: Optional[BookingRead] = None

class BookServiceResponse(BaseModel):
    booking: Booking



