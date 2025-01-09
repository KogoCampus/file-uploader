from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from typing import Optional
from uuid import uuid4
from PIL import Image
import os
from io import BytesIO
from ..backend.s3 import S3Service
from ..config import settings
import json

router = APIRouter(prefix="/images", tags=["images"])
s3_service = S3Service()

@router.post("/")
async def upload_image(
    file: UploadFile = File(...),
    fileName: Optional[str] = Form(None)
):
    """
    Upload an image to S3.
    
    body:
        - file: The image file to upload (required)
        - fileName: Custom filename for the uploaded image (optional)
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
    
    # Generate a unique imageId
    while True:
        image_id = str(uuid4())
        if not await s3_service.check_image_id_exists(image_id):
            break

    # Use provided filename or generate from original
    if fileName:
        file_extension = os.path.splitext(file.filename)[1]
        final_filename = f"{fileName}{file_extension}"
    else:
        final_filename = file.filename

    url = await s3_service.upload_file(file, image_id, final_filename)

    # create a metadata.json inside images_id/ folder
    filedata = await s3_service.get_filedata(f"images/{image_id}/origin/{final_filename}")
    metadata = {}
    metadata['url'] = url
    metadata['metadata'] = filedata
    metadata["variants"] = {}
    await s3_service.save_metadata(image_id, metadata)

    return {
        "imageId": image_id,
        "filename": final_filename,
        "url": url,
        "size": file_size,
        "content_type": content_type
    }

@router.post("/{image_id}/crop/{file_name}")
async def crop_image(
    image_id: str,
    file_name: str,
    dimensions: str = Query(..., alias="dimensions"),
    offset: Optional[str] = Query("0,0", alias="offset")
):
    """
    Crop an original(existing) image to S3.

    query:
        - image_id: ID of the original image (required)
        - file_name: name of the original image (required)
        - dimensions: Width and height of the crop (required)
        - offset: Width and height of the crop (optional)
    """
    try:
        dimensions = [int(i) for i in dimensions.strip("[]").split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dimensions format")
    
    try:
        offset = [int(i) for i in offset.strip("[]").split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid offset format")

    if len(dimensions) != 2:
        raise HTTPException(status_code=400, detail="Invalid dimensions")
    if len(offset) != 2:
        raise HTTPException(status_code=400, detail="Invalid offset")
    
    if not await s3_service.check_image_id_exists(image_id):
        raise HTTPException(status_code=404, detail="Image ID not found in S3")
    
    original_key = f"images/{image_id}/origin/{file_name}"
    try:
        # Get the image file from S3
        original_image = s3_service.s3_client.get_object(Bucket=s3_service.bucket_name, Key=original_key)
        file_content = original_image['Body'].read()
        content_type = original_image['ContentType']

        cropped_image_stream = crop_image_from_stream(file_content, dimensions, offset)
        file_size = len(cropped_image_stream.getvalue())
        cropped_file = UploadFile(
            file=cropped_image_stream,
            filename=file_name,
            headers={
                "content-type": content_type
            }
        )
    except HTTPException as e:
        raise HTTPException(status_code=500, detail="Failed to crop the original image")
    
    dims = f"{dimensions[0]}x{dimensions[1]}"
    offs = f"offset{offset[0]}x{offset[1]}"

    # create a url using s3_service.upload_file with the new file(cropped file)
    url = await s3_service.upload_file(cropped_file, image_id, file_name, ["crop/", f"{dims}/", f"{offs}"])

    # update the metadata.json inside images_id/ folder with the new cropped image
    newfile_metadata = await s3_service.get_filedata(f"images/{image_id}/crop/{dims}/{offs}/{file_name}")
    metadata_response = await s3_service.load_metadata(f"images/{image_id}/metadata.json")
    metadata = json.loads(metadata_response["Body"].read())
    if "crop" not in metadata["variants"]:
        metadata["variants"]["crop"] = {}
    metadata["variants"]["crop"][f"{dims}_{offs}"] = newfile_metadata
    await s3_service.save_metadata(image_id, metadata)

    return {
        "imageId": image_id,
        "filename": file_name,
        "url": url,
        "size": file_size,
        "content_type": content_type
    }

@router.get("/{image_id}")
async def get_image(image_id: str):
    """
    Get the data of the image from S3.
    """
    image_key = f"images/{image_id}/metadata.json"
    data = await s3_service.load_metadata(image_key)
    return json.loads(data["Body"].read())

# @router.delete("/{image_id}/{image_name}")
# async def delete_image(
#     image_id: str,
#     image_name: str,
#     dimensions: Optional[str] = Query(..., alias="dimensions"),
#     offset: Optional[str] = Query("0,0", alias="offset")
# ):
#     """
#     Delete an image from S3.
#     """
#     if dimensions:
#         try:
#             dimensions = [int(i) for i in dimensions.strip("[]").split(",")]
#         except ValueError:
#             raise HTTPException(status_code=400, detail="Invalid dimensions format")
        
#         try:
#             offset = [int(i) for i in offset.strip("[]").split(",")]
#         except ValueError:
#             raise HTTPException(status_code=400, detail="Invalid offset format")

#         if len(dimensions) != 2:
#             raise HTTPException(status_code=400, detail="Invalid dimensions")
#         if len(offset) != 2:
#             raise HTTPException(status_code=400, detail="Invalid offset")
        
#         dims = f"{dimensions[0]}x{dimensions[1]}"
#         offs = f"offset{offset[0]}x{offset[1]}"

#         prefix = f"images/{image_id}/crop/{dims}/{offs}/"
#     else: 
#         prefix = f"images/{image_id}/origin/"
        
#     await s3_service.delete_file(prefix + image_name)
#     return {
#         "message": "Image deleted successfully",
#         "filename": image_id,
#         "fileid": image_name
#     } 

def crop_image_from_stream(file_content: bytes, dimensions: list[int], offset: Optional[list[int]] = [0, 0]) -> BytesIO:
    # Open the image using PIL
    image = Image.open(BytesIO(file_content))

    # Calculate the crop box (left, upper, right, lower)
    left = offset[0]
    upper = offset[1]
    right = left + dimensions[0]
    lower = upper + dimensions[1]
    crop_box = (left, upper, right, lower)

    # Crop the image
    cropped_image = image.crop(crop_box)

    # Save the cropped image to a BytesIO object
    cropped_image_stream = BytesIO()
    cropped_image.save(cropped_image_stream, format=image.format)
    cropped_image_stream.seek(0)
    
    return cropped_image_stream