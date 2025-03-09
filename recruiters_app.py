from fastapi import FastAPI, HTTPException
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Load Firebase credentials from environment variable
cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))
firebase_admin.initialize_app(cred)

# Initialize Firestore client
db = firestore.client()

# Enable CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/recruiters")
def get_all_recruiters():
    """Fetch all recruiters from Firestore"""
    try:
        recruiters_ref = db.collection("recruiters").stream()
        recruiters = []
        
        # Retrieve recruiter data from Firestore
        for recruiter in recruiters_ref:
            recruiter_data = recruiter.to_dict()
            recruiter_data["id"] = recruiter.id  # Include document ID
            recruiters.append(recruiter_data)

        return {"recruiters": recruiters}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sponsored-recruiters")
def get_sponsored_recruiters():
    """Fetch only recruiters with sponsored.status = True"""
    try:
        recruiters_ref = db.collection("recruiters").where("sponsored.status", "==", True).stream()
        sponsored_recruiters = []
        
        # Retrieve sponsored recruiter data from Firestore
        for recruiter in recruiters_ref:
            recruiter_data = recruiter.to_dict()
            recruiter_data["id"] = recruiter.id  # Include document ID
            sponsored_recruiters.append(recruiter_data)

        return {"sponsored_recruiters": sponsored_recruiters}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/recruiter/{recruiter_id}")
def get_recruiter_by_id(recruiter_id: str):
    """Fetch a specific recruiter's details by ID"""
    try:
        recruiter_ref = db.collection("recruiters").document(recruiter_id)
        recruiter_doc = recruiter_ref.get()
        
        if recruiter_doc.exists:
            recruiter_data = recruiter_doc.to_dict()
            recruiter_data["id"] = recruiter_id  # Include document ID
            return {"recruiter": recruiter_data}
        else:
            raise HTTPException(status_code=404, detail="Recruiter not found")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
