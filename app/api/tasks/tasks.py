from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.base_endpoint import BaseHTTPEndpoint
from app.core.task_registry import task_registry
from app.core import celery as core_celery
from celery.result import AsyncResult

router = APIRouter()


class TaskListEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        queue = request.query_params.get("queue")
        
        if queue:
            tasks = task_registry.get_by_queue(queue)
        else:
            tasks = task_registry.all()
        
        task_list = [
            {
                "name": t.name,
                "queue": t.queue,
                "soft_time_limit": t.soft_time_limit,
                "time_limit": t.time_limit,
                "description": t.description,
                "tags": t.tags,
            }
            for t in tasks
        ]
        return self.success_response({"items": task_list, "total": len(task_list)})


class TaskDetailEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_name: str):
        task = task_registry.get(task_name)
        
        if not task:
            return self.error_response(message=f"Task {task_name} not found")
        
        return self.success_response({
            "name": task.name,
            "queue": task.queue,
            "soft_time_limit": task.soft_time_limit,
            "time_limit": task.time_limit,
            "description": task.description,
            "tags": task.tags,
            "options": task.options,
        })


class TaskRunEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        data = await request.json()
        
        task_name = data.get("task_name")
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        queue = data.get("queue")
        
        task_info = task_registry.get(task_name)
        if not task_info:
            return self.error_response(message=f"Task {task_name} not found")
        
        try:
            celery_app = core_celery.get_celery_app()
            
            send_kwargs = {}
            if queue:
                send_kwargs['queue'] = queue
            elif task_info.queue:
                send_kwargs['queue'] = task_info.queue
            
            result = celery_app.send_task(
                task_name,
                args=args,
                kwargs=kwargs,
                **send_kwargs
            )
            
            return self.success_response({
                "task_id": result.id,
                "task_name": task_name,
                "status": "PENDING",
            })
        except Exception as e:
            return self.error_response(message=f"Failed to run task: {str(e)}")


class TaskStatusEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_id: str):
        try:
            celery_app = core_celery.get_celery_app()
            async_result = AsyncResult(task_id, app=celery_app)
            
            return self.success_response({
                "task_id": task_id,
                "status": async_result.status,
                "result": async_result.result if async_result.ready() else None,
                "info": str(async_result.info) if async_result.info else None,
            })
        except Exception as e:
            return self.error_response(message=f"Failed to get task status: {str(e)}")


class TaskCancelEndpoint(BaseHTTPEndpoint):
    async def post(self, request, task_id: str):
        try:
            celery_app = core_celery.get_celery_app()
            async_result = AsyncResult(task_id, app=celery_app)
            async_result.revoke(terminate=True)
            
            return self.success_response({
                "task_id": task_id,
                "status": "REVOKED",
            })
        except Exception as e:
            return self.error_response(message=f"Failed to revoke task: {str(e)}")


class TaskRegisteredEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        task_names = task_registry.get_names()
        return self.success_response({"items": task_names, "total": len(task_names)})


router.add_route("/", TaskListEndpoint, methods=["GET"])
router.add_route("/register", TaskRegisteredEndpoint, methods=["GET"])
router.add_route("/run", TaskRunEndpoint, methods=["POST"])
router.add_route("/{task_name}", TaskDetailEndpoint, methods=["GET"])
router.add_route("/status/{task_id}", TaskStatusEndpoint, methods=["GET"])
router.add_route("/cancel/{task_id}", TaskCancelEndpoint, methods=["POST"])
