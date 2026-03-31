"""
Dead Letter API

提供失败任务的查看、重试、解决等功能
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_endpoint import BaseHTTPEndpoint
from app.core.database import dbm
from app.core.dead_letter import DeadLetterManager
from app.core.dramatiq_broker import get_broker

router = APIRouter()


async def get_db_session():
    session = await dbm.get_session()
    try:
        yield session
    finally:
        await session.close()


class DeadLetterListEndpoint(BaseHTTPEndpoint):
    async def get(self, request, db: AsyncSession = Depends(get_db_session)):
        status = request.query_params.get("status")
        task_name = request.query_params.get("task_name")
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        
        manager = DeadLetterManager(db)
        
        if status:
            records = await manager.list_all(
                status=status,
                task_name=task_name,
                limit=limit,
                offset=offset
            )
        else:
            records = await manager.list_pending(
                limit=limit,
                offset=offset,
                task_name=task_name
            )
        
        return self.success_response({
            "items": [r.to_dict() for r in records],
            "limit": limit,
            "offset": offset,
        })


class DeadLetterDetailEndpoint(BaseHTTPEndpoint):
    async def get(self, request, record_id: int, db: AsyncSession = Depends(get_db_session)):
        manager = DeadLetterManager(db)
        record = await manager.get_by_id(record_id)
        
        if not record:
            return self.error_response(code=404, message="Dead letter record not found")
        
        return self.success_response(record.to_dict())


class DeadLetterRetryEndpoint(BaseHTTPEndpoint):
    async def post(self, request, record_id: int, db: AsyncSession = Depends(get_db_session)):
        data = await request.json() if request.body() else {}
        queue = data.get("queue")
        
        manager = DeadLetterManager(db)
        record = await manager.get_by_id(record_id)
        
        if not record:
            return self.error_response(message="Dead letter record not found")
        
        try:
            broker = get_broker()
            actors = broker.actors
            actor = actors.get(record.task_name)
            
            if not actor:
                return self.error_response(message=f"Task {record.task_name} not found")
            
            task_queue = queue or record.queue or "default"
            message = actor.send(*record.args, **record.kwargs)
            
            record.status = "retrying"
            record.retry_count += 1
            from datetime import datetime
            record.last_retry_at = datetime.utcnow()
            await db.commit()
            
            return self.success_response({
                "message": "Task retried successfully",
                "new_task_id": message.message_id
            })
        except Exception as e:
            return self.error_response(message=f"Failed to retry task: {str(e)}")


class DeadLetterResolveEndpoint(BaseHTTPEndpoint):
    async def post(self, request, record_id: int, db: AsyncSession = Depends(get_db_session)):
        data = await request.json() if request.body() else {}
        result = data.get("result")
        
        manager = DeadLetterManager(db)
        success = await manager.mark_resolved(record_id, result=result)
        
        if success:
            return self.success_response({"message": "Dead letter marked as resolved"})
        else:
            return self.error_response(message="Dead letter record not found")


class DeadLetterDeleteEndpoint(BaseHTTPEndpoint):
    async def delete(self, request, record_id: int, db: AsyncSession = Depends(get_db_session)):
        manager = DeadLetterManager(db)
        success = await manager.delete(record_id)
        
        if success:
            return self.success_response({"message": "Dead letter deleted"})
        else:
            return self.error_response(message="Dead letter record not found")


class DeadLetterStatsEndpoint(BaseHTTPEndpoint):
    async def get(self, request, db: AsyncSession = Depends(get_db_session)):
        manager = DeadLetterManager(db)
        counts = await manager.count_by_status()
        
        return self.success_response(counts)


router.add_route("/", DeadLetterListEndpoint, methods=["GET"])
router.add_route("/stats", DeadLetterStatsEndpoint, methods=["GET"])
router.add_route("/{record_id}", DeadLetterDetailEndpoint, methods=["GET"])
router.add_route("/{record_id}/retry", DeadLetterRetryEndpoint, methods=["POST"])
router.add_route("/{record_id}/resolve", DeadLetterResolveEndpoint, methods=["POST"])
router.add_route("/{record_id}", DeadLetterDeleteEndpoint, methods=["DELETE"])
