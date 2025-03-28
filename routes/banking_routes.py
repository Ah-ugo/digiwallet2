from fastapi import APIRouter, Depends, HTTPException, Request, Query
from models import TransferRequest
from utils import initiate_deposit, initiate_transfer,verify_deposit, transfer_funds, initiate_monnify_transfer, get_all_banks
from database import users, transactions
from routes.auth_routes import get_admin_user, get_current_user
from bson import ObjectId
import logging
from datetime import datetime

router = APIRouter()


logging.basicConfig(level=logging.INFO)

@router.post("/deposit/")
async def deposit(amount: float, current_user=Depends(get_current_user)):
    response = initiate_deposit(current_user["email"], amount)
    if response["status"]:
        return {"message": "Deposit initialized", "payment_url": response["data"]["authorization_url"]}
    raise HTTPException(status_code=400, detail="Deposit failed")


@router.post("/monnify/deposit/")
async def monnify_deposit(amount: float = Query(...), current_user: dict = Depends(get_current_user)):
    logging.info(f"Deposit request received for user: {current_user['_id']}, amount: {amount}")

    if amount <= 0:
        logging.error("Invalid amount: must be greater than zero")
        raise HTTPException(status_code=400, detail="Invalid amount")

    if not current_user["account_number"]:
      logging.error("User does not have a monnify account number")
      raise HTTPException(status_code=400, detail="User does not have monnify account")

    try:
        response = initiate_monnify_deposit(current_user["account_number"], amount)

        logging.info(f"Monnify API Response: {response}")

        if response and response.get("requestSuccessful"): #added response and response.get check.

            return {
                "message": "Deposit initiated",
                "payment_url": response["responseBody"]["paymentUrl"],
                "account_number": current_user["account_number"],
                "amount": amount
            }
        else:
            logging.error(f"Monnify API call failed: {response}") #added logging
            raise HTTPException(status_code=400, detail="Deposit initiation failed")

    except Exception as e:
        logging.error(f"Monnify API call failed: {e}")
        raise HTTPException(status_code=400, detail="Deposit initiation failed")


@router.post("/verify-deposit/")
async def verify_deposit_transaction(payment_reference: str, current_user=Depends(get_current_user)):
    """
    Verify a deposit transaction using Monnify's API.
    """
    response = verify_deposit(payment_reference)
    if response["message"] == "Deposit successful":
        return response
    raise HTTPException(status_code=400, detail=response["message"])


@router.post("/transfer/")
async def transfer(transfer_data: TransferRequest, current_user=Depends(get_current_user)):
    response = initiate_transfer(transfer_data.recipient_account, transfer_data.bank_code, transfer_data.amount)
    if response["requestSuccessful"]:
        return {"message": "Transfer successful"}
    raise HTTPException(status_code=400, detail="Transfer failed")


