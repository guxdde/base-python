"""
任务管理 API

提供任务的查询、运行、状态查询等功能
"""
import dramatiq
from fastapi import APIRouter

from app.core.base_endpoint import BaseHTTPEndpoint
from app.core.dramatiq_broker import rabbitmq_broker
from app.core.task_result import TaskResultStore

router = APIRouter()


def _get_actors():
    """获取所有已注册的任务"""
    broker = rabbitmq_broker
    return broker.actors


class TaskListEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        queue = request.query_params.get("queue")
        
        actors = _get_actors()
        tasks = []
        
        for name, actor in actors.items():
            if queue is None or actor.queue_name == queue:
                tasks.append({
                    "name": name,
                    "queue": actor.queue_name,
                    "time_limit": actor.options.get("time_limit"),
                    "max_retries": actor.options.get("max_retries"),
                })
        
        return self.success_response({"items": tasks, "total": len(tasks)})


class TaskDetailEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_name: str):
        actors = _get_actors()
        actor = actors.get(task_name)
        
        if not actor:
            return self.error_response(message=f"Task {task_name} not found")
        
        return self.success_response({
            "name": task_name,
            "queue": actor.queue_name,
            "time_limit": actor.options.get("time_limit"),
            "max_retries": actor.options.get("max_retries"),
            "options": actor.options,
        })


class TaskRunEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        data = await request.json()
        
        task_name = data.get("task_name")
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        queue = data.get("queue")
        
        actors = _get_actors()
        actor = actors.get(task_name)
        
        if not actor:
            return self.error_response(message=f"Task {task_name} not found")
        
        try:
            task_queue = queue or actor.queue_name
            
            message = actor.send(*args, **kwargs)
            
            return self.success_response({
                "task_id": message.message_id,
                "task_name": task_name,
                "queue": task_queue,
                "status": "QUEUED",
            })
        except Exception as e:
            return self.error_response(message=f"Failed to run task: {str(e)}")


class TaskStatusEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_id: str):
        try:
            result = TaskResultStore.get_result(task_id)
            
            if not result:
                return self.success_response({
                    "task_id": task_id,
                    "status": "UNKNOWN",
                    "message": "Task result not found in cache",
                })
            
            return self.success_response({
                "task_id": task_id,
                "status": result.get("status"),
                "result": result.get("result"),
                "error": result.get("error"),
                "created_at": result.get("created_at"),
                "updated_at": result.get("updated_at"),
            })
        except Exception as e:
            return self.error_response(message=f"Failed to get task status: {str(e)}")


class TaskRegisteredEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        actors = _get_actors()
        task_names = list(actors.keys())
        return self.success_response({"items": task_names, "total": len(task_names)})


router.add_route("/", TaskListEndpoint, methods=["GET"])
router.add_route("/register", TaskRegisteredEndpoint, methods=["GET"])
router.add_route("/run", TaskRunEndpoint, methods=["POST"])
router.add_route("/{task_name}", TaskDetailEndpoint, methods=["GET"])
router.add_route("/status/{task_id}", TaskStatusEndpoint, methods=["GET"])
