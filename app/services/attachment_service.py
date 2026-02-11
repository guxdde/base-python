from sqlalchemy.ext.asyncio import AsyncSession
import os
import hashlib
import aiofiles
from pathlib import Path
from sqlalchemy import select
from sqlalchemy import and_
from fastapi import UploadFile
from typing import Optional
from typing import Tuple
import asyncio

from app.models.attachment import Attachments, AttachmentTypeEnum
from app.models.user import User
from app.core.config import settings


class AttachmentService:
    """附件服务"""

    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.user_id = user.id

    def _compute_checksum(self, file: bytes) -> str:
        # 生成文件checksum
        return hashlib.md5(file).hexdigest()

    @property
    def avatar_upload_dir(self):
        """获取头像上传路径"""
        if settings.attachment.access_type == 'local':
            return os.path.join(Path().resolve(), settings.attachment.avatar_dir)
        return os.path.join(settings.attachment.nginx_url, settings.attachment.avatar_dir)

    @classmethod
    def get_avatar_access_url(cls, filename: str) -> str:
        """获取附件访问URL"""
        avatar_uri = settings.attachment.avatar_dir
        if not avatar_uri.startswith('/'):
            avatar_uri = '/' + avatar_uri
        return os.path.join(avatar_uri, filename)


    async def upload_avatar(self, file: UploadFile, filename: str) -> Tuple[Optional[int], str]:
        """上传用户头像"""
        bin_data = await file.read()
        file_size = len(bin_data)
        mime_type = file.content_type
        max_size = 5 * 1024 * 1024  # 5MB
        if file_size > max_size:
            return None, f"文件大小不能超过5MB，当前大小: {file_size / (1024 * 1024):.2f}MB"
        # 确保头像存储目录存在
        os.makedirs(self.avatar_upload_dir, exist_ok=True)

        checksum = self._compute_checksum(bin_data)
        # 查询重复上传文件
        attachment_query = select(Attachments).where(
            and_(
                Attachments.checksum == checksum,
                Attachments.type == AttachmentTypeEnum.URL,
                Attachments.uploader_id == self.user_id,
                Attachments.mime_type == mime_type,
            )
        )
        attachment_result = await self.db.execute(attachment_query)
        attachment = attachment_result.scalars().first()
        file_extension = filename.split(".")[-1] if "." in filename else "jpg"
        new_filename = f"{checksum}.{file_extension}"
        file_path = os.path.join(self.avatar_upload_dir, new_filename)
        # 检查文件是否已存在
        file_exists = await asyncio.get_event_loop().run_in_executor(
            None, os.path.exists, file_path
        )

        if not file_exists:
            # 异步保存文件
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(bin_data)

        if not attachment:
            attachment = Attachments(
                file_path=file_path,
                file_size=file_size,
                original_filename=filename,
                stored_filename=new_filename,
                mime_type=mime_type,
                type=AttachmentTypeEnum.URL,
                uploader_id=self.user_id,
                checksum=checksum,
            )
            self.db.add(attachment)
            await self.db.commit()
            await self.db.refresh(attachment)
        user = await self.db.get(User, self.user_id)
        user.avatar_id = attachment.id
        await self.db.commit()
        return attachment.id, self.get_avatar_access_url(attachment.stored_filename)
