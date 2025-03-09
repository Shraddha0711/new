from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os 
from dotenv import load_dotenv
load_dotenv()

# Firebase setup
cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))  # Path to your service account key
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

# Pydantic model to represent candidate data, including created_by
class Candidate(BaseModel):
    name: str
    location: str
    ctc: float
    notice_period: str
    linkedin: Optional[str] = None
    role: str
    skills: List[str]
    experience: float
    contact: str
    email: str
    created_by: str  # Added field for creator's id
    candidate_id: Optional[str] = None  # Added field for candidate ID (document ID)

# Helper function to save candidate to Firestore
def save_candidate(candidate: Candidate):
    candidate_dict = candidate.dict()
    # Initialize empty bookmarks array if it doesn't exist
    candidate_dict['bookmarks'] = []
    candidate_dict['profile_seen_count'] = 0
    
    # Create a new document in Firestore and get its document ID
    doc_ref = db.collection("candidates").document()
    candidate_dict["candidate_id"] = doc_ref.id  # Assign the document ID as candidate_id
    doc_ref.set(candidate_dict)  # Save the candidate
    return doc_ref.id

# Endpoint to create a new candidate
@app.post("/candidates/")
async def create_candidate(candidate: Candidate):
    try:
        # Pass the creator's email and save the candidate
        candidate_id = save_candidate(candidate)
        return {"message": "Candidate created successfully", "candidate_id": candidate_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to create multiple candidates in bulk
@app.post("/candidates/bulk/")
async def bulk_create_candidates(candidates: List[Candidate]):
    try:
        batch = db.batch()
        for candidate in candidates:
            # Pass the creator's email and save each candidate in bulk
            doc_ref = db.collection("candidates").document()
            candidate_dict = candidate.dict()
            candidate_dict["candidate_id"] = doc_ref.id  # Assign document ID as candidate_id
            candidate_dict["bookmarks"] = []
            batch.set(doc_ref, candidate_dict)
        
        batch.commit()  # Commit all the bulk operations at once
        return {"message": f"{len(candidates)} candidates created successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint to get all candidates
@app.get("/candidates/")
async def get_all_candidates():
    try:
        candidates_ref = db.collection("candidates").stream()
        candidates = [candidate.to_dict() for candidate in candidates_ref]
        return {"candidates": candidates}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to search candidates by keyword (match in any field)
@app.get("/candidates/search/")
async def search_candidates(keyword: str):
    try:
        candidates_ref = db.collection("candidates").stream()
        matched_candidates = []
        
        for candidate in candidates_ref:
            candidate_data = candidate.to_dict()
            if any(keyword.lower() in str(value).lower() for value in candidate_data.values()):
                matched_candidates.append(candidate_data)

        return matched_candidates
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to filter candidates by multiple fields
@app.get("/candidates/filter/")
async def filter_candidates(
    location: Optional[str] = Query(None),
    ctc: Optional[float] = Query(None),
    role: Optional[str] = Query(None),
    experience: Optional[float] = Query(None),
    notice_period: Optional[str] = Query(None),
    skills: Optional[List[str]] = Query(None),
):
    try:
        candidates_ref = db.collection("candidates").stream()
        filtered_candidates = []

        for candidate in candidates_ref:
            candidate_data = candidate.to_dict()
            if (
                (location is None or candidate_data.get("location", "").lower() == location.lower()) and
                (ctc is None or candidate_data.get("ctc", float("inf")) <= ctc) and
                (role is None or candidate_data.get("role", "").lower() == role.lower()) and
                (experience is None or candidate_data.get("experience", 0) >= experience) and
                (notice_period is None or candidate_data.get("notice_period", "").lower() == notice_period.lower()) and
                (skills is None or ("skills" in candidate_data and all(skill.lower() in [s.lower() for s in candidate_data["skills"]] for skill in skills)))
            ):
                filtered_candidates.append(candidate_data)

        return filtered_candidates
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to bookmark a candidate
@app.post("/candidates/{candidate_id}/bookmark/")
async def bookmark_candidate(candidate_id: str, recruiter_id: str):
    try:
        candidate_ref = db.collection("candidates").document(candidate_id)
        recruiter_ref = db.collection("recruiters").document(recruiter_id)
        
        candidate = candidate_ref.get()
        recruiter = recruiter_ref.get()
        
        if not candidate.exists:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        candidate_data = candidate.to_dict()
        if recruiter_id not in candidate_data["bookmarks"]:
            candidate_data["bookmarks"].append(recruiter_id)
            candidate_ref.update({"bookmarks": candidate_data["bookmarks"]})
        
        if recruiter.exists:
            recruiter_data = recruiter.to_dict()
            if "bookmarked_candidates" not in recruiter_data:
                recruiter_data["bookmarked_candidates"] = []
            if candidate_id not in recruiter_data["bookmarked_candidates"]:
                recruiter_data["bookmarked_candidates"].append(candidate_id)
                recruiter_ref.update({"bookmarked_candidates": recruiter_data["bookmarked_candidates"]})
        else:
            recruiter_ref.set({"bookmarked_candidates": [candidate_id]})
        
        return {"message": "Candidate bookmarked successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to list all bookmarks for a recruiter
@app.get("/recruiters/{recruiter_id}/bookmarks/")
async def list_bookmarked_candidates(recruiter_id: str):
    try:
        recruiter_ref = db.collection("recruiters").document(recruiter_id)
        recruiter = recruiter_ref.get()
        
        if not recruiter.exists:
            return {"message": "No bookmarks found"}
        
        recruiter_data = recruiter.to_dict()
        candidate_ids = recruiter_data.get("bookmarked_candidates", [])
        
        if not candidate_ids:
            return {"message": "No bookmarks found"}
        
        candidates = []
        for candidate_id in candidate_ids:
            candidate_ref = db.collection("candidates").document(candidate_id)
            candidate_doc = candidate_ref.get()
            if candidate_doc.exists:
                candidates.append(candidate_doc.to_dict())
        
        return candidates
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to remove a bookmark
@app.delete("/candidates/{candidate_id}/bookmark/")
async def remove_bookmark(candidate_id: str, recruiter_id: str):
    try:
        candidate_ref = db.collection("candidates").document(candidate_id)
        recruiter_ref = db.collection("recruiters").document(recruiter_id)
        
        candidate = candidate_ref.get()
        recruiter = recruiter_ref.get()
        
        if not candidate.exists:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        candidate_data = candidate.to_dict()
        if recruiter_id in candidate_data["bookmarks"]:
            candidate_data["bookmarks"].remove(recruiter_id)
            candidate_ref.update({"bookmarks": candidate_data["bookmarks"]})
        
        if recruiter.exists:
            recruiter_data = recruiter.to_dict()
            if "bookmarked_candidates" in recruiter_data and candidate_id in recruiter_data["bookmarked_candidates"]:
                recruiter_data["bookmarked_candidates"].remove(candidate_id)
                recruiter_ref.update({"bookmarked_candidates": recruiter_data["bookmarked_candidates"]})
        
        return {"message": "Bookmark removed successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to update a candidate's profile
@app.put("/candidates/{candidate_id}/")
async def update_candidate(candidate_id: str, candidate: Candidate):
    try:
        candidate_ref = db.collection("candidates").document(candidate_id)
        candidate_doc = candidate_ref.get()

        if candidate_doc.exists:
            candidate_ref.update(candidate.dict())
            return {"message": "Candidate profile updated successfully."}
        else:
            raise HTTPException(status_code=404, detail="Candidate not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoint to delete a candidate
@app.delete("/candidates/{candidate_id}/")
async def delete_candidate(candidate_id: str):
    try:
        candidate_ref = db.collection("candidates").document(candidate_id)
        candidate = candidate_ref.get()

        if candidate.exists:
            candidate_ref.delete()
            return {"message": "Candidate deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Candidate not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
