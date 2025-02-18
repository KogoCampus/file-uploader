from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from typing import Optional
from PIL import Image
import os
from io import BytesIO
from ..backend.s3 import S3Service
import json

image_router = APIRouter(prefix="/images", tags=["images"])
s3_service = S3Service()

@image_router.post("/crop/{image_id}/{file_name}")
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
    
    if not await s3_service.check_file_id_exists(image_id, "images"):
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
    response = await s3_service.upload_file(cropped_file, file_name, ["crop/", f"{dims}/", f"{offs}"], image_id)
    url = response["url"]

    # update the metadata.json inside images_id/ folder with the new cropped image
    newfile_metadata = await s3_service.get_filedata(f"images/{image_id}/crop/{dims}/{offs}/{file_name}")
    metadata_response = await s3_service.load_metadata(f"images/{image_id}/metadata.json")
    metadata = json.loads(metadata_response["Body"].read())
    if "crop" not in metadata["variants"]:
        metadata["variants"]["crop"] = {}
    metadata["variants"]["crop"][f"{dims}_{offs}"] = newfile_metadata
    await s3_service.save_metadata(image_id, "images", metadata)

    return {
        "file_id": image_id,
        "filename": file_name,
        "url": url,
        "size": file_size,
        "content_type": content_type
    }

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