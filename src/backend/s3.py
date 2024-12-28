import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
from ..config import settings
import logging
from typing import BinaryIO, List

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

    async def upload_file(self, file: BinaryIO, filename: str) -> str:
        """Upload a file to S3"""
        try:
            self.s3_client.upload_fileobj(file, self.bucket_name, filename)
            return f"https://{self.bucket_name}.s3.amazonaws.com/{filename}"
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload file")

    async def delete_file(self, filename: str) -> bool:
        """Delete a file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=filename)
            return True
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete file")

    async def get_file_url(self, filename: str) -> str:
        """Get a presigned URL for a file"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': filename},
                ExpiresIn=3600  # URL expires in 1 hour
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise HTTPException(status_code=404, detail="File not found")

    async def list_files(self, prefix: str = "") -> List[dict]:
        """List all files in the bucket with optional prefix"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat()
                })
            return files
        except ClientError as e:
            logger.error(f"Error listing files from S3: {e}")
            raise HTTPException(status_code=500, detail="Failed to list files") 