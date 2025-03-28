from jose import JWTError, jwt
import datetime
# import requests
import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi import HTTPException
import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv
import requests
import base64
import time
from database import users
from bson import ObjectId
import logging
import json

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


MONNIFY_CONTRACT_CODE = "552949494001"
MONNIFY_BASE_URL_2 = "https://api.monnify.com/api/v2/bank-transfer/reserved-accounts"
MONNIFY_BASE_URL = "https://api.monnify.com/api/v1"
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")
MONNIFY_SECRET = os.getenv("MONNIFY_SECRET")
MONNIFY_API_KEY = os.getenv("MONNIFY_API_KEY")
MONNIFY_WALLET_ACCOUNT = os.getenv("MONNIFY_WALLET_ACCOUNT")
MONNIFY_BASE_URL_3 = "https://api.monnify.com/api/v2/disbursements/single"
monnify_token = None
token_expiry = 0


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str):
    return pwd_context.verify(password, hashed_password)


# Payment setup

def initiate_deposit(email: str, amount: float):
    url = "https://api.paystack.co/transaction/initialize"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}
    data = {"email": email, "amount": int(amount * 100)}
    response = requests.post(url, json=data, headers=headers)
    return response.json()



def initiate_transfer(recipient_account: str, bank_code: str, amount: float):
    url = "https://api.monnify.com/api/v2/disbursements/single"
    headers = {"Authorization": f"Bearer {MONNIFY_API_KEY}"}
    data = {
        "amount": amount,
        "destinationBankCode": bank_code,
        "destinationAccountNumber": recipient_account,
        "narration": "Bank Transfer"
    }
    response = requests.post(url, json=data, headers=headers)
    return response.json()

# cloudinary setup
def upload_image(image):
    result = cloudinary.uploader.upload(image.file)
    return result.get("secure_url")

# monnify setup

# def get_monnify_token():
#     """Fetch and cache Monnify authentication token."""
#     credentials = f"{MONNIFY_API_KEY}:{MONNIFY_SECRET}"
#     encoded_credentials = base64.b64encode(credentials.encode()).decode()
#
#     headers = {"Authorization": f"Basic {encoded_credentials}"}
#     response = requests.post(f"{MONNIFY_BASE_URL}/auth/login", headers=headers)
#
#     if response.status_code == 200:
#         data = response.json()["responseBody"]
#         return data["accessToken"]
#
#     raise Exception("Failed to authenticate with Monnify")




def get_monnify_token():
    """
    Fetch Monnify authentication token with enhanced error handling
    Ref: https://docs.monnify.com/v1.0/reference/authentication
    """
    try:
        # Encode credentials using Base64
        credentials = f"{MONNIFY_API_KEY}:{MONNIFY_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        # Prepare headers for authentication
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }

        # Authentication endpoint
        auth_url = "https://api.monnify.com/api/v1/auth/login"

        # Make authentication request
        response = requests.post(auth_url, headers=headers)

        # Log full response for debugging
        logging.info(f"Monnify Auth Response Status: {response.status_code}")
        logging.info(f"Monnify Auth Response Headers: {response.headers}")
        logging.info(f"Monnify Auth Response Body: {response.text}")

        # Check response status
        if response.status_code == 200:
            # Parse JSON response
            data = response.json()

            # Extract and return access token
            access_token = data.get('responseBody', {}).get('accessToken')

            if not access_token:
                logging.error("No access token found in Monnify response")
                raise Exception("Failed to retrieve Monnify access token")

            return access_token
        else:
            # Detailed error logging
            logging.error(f"Monnify Authentication Failed: {response.status_code}")
            logging.error(f"Response Body: {response.text}")

            # Raise specific exceptions based on response
            if response.status_code == 401:
                raise Exception("Monnify Authentication Failed: Invalid Credentials")
            elif response.status_code == 403:
                raise Exception("Monnify Authentication Failed: IP not whitelisted")
            else:
                raise Exception(f"Monnify Authentication Failed: {response.text}")

    except requests.exceptions.RequestException as req_error:
        logging.error(f"Monnify Request Error: {req_error}")
        raise Exception(f"Network Error: {req_error}")
    except Exception as e:
        logging.error(f"Unexpected Monnify Authentication Error: {e}")
        raise Exception("Failed to authenticate with Monnify")



