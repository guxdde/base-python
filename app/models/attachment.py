from sqlalchemy import Column, BigInteger, String, DateTime, Integer, ForeignKey, Enum, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as BaseEnum

from app.core.database import Base

class AttachmentTypeEnum(str, BaseEnum):
    """附件类型"""
    FILE = "file" # 文件
    URL = "url"   # url
    OBJECT_STORAGE = "object_storage"   # 对象存储

class Attachments(Base):
    """附件"""

    __tablename__ = "attachments"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键ID')
    type = Column(Enum(AttachmentTypeEnum), nullable=False, comment='附件类型')
    original_filename = Column(String(255), nullable=False, comment='原始文件名')
    stored_filename = Column(String(255), nullable=False, comment='存储文件名')
    file_path = Column(String(255), nullable=True, comment='文件路径')
    file_size = Column(Integer, nullable=True, comment='文件大小')
    mime_type = Column(String(100), nullable=False, comment='MIME类型')
    uploader_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment='上传者ID')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment='更新时间')
    checksum = Column(String(32), comment='校验和', index=True)
    datas = Column(LargeBinary, comment='数据')

    # avatar_user = relationship("User", back_populates="avatar", foreign_keys="[User.avatar_id]")
