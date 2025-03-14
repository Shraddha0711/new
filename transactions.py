from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Firebase Setup
cred = credentials.Certificate(os.getenv("CRED_PATH"))
initialize_app(cred)
db = firestore.client()

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Model for Connects Input
class ConnectInput(BaseModel):
    user_id: str
    connects: int
    transaction_type: str  # ["buy", "use", "add"]

### ✅ Helper Function to Calculate Amount
def calculate_amount(connects: int):
    # You can set your own logic of amount per connect
    price_per_connect = 10  # Example: 10 rupees per connect
    return connects * price_per_connect


### ✅ 1. Handle Connect Transactions (Add/Use/Buy)
@app.post("/connects/")
async def manage_connects(data: ConnectInput):
    # Fetch the recruiter document
    recruiter_ref = db.collection("recruiters").document(data.user_id)
    recruiter = recruiter_ref.get()

    # If recruiter does not exist
    if not recruiter.exists:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    # Get current connects of the recruiter
    recruiter_data = recruiter.to_dict()
    current_connects = recruiter_data.get("connects", 0)

    # Handle Transaction Types
    if data.transaction_type.lower() == "buy":
        # Add connects for buy
        new_connects = current_connects + data.connects
        transaction_type = "Buy"
    elif data.transaction_type.lower() == "add":
        # Add free connects (like bonus or admin gift)
        new_connects = current_connects + data.connects
        transaction_type = "Add"
    elif data.transaction_type.lower() == "use":
        # Use connects
        if data.connects > current_connects:
            raise HTTPException(status_code=400, detail="Insufficient connects")
        new_connects = current_connects - data.connects
        transaction_type = "Use"
    else:
        raise HTTPException(status_code=400, detail="Invalid transaction type. Use 'buy', 'add', or 'use'.")

    # ✅ Step 1: Update Recruiter Profile with New Connects
    recruiter_ref.update({
        "connects": new_connects,
        "updated_at": datetime.utcnow()
    })

    # ✅ Step 2: Add Transaction Record in `connects_transaction`
    amount = calculate_amount(data.connects) if transaction_type == "Buy" else 0
    transaction_ref = db.collection("connects_transaction").document()
    transaction_ref.set({
        "user_id": data.user_id,
        "connects": data.connects,
        "amount": amount,
        "transaction_type": transaction_type,
        "timestamp": datetime.utcnow()
    })

    return {
        "message": f"{transaction_type} completed successfully.",
        "new_connects": new_connects
    }


### ✅ 2. Get Connects Summary for Recruiter
@app.get("/connects/{user_id}")
async def get_connects_summary(user_id: str):
    # Get Recruiter Profile
    recruiter_ref = db.collection("recruiters").document(user_id)
    recruiter = recruiter_ref.get()

    if not recruiter.exists:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    recruiter_data = recruiter.to_dict()
    return {
        "user_id": user_id,
        "total_connects": recruiter_data.get("connects", 0)
    }


### ✅ 3. Get All Connect Transactions for User
@app.get("/transactions/{user_id}")
async def get_all_transactions(user_id: str):
    transactions = db.collection("connects_transaction").where("user_id", "==", user_id).stream()

    data = []
    for transaction in transactions:
        data.append({
            "id": transaction.id,
            **transaction.to_dict()
        })
    return data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

