from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from typing import Optional
import os
from ..backend.s3 import S3Service
from ..config import settings

schedule_router = APIRouter(prefix="/schedules", tags=["schedules"])
s3_service = S3Service()

@schedule_router.post("")
async def schedule_file(
    file: UploadFile = File(...),
    fileName: Optional[str] = Form(None)
):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    content_type = file.content_type
    file_type = await s3_service.get_file_type(file)
    
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
    
    response = await s3_service.upload_file(file, final_filename)
    file_id = response["file_id"]
    url = response["url"]

    # create a metadata.json inside images_id/ folder
    filedata = await s3_service.get_filedata(f"{file_type}/{file_id}/origin/{final_filename}")
    metadata = {}
    metadata['url'] = url
    metadata['metadata'] = filedata
    metadata["variants"] = {}
    await s3_service.save_metadata(file_id,f"{file_type}", metadata)
    await s3_service.schedule_staling(file_id, 1)
    return {
        "file_id": file_id,
        "filename": final_filename,
        "url": url,
        "size": file_size,
        "content_type": content_type
    }

@schedule_router.post("/keep/{file_id}")
async def schedule_keep_file(
    file_id: str
): 
    await s3_service.keep_file(file_id)
    return {
        "message": "file successuly kept",
        "file_id": file_id
    }