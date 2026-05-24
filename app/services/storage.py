import os
import shutil
import uuid
from fastapi import UploadFile
from app.config import settings


class StorageService:
    @staticmethod
    def _generate_unique_filename(filename: str) -> str:
        ext = os.path.splitext(filename)[1]
        return f"{uuid.uuid4()}{ext}"

    async def save_uploaded_file(self, file: UploadFile, folder: str = "uploads") -> str:
        """
        Saves an uploaded file locally and returns its accessible path/url.
        Can be refactored to upload to S3 if AWS settings are provided.
        """
        dest_dir = os.path.join(settings.STATIC_DIR, folder)
        os.makedirs(dest_dir, exist_ok=True)
        
        unique_name = self._generate_unique_filename(file.filename or "file.bin")
        file_path = os.path.join(dest_dir, unique_name)
        
        # Save file asynchronously in chunks
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return the public web path
        # In a real cluster, this would point to a CDN or S3 bucket URL
        return f"/static/{folder}/{unique_name}"

    def save_binary_content(self, content: bytes, filename: str, folder: str = "uploads") -> str:
        """
        Saves a raw byte block to disk. Useful for model downloads from APIs.
        """
        dest_dir = os.path.join(settings.STATIC_DIR, folder)
        os.makedirs(dest_dir, exist_ok=True)
        
        file_path = os.path.join(dest_dir, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(content)
            
        return f"/static/{folder}/{filename}"

    def delete_file(self, file_url: str) -> bool:
        """
        Removes file from disk given its static path.
        """
        if not file_url.startswith("/static/"):
            return False
            
        relative_path = file_url.lstrip("/")
        full_path = os.path.join(os.getcwd(), relative_path)
        
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                return True
            except OSError:
                return False
        return False


storage_service = StorageService()
