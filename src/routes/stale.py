from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from typing import Optional
import os
from ..backend.s3 import S3Service
from ..config import settings
from ..backend.file_types import ALLOWED_FILE_TYPES

stale_router = APIRouter(prefix="/stale", tags=["stale"])
s3_service = S3Service()

@stale_router.post("")
async def stale_file(
    file: UploadFile = File(...),
    fileName: Optional[str] = Form(None)
):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Get file type
    file_type = ALLOWED_FILE_TYPES.get(file.content_type)
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
    
    #upload_file
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

    # start staling scheudle
    await s3_service.schedule_staling(file_id, 20)
    return filedata

@stale_router.post("/persist/{file_id}")
async def persist_file(
    file_id: str
): 
    await s3_service.persist_file(file_id)
    return {
        "detail": "file successuly persisted",
        "file_id": file_id
    }