# def create_reserved_account(user_id: str):
#     """Create a Monnify Reserved Account for a user."""
#     user = users.find_one({"_id": ObjectId(user_id)})
#     if not user:
#         raise Exception("User not found")
#
#     token = get_monnify_token()
#
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json"
#     }
#
#     data = {
#         "accountReference": str(user["_id"]),  # Unique reference for each user
#         "accountName": user["name"],
#         "customerEmail": user["email"],
#         "customerName": user["name"],
#         "bvn": user.get("bvn", ""),  # Optional BVN
#         "contractCode": MONNIFY_CONTRACT_CODE,
#         "currencyCode": "NGN",
#         "getAllAvailableBanks": True
#     }
#
#     response = requests.post(f"{MONNIFY_BASE_URL}/reserved-accounts", json=data, headers=headers)
#
#     if response.status_code == 201:
#         return response.json()["responseBody"]
#
#     raise Exception("Failed to create reserved account")


def create_reserved_account(account_reference, account_name, customer_email, bvn, customer_name=None):
    """Create a general reserved account."""
    token = get_monnify_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    data = {
        "accountReference": account_reference,
        "accountName": account_name,
        "currencyCode": "NGN",
        "contractCode": MONNIFY_CONTRACT_CODE,
        "customerEmail": customer_email,
        "bvn": bvn,
        "getAllAvailableBanks": True,
    }

    print("Monnify Request Data:", data)

    if customer_name:
        data["customerName"] = customer_name

    try:
        response = requests.post(
            "https://api.monnify.com/api/v2/bank-transfer/reserved-accounts",
            json=data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def verify_deposit(payment_reference: str):
    """Verify a deposit transaction from Monnify."""
    token = get_monnify_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.get(f"{MONNIFY_BASE_URL}/transactions/{payment_reference}", headers=headers)

    if response.status_code == 200:
        transaction = response.json()["responseBody"]

        if transaction["paymentStatus"] == "PAID":
            user = users.find_one({"account_number": transaction["accountNumber"]})
            if user:
                new_balance = user["wallet_balance"] + float(transaction["amountPaid"])
                users.update_one({"_id": user["_id"]}, {"$set": {"wallet_balance": new_balance}})

                return {"message": "Deposit successful", "new_balance": new_balance}

        return {"message": "Deposit pending or failed"}

    raise HTTPException(status_code=500, detail="Failed to verify deposit")


def transfer_funds(user_id: str, amount: float, recipient_bank: str, recipient_account: str):
    """Transfer funds from a Monnify Reserved Account to another bank."""
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user["wallet_balance"] < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    token = get_monnify_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data = {
        "amount": amount,
        "reference": f"TRANSFER_{ObjectId()}",
        "narration": "Bank Transfer",
        "destinationAccountNumber": recipient_account,
        "destinationBankCode": recipient_bank,
        "sourceAccountNumber": user["account_number"],
        "currency": "NGN"
    }

    response = requests.post(f"{MONNIFY_BASE_URL}/transfer", json=data, headers=headers)

    if response.status_code == 200:
        new_balance = user["wallet_balance"] - amount
        users.update_one({"_id": ObjectId(user_id)}, {"$set": {"wallet_balance": new_balance}})
        return {"message": "Transfer successful", "new_balance": new_balance}

    raise HTTPException(status_code=500, detail="Transfer failed")


# def initiate_monnify_deposit(account_number: str, amount: float):
#     """Initiate a deposit using Monnify Reserved Account"""
#     token = get_monnify_token()
#
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json"
#     }
#
#     data = {
#         "accountReference": f"DEP_{ObjectId()}",
#         "accountNumber": account_number,
#         "amount": amount,
#         "currencyCode": "NGN",
#         "paymentDescription": "Wallet Funding"
#     }
#
#     response = requests.post(f"{MONNIFY_BASE_URL}/transactions/initiate", json=data, headers=headers)
#     return response.json()


def get_all_banks():
    """Fetch all banks and their codes from Monnify."""
    token = get_monnify_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get("https://api.monnify.com/api/v1/banks", headers=headers)
        response.raise_for_status()
        return response.json()["responseBody"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch banks from Monnify: {e}")
        return {"error": str(e)}


# def initiate_monnify_transfer(amount, reference, narration, destination_bank_code, destination_account_number, source_account_number):
#     """Initiate a single transfer using Monnify."""
#     token = get_monnify_token()
#
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json",
#     }
#
#     data = {
#         "amount": amount,
#         "reference": reference,
#         "narration": narration,
#         "destinationBankCode": destination_bank_code,
#         "destinationAccountNumber": destination_account_number,
#         "currency": "NGN",
#         "sourceAccountNumber": source_account_number,
#     }
#
#     logging.info(f"Monnify Transfer Request Data: {data}") #add logging
#
#     try:
#         response = requests.post(MONNIFY_BASE_URL_3, json=data, headers=headers)
#         response.raise_for_status()
#         return response.json()
#     except requests.exceptions.RequestException as e:
#         logging.error(f"Monnify Transfer Request Exception: {e}") #add logging
#         return {"error": str(e)}

def initiate_monnify_transfer(amount, reference, narration, destination_bank_code, destination_account_number,
                              source_account_number):
    """
    Initiate a single transfer using Monnify API v2 disbursement endpoint
    Ref: https://docs.monnify.com/v1.0/reference/single-disbursement
    """
    try:
        # Get authentication token
        token = get_monnify_token()

        # Prepare headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Prepare request payload
        # Note: Carefully follow Monnify's documented payload structure
        payload = {
            "amount": str(amount),  # Ensure amount is a string
            "destinationAccountNumber": destination_account_number,
            "destinationBankCode": destination_bank_code,
            "currency": "NGN",
            "narration": narration,
            "reference": reference,
            # Ensure all required fields are included
            "sourceAccountNumber": MONNIFY_WALLET_ACCOUNT,  # Use the configured wallet account
        }

        # Log detailed request information
        logging.info("Monnify Transfer Request Payload:")
        logging.info(json.dumps(payload, indent=2))

        # Make the API call
        url = "https://api.monnify.com/api/v2/disbursements/single"
        response = requests.post(url, json=payload, headers=headers)

        # Log full response details
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Headers: {response.headers}")

        # Log full response text
        full_response_text = response.text
        logging.info(f"Full Response Text: {full_response_text}")

        # Try to parse JSON response
        try:
            response_data = response.json()
        except ValueError as json_error:
            logging.error(f"JSON Parsing Error: {json_error}")
            return {
                "status": False,
                "error": "Unable to parse JSON response",
                "raw_response": full_response_text
            }

        # Comprehensive response handling
        logging.info(f"Parsed Response Data: {response_data}")

        # Monnify's response structure might differ from our initial assumptions
        # Check the actual response structure
        if response.status_code == 200:
            # Monnify might use different keys
            return {
                "status": True,
                "data": response_data,
                "message": response_data.get('responseMessage', 'Transfer initiated'),
                "transaction_reference": response_data.get('responseBody', {}).get('transactionReference')
            }
        else:
            # Handle error responses
            return {
                "status": False,
                "error_code": response.status_code,
                "message": response_data.get('responseMessage', 'Transfer failed'),
                "details": response_data
            }

    except requests.exceptions.RequestException as req_error:
        logging.error(f"Request Exception: {req_error}")
        return {
            "status": False,
            "error": str(req_error),
            "type": "request_exception"
        }
    except Exception as unexpected_error:
        logging.error(f"Unexpected Error: {unexpected_error}")
        return {
            "status": False,
            "error": str(unexpected_error),
            "type": "unexpected_error"
        }

# paystack transfer setup


def create_transfer_recipient(account_number: str, bank_code: str):
    """Create a transfer recipient on Paystack"""
    url = "https://api.paystack.co/transferrecipient"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    data = {
        "type": "nuban",
        "name": "Customer",
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "NGN"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Paystack Create Recipient Error: {str(e)}")
        if hasattr(e, 'response'):
            logging.error(f"Response content: {e.response.content}")
        return {"error": str(e)}


def initiate_paystack_transfer(amount: float, recipient_code: str, reason: str = "Transfer"):
    """Initiate a transfer using Paystack"""
    url = "https://api.paystack.co/transfer"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    amount_in_kobo = int(amount * 100)

    data = {
        "source": "balance",
        "amount": amount_in_kobo,
        "recipient": recipient_code,
        "reason": reason
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Paystack Transfer Error: {str(e)}")
        if hasattr(e, 'response'):
            logging.error(f"Response content: {e.response.content}")
        return {"error": str(e)}


def verify_paystack_transfer(transfer_code: str):
    """Verify a Paystack transfer status"""
    url = f"https://api.paystack.co/transfer/verify/{transfer_code}"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Paystack Transfer Verification Error: {str(e)}")
        if hasattr(e, 'response'):
            logging.error(f"Response content: {e.response.content}")
        return {"error": str(e)}