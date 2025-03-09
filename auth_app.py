from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import requests
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Optional
import os
import uvicorn
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from datetime import timezone
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

class UserSignUp(BaseModel):
    email: str
    password: str

class UserSignIn(BaseModel):
    email: str
    password: str


@app.post("/signup")
def sign_up(user: UserSignUp):
    # Firebase sign-up endpoint
    sign_up_url = f'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}'
    sign_up_payload = {
        "email": user.email,
        "password": user.password,
        "returnSecureToken": True
    }
    sign_up_response = requests.post(sign_up_url, json=sign_up_payload)
    
    if sign_up_response.status_code == 200:
        id_token = sign_up_response.json().get('idToken')
        
        # Send email verification
        verify_email_url = f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}'
        verify_email_payload = {
            "requestType": "VERIFY_EMAIL",
            "idToken": id_token
        }
        verify_email_response = requests.post(verify_email_url, json=verify_email_payload)
        
        if verify_email_response.status_code == 200:
            return {"message": "Verification email sent. Please check your inbox."}
        else:
            raise HTTPException(status_code=verify_email_response.status_code, detail=verify_email_response.json())
    else:
        raise HTTPException(status_code=sign_up_response.status_code, detail=sign_up_response.json())
    

    
@app.post("/signin")
def sign_in(user: UserSignIn):
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}'
    payload = {
        "email": user.email,
        "password": user.password,
        "returnSecureToken": True
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    
class UserProfile(BaseModel):
    name: str
    city: str
    country: str
    phone_number: str
    email: str
    bio: Optional[str] = None
    role: str
    profile_pic_url: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: str

@app.post("/password-reset")
def send_password_reset_email(request: PasswordResetRequest):
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}'
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": request.email
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return {"message": "Password reset email sent."}
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    

@app.post("/user/profile")
def create_user_profile(profile: UserProfile, token: str):
    try:
        # Verify Firebase ID token
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]

        # Reference Firestore document
        user_ref = db.collection("recruiters").document(uid)

        # Data to be stored (including static and derived fields)
        user_data = {
            "name": profile.name,
            "city": profile.city,
            "country": profile.country,
            "phone_number": profile.phone_number,
            "email": profile.email,
            "bio": profile.bio,
            "role": profile.role,
            "profile_pic_url": profile.profile_pic_url,
            "connects": 100, # Default 100 connects
            "rating": 0.0,  # Default rating
            "no_of_people_rated": 0,  # Initially 0
            "verified_badge": False,  # Recruiters need to purchase verification
            "num_candidates_listed": 0,  # Updated dynamically as they list candidates
            "created_at": datetime.utcnow(),  # Timestamp at creation
            "updated_at": datetime.utcnow(),  # Timestamp at update
            "num_of_deals": 0,  # Starts at 0
            "tags": [],  # Derived from roles of listed candidates
            "sponsored": {"status": False, "created_at": None, "plan_name": None, "end_date": None},
            "highlighted": False  # Default false
        }

        # Save user profile in Firestore
        user_ref.set(user_data)

        return {"message": "User profile created/updated successfully."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/logout")
def logout(token: str):
    try:
        # Verify the ID token and get the user UID
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]

        # Revoke all refresh tokens for the user
        auth.revoke_refresh_tokens(uid)

        return {"message": "User logged out successfully."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/verify-token")
def verify_token(token: str = Header(None)):
    try:
        # Decode and verify the Firebase ID token (disable IAM check)
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        uid = decoded_token["uid"]

        return {
            "message": "Token is valid.",
            "user_id": uid,
            "email": decoded_token.get("email"),
            "expires_at": datetime.utcfromtimestamp(decoded_token["exp"]).strftime("%Y-%m-%d %H:%M:%S UTC")
        }

    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired. Please log in again.")
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token has been revoked.")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@app.get("/users")
def get_all_users():
    try:
        users_ref = db.collection("recruiters").stream()
        users = []

        for user in users_ref:
            user_data = user.to_dict()
            user_data["id"] = user.id  # Include document ID
            users.append(user_data)

        return {"users": users}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Entry point to run the FastAPI app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
