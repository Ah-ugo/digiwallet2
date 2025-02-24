from fastapi import APIRouter, HTTPException, Depends, Form, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from utils import (
    create_access_token, decode_access_token, hash_password, verify_password,
    upload_image, pwd_context
)
from database import users
from models import UserRegister, UserLogin
from bson import ObjectId
import requests
from utils import create_reserved_account, get_monnify_token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    user_id = payload.get("user_id")
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_admin_user(current_user=Depends(get_current_user)):
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


# @router.post("/register/")
# async def register(
#         name: str = Form(...),
#         email: str = Form(...),
#         phone: str = Form(...),
#         password: str = Form(...),
#         profile_image: UploadFile = File(...)
# ):
#     if users.find_one({"email": email}):
#         raise HTTPException(status_code=400, detail="Email already exists")
#
#     image_url = upload_image(profile_image)
#     hashed_password = pwd_context.hash(password)
#
#
#     new_user = {
#         "name": name,
#         "email": email,
#         "phone": phone,
#         "password": hashed_password,
#         "profile_image": image_url,
#         "wallet_balance": 0.0,
#         "account_number": None,
#         "is_admin": False
#     }
#
#     result = users.insert_one(new_user)
#     user_id = str(result.inserted_id)  # Get MongoDB ObjectId
#
#
#     try:
#         monnify_response = create_reserved_account(user_id)
#         reserved_account = monnify_response["accounts"][0]["accountNumber"]
#
#
#         users.update_one(
#             {"_id": ObjectId(user_id)},
#             {"$set": {"account_number": reserved_account}}
#         )
#     except Exception as e:
#         users.delete_one({"_id": ObjectId(user_id)})
#         raise HTTPException(status_code=500, detail=f"Monnify account creation failed: {str(e)}")
#
#     return {
#         "message": "User registered successfully",
#         "account_number": reserved_account
#     }


# @router.post("/register/")
# async def register(
#         name: str = Form(...),
#         email: str = Form(...),
#         phone: str = Form(...),
#         password: str = Form(...),
#         profile_image: UploadFile = File(...)
# ):
#     if users.find_one({"email": email}):
#         raise HTTPException(status_code=400, detail="Email already exists")
#
#     image_url = upload_image(profile_image)
#     hashed_password = pwd_context.hash(password)
#
#     new_user = {
#         "name": name,
#         "email": email,
#         "phone": phone,
#         "password": hashed_password,
#         "profile_image": image_url,
#         "wallet_balance": 0.0,
#         "account_number": None,
#         "is_admin": False
#     }
#
#     result = users.insert_one(new_user)
#     user_id = str(result.inserted_id)  # Get MongoDB ObjectId
#
#     try:
#         user_data = users.find_one({"_id": ObjectId(user_id)})
#         bvn_value = "22539059076" #replace with a valid bvn or nin.
#         monnify_response = create_reserved_account(
#             account_reference = str(user_data["_id"]),
#             account_name = user_data["name"],
#             customer_email = user_data["email"],
#             bvn = bvn_value,
#             customer_name = user_data["name"]
#         )
#
#         if "error" in monnify_response:
#             raise HTTPException(status_code=500, detail=f"Monnify account creation failed: {monnify_response['error']}")
#
#         reserved_account = monnify_response["responseBody"]["accounts"][0]["accountNumber"]
#
#         users.update_one(
#             {"_id": ObjectId(user_id)},
#             {"$set": {"account_number": reserved_account}}
#         )
#     except Exception as e:
#         users.delete_one({"_id": ObjectId(user_id)})
#         raise HTTPException(status_code=500, detail=f"Monnify account creation failed: {str(e)}")
#
#     return {
#         "message": "User registered successfully",
#         "account_number": reserved_account
#     }


@router.post("/register/")
async def register(
        name: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        password: str = Form(...),
        profile_image: UploadFile = File(...)
):
    if users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")

    image_url = upload_image(profile_image)
    hashed_password = pwd_context.hash(password)

    new_user = {
        "name": name,
        "email": email,
        "phone": phone,
        "password": hashed_password,
        "profile_image": image_url,
        "wallet_balance": 0.0,
        "account_number": None,
        "is_admin": False,
        "bank_name": None # add bank name to user profile
    }

    result = users.insert_one(new_user)
    user_id = str(result.inserted_id)

    try:
        user_data = users.find_one({"_id": ObjectId(user_id)})
        bvn_value = "22539059076"  # Replace with a valid bvn or nin.
        monnify_response = create_reserved_account(
            account_reference=str(user_data["_id"]),
            account_name=user_data["name"],
            customer_email=user_data["email"],
            bvn=bvn_value,
            customer_name=user_data["name"]
        )

        if "error" in monnify_response:
            raise HTTPException(status_code=500, detail=f"Monnify account creation failed: {monnify_response['error']}")

        reserved_account = monnify_response["responseBody"]["accounts"][0]["accountNumber"]
        bank_name = monnify_response["responseBody"]["accounts"][0]["bankName"] # get bank name

        users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"account_number": reserved_account, "bank_name": bank_name}} # update user profile with bank name
        )
    except Exception as e:
        users.delete_one({"_id": ObjectId(user_id)})
        raise HTTPException(status_code=500, detail=f"Monnify account creation failed: {str(e)}")

    return {
        "message": "User registered successfully",
        "account_number": reserved_account,
        "bank_name": bank_name # return bank name
    }


@router.post("/login/")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token(data={"user_id": str(user["_id"])})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/users/me/")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Endpoint to get the current authenticated user's profile.
    """
    # Convert ObjectId to string for JSON serialization
    current_user["_id"] = str(current_user["_id"])
    return current_user