@router.post("/monnify/transfer/")
async def monnify_transfer(
    amount: float = Query(...),
    destination_bank_code: str = Query(...),
    destination_account_number: str = Query(...),
    narration: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    logging.info(f"Transfer request received for user: {str(current_user['_id'])}, amount: {amount}, bank: {destination_bank_code}, account: {destination_account_number}")

    if amount <= 0:
        logging.error("Invalid amount: must be greater than zero")
        raise HTTPException(status_code=400, detail="Invalid amount")

    if not current_user.get("account_number"):
        logging.error("User does not have a Monnify account number")
        raise HTTPException(status_code=400, detail="User does not have a Monnify account")

    if current_user.get("wallet_balance", 0) < amount:
        logging.error("Insufficient Funds")
        raise HTTPException(status_code=400, detail="Insufficient Funds")

    try:
        transfer_reference = f"TRANSFER_{str(ObjectId())}_{int(datetime.utcnow().timestamp())}"
        response = initiate_monnify_transfer(amount, transfer_reference, narration, destination_bank_code, destination_account_number, current_user["account_number"])
        logging.info(f"Monnify Transfer API Response: {response}")

        if response and response.get("requestSuccessful") == True:
            new_balance = current_user["wallet_balance"] - amount
            users.update_one({"_id": ObjectId(current_user["_id"])}, {"$set": {"wallet_balance": new_balance}})

            transaction = {
                "user_id": str(current_user["_id"]),  # Convert ObjectId to string
                "type": "transfer",
                "amount": amount,
                "reference": transfer_reference,
                "recipient_bank_code": destination_bank_code,
                "recipient_account_number": destination_account_number,
                "narration": narration,
                "status": "success",
                "timestamp": datetime.utcnow()
            }
            transactions.insert_one(transaction)

            return {
                "message": "Transfer initiated and recorded",
                "reference": transfer_reference,
                "amount": amount,
                "new_balance": new_balance,
                "transfer_details": response.get("responseBody"),
                "transaction": {**transaction, "_id": str(transaction.get("_id", ""))}  # Convert _id if it exists
            }
        else:
            logging.error(f"Monnify Transfer API call failed: {response}")
            raise HTTPException(status_code=400, detail="Transfer initiation failed")

    except Exception as e:
        logging.error(f"Monnify Transfer API call failed: {e}")
        raise HTTPException(status_code=400, detail="Transfer initiation failed")





@router.post("/paystack/transfer/")
async def paystack_transfer(
        amount: float = Query(...),
        destination_bank_code: str = Query(...),
        destination_account_number: str = Query(...),
        narration: str = Query(...),
        current_user: dict = Depends(get_current_user)
):
    """Endpoint to handle Paystack transfers"""
    logging.info(f"Transfer request received for user: {current_user['_id']}, amount: {amount}")

    # Validate amount
    if amount <= 0:
        logging.error("Invalid amount: must be greater than zero")
        raise HTTPException(status_code=400, detail="Invalid amount")

    # Check if user has sufficient balance
    if current_user["wallet_balance"] < amount:
        logging.error("Insufficient Funds")
        raise HTTPException(status_code=400, detail="Insufficient Funds")

    try:
        # Create transfer recipient
        recipient_response = create_transfer_recipient(
            destination_account_number,
            destination_bank_code
        )

        if "error" in recipient_response or not recipient_response.get("status"):
            logging.error(f"Failed to create transfer recipient: {recipient_response}")
            raise HTTPException(status_code=400, detail="Failed to create transfer recipient")

        recipient_code = recipient_response["data"]["recipient_code"]

        # Initiate transfer
        transfer_response = initiate_paystack_transfer(
            amount,
            recipient_code,
            narration
        )

        if "error" in transfer_response or not transfer_response.get("status"):
            logging.error(f"Failed to initiate transfer: {transfer_response}")
            raise HTTPException(status_code=400, detail="Failed to initiate transfer")

        # Update user's wallet balance
        new_balance = current_user["wallet_balance"] - amount
        users.update_one(
            {"_id": ObjectId(current_user["_id"])},
            {"$set": {"wallet_balance": new_balance}}
        )

        # Record the transaction
        transaction_data = {
            "user_id": str(current_user["_id"]),
            "type": "transfer",
            "amount": amount,
            "recipient_account": destination_account_number,
            "recipient_bank_code": destination_bank_code,
            "transfer_code": transfer_response["data"]["transfer_code"],
            "status": transfer_response["data"]["status"],
            "created_at": datetime.datetime.utcnow()
        }
        transactions.insert_one(transaction_data)

        return {
            "message": "Transfer initiated",
            "reference": transfer_response["data"]["transfer_code"],
            "amount": amount,
            "new_balance": new_balance,
            "transfer_details": transfer_response.get("data")
        }

    except Exception as e:
        logging.error(f"Transfer failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Transfer initiation failed")


@router.get("/paystack/transfer/{transfer_code}/verify")
async def verify_transfer(
        transfer_code: str,
        current_user: dict = Depends(get_current_user)
):
    """Verify a Paystack transfer status"""
    try:
        verification = verify_paystack_transfer(transfer_code)

        if "error" in verification or not verification.get("status"):
            raise HTTPException(status_code=400, detail="Transfer verification failed")

        # Update transaction status in database
        transactions.update_one(
            {"transfer_code": transfer_code},
            {"$set": {"status": verification["data"]["status"]}}
        )

        return {
            "message": "Transfer verified",
            "status": verification["data"]["status"],
            "amount": verification["data"]["amount"] / 100  # Convert from kobo to naira
        }

    except Exception as e:
        logging.error(f"Transfer verification failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Transfer verification failed")


@router.get("/balance/")
async def get_balance(account_number: str = None, current_user=Depends(get_current_user)):
    """Users get their own balance. Admins can check any user's balance by account number."""
    if account_number:
        admin_user = get_admin_user(current_user)
        user = users.find_one({"account_number": account_number})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"balance": user["wallet_balance"]}
    return {"balance": current_user["wallet_balance"]}


