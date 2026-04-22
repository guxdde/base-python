import logging
from datetime import datetime
from typing import Optional, List, Any, Dict
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter import DeadLetterRecord, DeadLetterStatus

logger = logging.getLogger(__name__)


class DeadLetterManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def save_failure(
        self,
        task_id: str,
        task_name: str,
        args: tuple = None,
        kwargs: dict = None,
        exception: str = None,
        traceback: str = None,
        queue: str = None,
        worker: str = None,
        max_retries: int = 3,
    ) -> DeadLetterRecord:
        record = DeadLetterRecord(
            task_id=task_id,
            task_name=task_name,
            args=list(args) if args else [],
            kwargs=kwargs or {},
            exception=exception,
            traceback=traceback,
            failed_at=datetime.utcnow(),
            retry_count=0,
            max_retries=max_retries,
            status=DeadLetterStatus.PENDING,
            queue=queue,
            worker=worker,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        logger.info(f"Dead letter record saved: {task_id} - {task_name}")
        return record

    async def get_by_id(self, record_id: int) -> Optional[DeadLetterRecord]:
        result = await self.db.execute(
            select(DeadLetterRecord).where(DeadLetterRecord.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_by_task_id(self, task_id: str) -> Optional[DeadLetterRecord]:
        result = await self.db.execute(
            select(DeadLetterRecord).where(DeadLetterRecord.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_pending(
        self, 
        limit: int = 100, 
        offset: int = 0,
        task_name: str = None
    ) -> List[DeadLetterRecord]:
        query = select(DeadLetterRecord).where(
            DeadLetterRecord.status == DeadLetterStatus.PENDING
        )
        
        if task_name:
            query = query.where(DeadLetterRecord.task_name == task_name)
        
        query = query.order_by(desc(DeadLetterRecord.failed_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_all(
        self,
        status: Optional[str] = None,
        task_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DeadLetterRecord]:
        query = select(DeadLetterRecord)
        
        conditions = []
        if status:
            conditions.append(DeadLetterRecord.status == status)
        if task_name:
            conditions.append(DeadLetterRecord.task_name == task_name)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(DeadLetterRecord.failed_at))
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self) -> Dict[str, int]:
        from sqlalchemy import func
        
        result = await self.db.execute(
            select(DeadLetterRecord.status, func.count(DeadLetterRecord.id))
            .group_by(DeadLetterRecord.status)
        )
        counts = {}
        for status, count in result.all():
            counts[status] = count
        return counts

    async def retry(
        self, 
        record_id: int, 
        celery_app=None,
        queue: Optional[str] = None,
    ) -> Optional[str]:
        return await self.retry_taskiq(record_id, taskiq_app=None, queue=queue)

    async def retry_taskiq(
        self, 
        record_id: int, 
        taskiq_app=None,
        queue: Optional[str] = None,
    ) -> Optional[str]:
        record = await self.get_by_id(record_id)
        if not record:
            logger.warning(f"Dead letter record not found: {record_id}")
            return None
        
        if record.status == DeadLetterStatus.RESOLVED:
            logger.warning(f"Dead letter record already resolved: {record_id}")
            return None
        
        if record.retry_count >= record.max_retries:
            record.status = DeadLetterStatus.FAILED
            await self.db.commit()
            logger.warning(f"Dead letter record exceeded max retries: {record_id}")
            return None
        
        try:
            record.status = DeadLetterStatus.RETRYING
            record.retry_count += 1
            record.last_retry_at = datetime.utcnow()
            await self.db.commit()
            
            task_queue = queue or record.queue
            
            if taskiq_app:
                task_func = taskiq_app.find_task(record.task_name)
                if task_func:
                    task = task_func.kiq(
                        *record.args,
                        **record.kwargs,
                        queue=task_queue,
                    )
                    logger.info(f"Task retried: {record.task_name}, new task_id: {task.task_id}")
                    return task.task_id
                else:
                    logger.error(f"TaskIQ task not found: {record.task_name}")
                    record.status = DeadLetterStatus.PENDING
                    await self.db.commit()
                    return None
            else:
                logger.error("TaskIQ app not available for retry")
                record.status = DeadLetterStatus.PENDING
                await self.db.commit()
                return None
                
        except Exception as e:
            logger.exception(f"Failed to retry task: {record_id}")
            record.status = DeadLetterStatus.PENDING
            await self.db.commit()
            return None

    async def mark_resolved(self, record_id: int, result: str = None) -> bool:
        record = await self.get_by_id(record_id)
        if not record:
            return False
        
        record.status = DeadLetterStatus.RESOLVED
        if result:
            record.result = result
        await self.db.commit()
        logger.info(f"Dead letter marked as resolved: {record_id}")
        return True

    async def mark_failed(self, record_id: int) -> bool:
        record = await self.get_by_id(record_id)
        if not record:
            return False
        
        record.status = DeadLetterStatus.FAILED
        await self.db.commit()
        logger.info(f"Dead letter marked as failed: {record_id}")
        return True

    async def delete(self, record_id: int) -> bool:
        record = await self.get_by_id(record_id)
        if not record:
            return False
        
        await self.db.delete(record)
        await self.db.commit()
        logger.info(f"Dead letter deleted: {record_id}")
        return True

    async def delete_resolved(self, days: int = 30) -> int:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(DeadLetterRecord).where(
                and_(
                    DeadLetterRecord.status == DeadLetterStatus.RESOLVED,
                    DeadLetterRecord.updated_at < cutoff_date
                )
            )
        )
        records = result.scalars().all()
        
        for record in records:
            await self.db.delete(record)
        
        await self.db.commit()
        logger.info(f"Deleted {len(records)} resolved dead letters older than {days} days")
        return len(records)
