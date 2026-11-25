from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from models import ContainerStatus, ServiceType, SizeType


class VesselSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vessel_name: str
    voyage_no: str
    eta: datetime
    closing_time: datetime
    port_code: str


class ContainerLookupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cntr_no: str
    is_iso6346_valid: bool
    found_in_yard: bool
    id: Optional[int] = None
    size_type: Optional[SizeType] = None
    status: Optional[ContainerStatus] = None
    customs_cleared: Optional[bool] = None
    do_expiry_date: Optional[datetime] = None
    yard_in_date: Optional[datetime] = None
    yard_location: Optional[str] = None
    vessel: Optional[VesselSummary] = None


class OrderCreateRequest(BaseModel):
    cntr_no: str = Field(..., min_length=1, max_length=20)
    service_type: ServiceType
    truck_no: str = Field(..., min_length=3, max_length=20)
    user_id: Optional[int] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_code: str
    cntr_no: str
    service_type: ServiceType
    truck_no: str
    handling_fee: float
    storage_fee: float
    total_amount: float
    payment_status: str
    qr_token: str
    created_at: datetime
    user_id: int
    container_id: int


class OrderPayResponse(BaseModel):
    order_id: int
    order_code: str
    payment_status: str
    qr_token: str
    qr_base64: str
    message: str


class GateCheckinRequest(BaseModel):
    qr_token: str = Field(..., min_length=1, max_length=255)
    gate_operator: str = Field(default="gate_01")


class GateCheckinResponse(BaseModel):
    order_id: int
    order_code: str
    eir_no: str
    cntr_no: str
    size_type: str
    service_type: ServiceType
    truck_no: str
    yard_location: str
    vessel_info: str
    total_amount: float
    payment_status: str
    checked_in_at: datetime
    message: str