@router.get("/transactions/")
async def get_transactions(account_number: str = None, current_user=Depends(get_current_user)):
    """Users get their own transactions. Admins can check any user's transactions by account number."""
    if account_number:
        admin_user = get_admin_user(current_user)
        user = users.find_one({"account_number": account_number})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return list(transactions.find({"user_id": str(user["_id"])}))

    return list(transactions.find({"user_id": str(current_user["_id"])}))


@router.get("/users/{account_number}/")
async def get_user_by_account(account_number: str, current_user=Depends(get_admin_user)):
    user = users.find_one({"account_number": account_number})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# @router.post("/monnify/webhook/")
# async def monnify_webhook(request: Request):
#     try:
#         data = await request.json()
#         logging.info(f"Webhook received: {data}")
#
#         event_type = data.get("eventType")
#         transaction_reference = data.get("transactionReference")
#         payment_status = data.get("paymentStatus")
#         amount = float(data.get("amountPaid", 0))
#         account_number = data.get("destinationAccountNumber")
#         source_account = data.get("sourceAccountNumber")
#         transaction_type = data.get("paymentMethod")
#
#         if event_type == "SUCCESSFUL_TRANSACTION" and payment_status == "PAID":
#             # Check if it's an incoming transfer
#             if source_account: #if source account exist, it is a transfer.
#                 user = users.find_one({"account_number": account_number})
#                 if not user:
#                     logging.error(f"No user found for account {account_number}")
#                     raise HTTPException(status_code=400, detail="User not found")
#
#                 new_balance = user.get("wallet_balance", 0) + amount
#                 users.update_one({"_id": user["_id"]}, {"$set": {"wallet_balance": new_balance}})
#
#                 transaction = {
#                     "user_id": str(user["_id"]),
#                     "type": "deposit",
#                     "amount": amount,
#                     "reference": transaction_reference,
#                     "method": transaction_type.lower(),
#                     "status": "success",
#                     "timestamp": datetime.utcnow(),
#                 }
#                 transactions.insert_one(transaction)
#
#                 return {"message": "Deposit recorded", "transaction": transaction}
#             else: #if source account does not exist, it is a direct deposit.
#                 user = users.find_one({"account_number": account_number})
#                 if not user:
#                     logging.error(f"No user found for account {account_number}")
#                     raise HTTPException(status_code=400, detail="User not found")
#
#                 new_balance = user.get("wallet_balance", 0) + amount
#                 users.update_one({"_id": user["_id"]}, {"$set": {"wallet_balance": new_balance}})
#
#                 transaction = {
#                     "user_id": str(user["_id"]),
#                     "type": "deposit",
#                     "amount": amount,
#                     "reference": transaction_reference,
#                     "method": transaction_type.lower(),
#                     "status": "success",
#                     "timestamp": datetime.utcnow(),
#                 }
#                 transactions.insert_one(transaction)
#
#                 return {"message": "Deposit recorded", "transaction": transaction}
#
#         elif event_type == "TRANSFER_SUCCESS":
#             sender = users.find_one({"account_number": source_account})
#             if not sender:
#                 logging.error(f"No sender found for account {source_account}")
#                 raise HTTPException(status_code=400, detail="Sender not found")
#
#             new_balance = sender.get("wallet_balance", 0) - amount
#             users.update_one({"_id": sender["_id"]}, {"$set": {"wallet_balance": new_balance}})
#
#             transaction = {
#                 "user_id": str(sender["_id"]),
#                 "type": "transfer",
#                 "amount": amount,
#                 "reference": transaction_reference,
#                 "recipient_account": account_number,
#                 "status": "success",
#                 "timestamp": datetime.utcnow(),
#             }
#             transactions.insert_one(transaction)
#
#             return {"message": "Transfer recorded", "transaction": transaction}
#
#         return {"message": "Unhandled event type"}
#
#     except KeyError as e:
#         logging.error(f"Webhook processing failed due to missing key: {e}")
#         raise HTTPException(status_code=400, detail=f"Webhook processing failed: Missing key {e}")
#     except Exception as e:
#         logging.error(f"Webhook processing failed: {e}")
#         raise HTTPException(status_code=400, detail="Webhook processing failed")


