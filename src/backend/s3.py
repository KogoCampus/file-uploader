import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
from io import BytesIO
from ..config import settings
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.bucket_name = settings.s3_bucket_name
    
    async def check_image_id_exists(self, image_id: str) -> bool:
        """Check if an image with the given image_id exists in S3"""
        prefix = f"images/{image_id}/"
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1  # at least one exists
            )
            return 'Contents' in response  # return truㄷ if such file exists
        except ClientError as e:
            logger.error(f"Error checking for imageId {image_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to check image ID")

    async def upload_file(self, file: UploadFile, file_id: str, filename: str, suffix: list[str]=["origin/"]) -> str:
        """Upload a file to S3"""
        try:
            # Read the file content into memory (async)
            file_content = await file.read()
            
            # Convert it to a BytesIO object for the synchronous boto3 method
            file_stream = BytesIO(file_content)
            content_type = file.content_type

            # Generate s3 key using path
            path = [f"{file_id}/"] + suffix + [filename]
            s3_key = str(Path(*path)).lstrip('/')

             # Create the object key using imageId
            if content_type.startswith('image/'):  # Checks if the content type starts with 'image/'
                file_type = "images/"
            elif content_type.startswith('video/'):  # Checks if the content type starts with 'video/'
                file_type = "videos/"
            else:
                raise HTTPException(status_code=400, detail="Unsupported file type")
            final_key = file_type + s3_key

            #upload the file
            self.s3_client.upload_fileobj(
                file_stream,
                self.bucket_name,
                final_key,
                ExtraArgs={
                    "ContentType": content_type
                }
            )
            return f"https://{self.bucket_name}.s3.amazonaws.com/{final_key}"
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload file")

    async def save_metadata(self, image_id: str, metadata: dict):
        """
        Save the metadata.json file back to S3.
        """
        key = f"images/{image_id}/metadata.json"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(metadata, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

    async def get_filedata(self, file_key: str) -> dict:
        filedata = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
        return {
            "size": filedata["ContentLength"],
            "content_type": filedata["ContentType"],
            "last_modified": filedata["LastModified"].isoformat()
        }

    async def load_metadata(self, file_key: str) -> dict:
        return self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)

    async def delete_file(self, file_id: str):
        """Delete a file from S3"""
        prefix = f"images/{file_id}/"
        try:
            # List all objects with the given prefix
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' not in response:
                raise HTTPException(status_code=404, detail="No files found in the specified folder")
            # Collect all keys to delete
            keys_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]

            # Perform bulk delete
            delete_response = self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': keys_to_delete}
            )
            # Check for errors in the deletion response
            if 'Errors' in delete_response:
                logger.error(f"Errors occurred during deletion: {delete_response['Errors']}")
                raise HTTPException(status_code=500, detail="Failed to delete some or all files")

            logger.info(f"Successfully deleted folder: {prefix}")
        except ClientError as e:
            logger.error(f"Error deleting folder {prefix}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete folder")