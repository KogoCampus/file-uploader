from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import os
from ..backend.s3 import S3Service
from ..config import settings

router = APIRouter(prefix="/images", tags=["images"])
s3_service = S3Service()

@router.post("/")
async def upload_image(
    file: UploadFile = File(...),
    fileName: Optional[str] = Form(None)
):
    """
    Upload an image to S3.
    
    - **file**: The image file to upload (required)
    - **fileName**: Custom filename for the uploaded image (optional)
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    content_type = file.content_type
    if not content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")

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

    url = await s3_service.upload_file(file.file, final_filename)
    return {
        "filename": final_filename,
        "url": url,
        "size": file_size,
        "content_type": content_type
    }

@router.get("/")
async def list_images(prefix: str = ""):
    """
    List all images in the bucket.
    """
    return await s3_service.list_files(prefix)

@router.get("/{image_name}")
async def get_image(image_name: str):
    """
    Get a presigned URL for an image.
    """
    return {"url": await s3_service.get_file_url(image_name)}

@router.delete("/{image_name}")
async def delete_image(image_name: str):
    """
    Delete an image from S3.
    """
    success = await s3_service.delete_file(image_name)
    return {
        "success": success,
        "message": "Image deleted successfully",
        "filename": image_name
    } 