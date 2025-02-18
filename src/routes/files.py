from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from typing import Optional
import os
from io import BytesIO
from ..backend.s3 import S3Service
from ..config import settings
from ..backend.file_types import ALLOWED_FILE_TYPES
import json

file_router = APIRouter(prefix="/files", tags=["files"])
s3_service = S3Service()

@file_router.post("")
async def upload_file(
    file: UploadFile = File(...),
    fileName: Optional[str] = Form(None)
):
    """
    Upload a file to S3.
    
    body:
        - file: The (image/video/gif) file to upload (required)
        - fileName: Custom filename for the uploaded file (optional)
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Get file type
    file_type = ALLOWED_FILE_TYPES[file.content_type]
    if file_type is None:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Check file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.max_file_size:
        raise HTTPException(status_code=400, detail="File too large")

    # Use provided filename or generate from original
    if fileName:
        file_extension = os.path.splitext(file.filename)[1]
        final_filename = f"{fileName}{file_extension}"
    else:
        final_filename = file.filename

    # Upload file to S3
    response = await s3_service.upload_file(file, final_filename)
    file_id = response["file_id"]
    url = response["url"]

    # create a filedata.json inside file_id folder
    filedata = {
        "url": url,
        "file_id": file_id,
        "filename": final_filename,
        "metadata": await s3_service.get_metadata(f"{file_type}/{file_id}/origin/{final_filename}"),
        "variants": {},
    }
    await s3_service.save_filedata(file_id, file_type, filedata)

    return filedata

@file_router.get("/{file_id}")
async def get_file(file_id: str):
    """
    Get the data of the file from S3.
    """
    data = await s3_service.load_filedata(file_id)
    return json.loads(data["Body"].read())

@file_router.delete("/{file_id}")
async def delete_file(
    file_id: str,
):
    """
    Delete a file from S3.
    """   
    await s3_service.delete_file(file_id)
    return {
        "message": "File deleted successfully",
        "file_id": file_id,
    } 
