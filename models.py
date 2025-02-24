from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str
    profile_image: str  # URL after Cloudinary upload


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Transaction(BaseModel):
    user_id: str
    type: str  # "deposit" or "transfer"
    amount: float
    status: str  # "pending", "completed", "failed"
    reference: str
    timestamp: datetime = datetime.utcnow()


class TransferRequest(BaseModel):
    recipient_account: str
    bank_code: str
    amount: float


class DepositWebhook(BaseModel):
    event: str
    data: dict
