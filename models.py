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
    id: int
    created_at: datetime
    name: str
    phone: Optional[str] = None
    provider_role: Optional[str] = None # Snake_case

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
    tech_id: int # Snake_case
    service_id: int # Snake_case
    scheduled_at: Optional[datetime] = None # Snake_case

class Booking(BaseModel):
    id: int
    created_at: datetime
    user_id: UUID
    service_id: int
    scheduled_at: datetime
    assignment_id: Optional[int] = None
    status: Optional[str] = "pending"

class Notification(BaseModel):
    id: int
    created_at: datetime
    user_id: UUID
    title: str
    content: Optional[str] = None