@router.post("/monnify/webhook/")
async def monnify_webhook(request: Request):
    try:
        data = await request.json()
        logging.info(f"Webhook received: {data}")

        event_type = data.get("eventType")
        transaction_reference = data.get("transactionReference")
        payment_status = data.get("paymentStatus")
        amount = float(data.get("amountPaid", 0))
        account_number = data.get("destinationAccountNumber")
        source_account = data.get("sourceAccountNumber")
        transaction_type = data.get("paymentMethod")

        if event_type == "SUCCESSFUL_TRANSACTION" and payment_status == "PAID":
            user = users.find_one({"account_number": account_number})
            if not user:
                logging.error(f"No user found for account {account_number}")
                raise HTTPException(status_code=400, detail="User not found")

            try:
                current_balance = float(user.get("wallet_balance", 0))
                new_balance = current_balance + amount

                logging.info(f"Updating balance for user {user['_id']}. Current balance: {current_balance}, amount: {amount}, new balance: {new_balance}")

                result = users.update_one({"_id": user["_id"]}, {"$set": {"wallet_balance": new_balance}})

                if result.modified_count == 0:
                    logging.error(f"Failed to update balance for user {user['_id']}")
                    raise HTTPException(status_code=500, detail="Failed to update balance")

                logging.info(f"Database update result: {result.modified_count}")

                transaction = {
                    "user_id": str(user["_id"]),
                    "type": "deposit",
                    "amount": amount,
                    "reference": transaction_reference,
                    "method": transaction_type.lower(),
                    "status": "success",
                    "timestamp": datetime.utcnow(),
                }
                transactions.insert_one(transaction)

                return {"message": "Deposit recorded", "transaction": transaction}

            except Exception as db_error:
                logging.error(f"Error updating database: {db_error}")
                raise HTTPException(status_code=500, detail="Database update failed")

        elif event_type == "TRANSFER_SUCCESS":
            sender = users.find_one({"account_number": source_account})
            if not sender:
                logging.error(f"No sender found for account {source_account}")
                raise HTTPException(status_code=400, detail="Sender not found")

            try:
                current_balance = float(sender.get("wallet_balance", 0))
                new_balance = current_balance - amount

                logging.info(f"Updating balance for sender {sender['_id']}. Current balance: {current_balance}, amount: {amount}, new balance: {new_balance}")

                result = users.update_one({"_id": sender["_id"]}, {"$set": {"wallet_balance": new_balance}})

                if result.modified_count == 0:
                    logging.error(f"Failed to update balance for sender {sender['_id']}")
                    raise HTTPException(status_code=500, detail="Failed to update balance")

                logging.info(f"Database update result: {result.modified_count}")

                transaction = {
                    "user_id": str(sender["_id"]),
                    "type": "transfer",
                    "amount": amount,
                    "reference": transaction_reference,
                    "recipient_account": account_number,
                    "status": "success",
                    "timestamp": datetime.utcnow(),
                }
                transactions.insert_one(transaction)

                return {"message": "Transfer recorded", "transaction": transaction}

            except Exception as db_error:
                logging.error(f"Error updating database: {db_error}")
                raise HTTPException(status_code=500, detail="Database update failed")

        return {"message": "Unhandled event type"}

    except KeyError as e:
        logging.error(f"Webhook processing failed due to missing key: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook processing failed: Missing key {e}")

    except Exception as e:
        logging.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")


@router.get("/transactions/{user_id}")
async def get_transactions(user_id: str):
    user_transactions = list(transactions.find({"user_id": user_id}, {"_id": 0}))
    return {"transactions": user_transactions}



@router.get("/banks/")
async def get_banks_endpoint():
    """Endpoint to get all banks and their codes."""
    banks = get_all_banks()

    if "error" in banks:
        raise HTTPException(status_code=500, detail="Failed to fetch banks")

    return banks
