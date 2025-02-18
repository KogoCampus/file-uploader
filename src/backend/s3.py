import boto3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
from io import BytesIO
from ..config import settings
from uuid import uuid4
from typing import Dict
from ..backend.file_types import ALLOWED_FILE_TYPES
import logging
import asyncio
from pathlib import Path
import json

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.bucket_name = settings.s3_bucket_name
        self.file_staling_jobs: Dict[str, asyncio.Task] = {}
    
    async def start_scheduler(self):
        """
        Start scheduler if not running
        """
        if not scheduler.running:
            scheduler.start()
            logger.info("Scheduler started.")
    
    async def check_file_type(self, file_id: str) -> bool:
        """Check the file_type of the file with the given file_id in S3"""
        for file_type in ALLOWED_FILE_TYPES.values():
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=f"{file_type}/{file_id}/",
                    MaxKeys=1  # at least one exists
                )
                if 'Contents' in response:
                    return file_type
            except ClientError as e:
                raise HTTPException(status_code=500, detail="Failed to check file ID")
        raise HTTPException(status_code=404, detail="File not found in S3")

    async def upload_file(self, file: UploadFile, filename: str, suffix: list[str]=["origin/"], file_id: str = None) -> dict:
        """Upload a file to S3"""
        try:
            # Read the file content into memory
            file_content = await file.read()
            # Convert it to a BytesIO object for the synchronous boto3 method
            file_stream = BytesIO(file_content)

            content_type = file.content_type
            file_type = ALLOWED_FILE_TYPES[content_type]
            
            # Generate a unique file ID if not provided
            if not file_id:
                while True:
                    file_id = str(uuid4())
                    try:
                        await self.check_file_type(file_id)
                    except HTTPException as e:
                        if e.status_code == 404:
                            break  # File ID is unique, break the loop
                        else:
                            raise

            # Generate s3 key using path
            path = [f"{file_id}/"] + suffix + [filename]
            s3_key = str(Path(*path)).lstrip('/')
            final_key = file_type + "/" + s3_key
            
            #upload the file
            self.s3_client.upload_fileobj(
                file_stream,
                self.bucket_name,
                final_key,
                ExtraArgs={
                    "ContentType": content_type
                }
            )
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{final_key}"

            return {
                "file_id": file_id,
                "url": url,
            }
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload file")

    async def save_filedata(self, file_id: str, file_type: str, filedata: dict):
        """
        Save the filedata.json file back to S3.
        """
        key = f"{file_type}/{file_id}/filedata.json"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(filedata, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

    async def get_metadata(self, file_key: str) -> dict:
        filedata = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
        return {
            "size": filedata["ContentLength"],
            "content_type": filedata["ContentType"],
            "last_modified": filedata["LastModified"].isoformat()
        }

    async def load_filedata(self, file_id: str) -> dict:
        try:
            file_type = await self.check_file_type(file_id)
            return self.s3_client.get_object(Bucket=self.bucket_name, Key=f"{file_type}/{file_id}/filedata.json")
        except ClientError as e:
            raise HTTPException(status_code=500, detail="Failed to load filedata")
        except HTTPException as http_exc:
            raise http_exc # 404

    async def delete_file(self, file_id: str):
        """Delete a file from S3"""
        file_type = await self.check_file_type(file_id)
        prefix = f"{file_type}/{file_id}/"
        try:
                # List all objects under the prefix (all file variants)
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

            # Extract object keys to delete
            keys_to_delete = [{'Key': obj['Key']} for obj in response.get('Contents', [])]

            if not keys_to_delete:
                raise HTTPException(status_code=404, detail="File not found")  # Shouldn't happen, but just in case

            # Perform bulk delete
            delete_response = self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': keys_to_delete}
            )
            # Check for errors in the deletion response
            if 'Errors' in delete_response:
                raise HTTPException(status_code=500, detail="Failed to delete some files")
        except ClientError as e:
            raise HTTPException(status_code=500, detail="Failed to delete folder")
    
    async def schedule_staling(self, file_id: str, delay_minutes: int = 20):
        """
        Schedule a deletion of a file after delay_mintues
        """
        async def wait_and_delete():
            await asyncio.sleep(delay_minutes * 60)  # wait for delay_minutes
            if file_id in self.file_staling_jobs:  # if file_id is still in staling jobs after delay
                try:
                    await self.delete_file(file_id)
                    logger.info(f"Scheduled deletion of file: {file_id} completeted")
                except Exception as e:
                    logger.error(f"Error deleting file {file_id}: {e}")
                finally:
                    self.file_staling_jobs.pop(file_id, None)
        
        # update the task for the file id
        self.file_staling_jobs[file_id] = asyncio.create_task(wait_and_delete())

    async def persist_file(self, file_id: str):
        """
        Persist the file.
        """
        if file_id in self.file_staling_jobs:
            self.file_staling_jobs[file_id].cancel()  # cancel auto delete
            self.file_staling_jobs.pop(file_id, None)
        else:
            raise HTTPException(status_code=404, detail="File ID not found in staling jobs")
