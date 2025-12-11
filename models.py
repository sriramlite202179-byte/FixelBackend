from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

class Service(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    name: str
    price: int
    description: Optional[str] = None
    provider_role_id: Optional[str] = None

class Assignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tech_id: int = Field(foreign_key="technician.id")
    service_id: int = Field(foreign_key="service.id") 
    scheduled_at: Optional[datetime] = None

class Technician(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    name: str
    phone: Optional[str] = None
    provider_role: Optional[str] = None

class UserProfile(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: Optional[str] = None
    mob_no: Optional[str] = None
    address: Optional[str] = None
