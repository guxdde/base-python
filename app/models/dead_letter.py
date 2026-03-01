from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func

from app.core.database import Base


class DeadLetterStatus:
    PENDING = "pending"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    FAILED = "failed"


class DeadLetterRecord(Base):
    __tablename__ = "dead_letter_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String(36), nullable=False, index=True, comment="Celery task ID")
    task_name = Column(String(255), nullable=False, comment="任务名称")
    
    args = Column(JSON, nullable=True, comment="位置参数")
    kwargs = Column(JSON, nullable=True, comment="关键字参数")
    
    exception = Column(Text, nullable=True, comment="异常信息")
    traceback = Column(Text, nullable=True, comment="完整堆栈")
    
    failed_at = Column(DateTime, nullable=False, default=func.now(), comment="失败时间")
    last_retry_at = Column(DateTime, nullable=True, comment="最后重试时间")
    
    retry_count = Column(Integer, nullable=False, default=0, comment="重试次数")
    max_retries = Column(Integer, nullable=False, default=3, comment="最大重试次数")
    
    status = Column(String(50), nullable=False, default=DeadLetterStatus.PENDING, 
                    index=True, comment="状态: pending/retrying/resolved/failed")
    
    queue = Column(String(100), nullable=True, comment="原始队列")
    worker = Column(String(100), nullable=True, comment="执行worker")
    
    result = Column(Text, nullable=True, comment="任务执行结果")
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DeadLetterRecord(id={self.id}, task_name={self.task_name}, status={self.status})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "args": self.args,
            "kwargs": self.kwargs,
            "exception": self.exception,
            "traceback": self.traceback,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "status": self.status,
            "queue": self.queue,
            "worker": self.worker,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
