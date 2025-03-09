from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
load_dotenv()
# Initialize Firebase
cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))
initialize_app(cred)
db = firestore.client()

app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model
class Biding(BaseModel):
    role: str
    location: str
    ctc: float
    skills: List[str]
    recruiter_id: str
    match_find: bool = False

# Create Biding
@app.post("/biding/", response_model=dict)
def create_biding(biding: Biding):
    doc_ref = db.collection("biding").add(biding.dict())
    return {"id": doc_ref[1].id, "message": "Biding created successfully"}

# Update Biding
@app.put("/biding/{biding_id}", response_model=dict)
def update_biding(biding_id: str, biding: Biding):
    doc_ref = db.collection("biding").document(biding_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Biding not found")
    doc_ref.update(biding.dict())
    return {"message": "Biding updated successfully"}

# Delete Biding
@app.delete("/biding/{biding_id}", response_model=dict)
def delete_biding(biding_id: str):
    doc_ref = db.collection("biding").document(biding_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Biding not found")
    doc_ref.delete()
    return {"message": "Biding deleted successfully"}

# List all Biding with match_find=False
@app.get("/biding/", response_model=Dict[str, List[Dict[str, Any]]])
def list_bidings():
    try:
        biding_docs = db.collection("biding").where("match_find", "==", False).stream()
        bidings = [{"id": doc.id, **doc.to_dict()} for doc in biding_docs]

        return {"bidings": bidings}  # Correct structure
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)