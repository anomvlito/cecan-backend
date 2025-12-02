from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
import os
import shutil
from datetime import datetime
from api.routes.auth import require_editor, User

router = APIRouter(prefix="/files", tags=["Files"])

UPLOAD_DIR = "backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_editor)
):
    try:
        # Generate safe filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize filename to avoid directory traversal
        safe_filename = os.path.basename(file.filename)
        filename = f"{timestamp}_{safe_filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"filename": filename, "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{filename}")
async def get_file(filename: str):
    # Sanitize filename
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)
