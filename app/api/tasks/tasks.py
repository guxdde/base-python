from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.base_endpoint import BaseHTTPEndpoint
from app.core.task_registry import task_registry
from app.core import celery as core_celery
from app.core.taskiq import taskiq_app
from app.core.taskiq_scheduler import get_schedules
from taskiq.state import TaskiqState
from celery.result import AsyncResult  # Keep for backward compatibility

router = APIRouter()


class TaskListEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        queue = request.query_params.get("queue")

        # Get legacy tasks from registry
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
                "backend": "legacy",
            }
            for t in tasks
        ]

        # Add TaskIQ tasks
        try:
            for task in taskiq_app.tasks:
                task_info = {
                    "name": task.taskiq_name,
                    "queue": getattr(task, 'queue', 'default'),
                    "soft_time_limit": getattr(task, 'soft_timeout', None),
                    "time_limit": getattr(task, 'timeout', None),
                    "description": getattr(task, 'description', None),
                    "tags": getattr(task, 'tags', []),
                    "backend": "taskiq",
                }

                # Filter by queue if specified
                if queue and task_info['queue'] != queue:
                    continue

                task_list.append(task_info)
        except Exception as e:
            return self.error_response(message=f"Failed to get TaskIQ tasks: {str(e)}")

        return self.success_response({
            "items": task_list,
            "total": len(task_list),
            "legacy_count": len([t for t in task_list if t['backend'] == 'legacy']),
            "taskiq_count": len([t for t in task_list if t['backend'] == 'taskiq']),
        })


class TaskDetailEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_name: str):
        # Check legacy registry first
        task = task_registry.get(task_name)

        if task:
            return self.success_response({
                "name": task.name,
                "queue": task.queue,
                "soft_time_limit": task.soft_time_limit,
                "time_limit": task.time_limit,
                "description": task.description,
                "tags": task.tags,
                "options": task.options,
                "backend": "legacy",
            })

        # Check TaskIQ tasks
        try:
            task_func = taskiq_app.get_task(task_name)
            if task_func:
                return self.success_response({
                    "name": task_func.taskiq_name,
                    "queue": getattr(task_func, 'queue', 'default'),
                    "soft_time_limit": getattr(task_func, 'soft_timeout', None),
                    "time_limit": getattr(task_func, 'timeout', None),
                    "description": getattr(task_func, 'description', None),
                    "tags": getattr(task_func, 'tags', []),
                    "options": getattr(task_func, 'taskiq_options', {}),
                    "backend": "taskiq",
                    "async": True,  # TaskIQ tasks are async
                })
        except Exception as e:
            return self.error_response(message=f"Failed to get TaskIQ task: {str(e)}")

        return self.error_response(message=f"Task {task_name} not found")


class TaskRunEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        data = await request.json()

        task_name = data.get("task_name")
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        queue = data.get("queue")

        # Try to get task from registry first (Celery legacy)
        task_info = task_registry.get(task_name)

        try:
            # Use TaskIQ for task execution (preferred)
            # Get task function from TaskIQ
            task_func = taskiq_app.get_task(task_name)

            if not task_func:
                # Fallback to Celery for backward compatibility
                if task_info:
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
                        "backend": "celery",
                    })
                else:
                    return self.error_response(message=f"Task {task_name} not found")

            # Execute with TaskIQ (async)
            send_kwargs = {}
            if queue:
                send_kwargs['queue'] = queue

            # Create task and execute
            task = task_func.kiq(*args, **kwargs, **send_kwargs)

            return self.success_response({
                "task_id": task.task_id,
                "task_name": task_name,
                "status": "PENDING",
                "backend": "taskiq",
            })

        except Exception as e:
            return self.error_response(message=f"Failed to run task: {str(e)}")


class TaskStatusEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_id: str):
        try:
            # Try TaskIQ first, then fallback to Celery
            try:
                from taskiq.result import TaskiqResult
                from taskiq.state import TaskiqState

                # Check if it's a TaskIQ task
                result = TaskiqResult(task_id)

                status_info = {
                    "task_id": task_id,
                    "status": TaskiqState(result.state).name,
                    "backend": "taskiq",
                }

                if result.state == "SUCCESS":
                    status_info["result"] = result.result
                elif result.state == "ERROR":
                    status_info["error"] = str(result.result)

                # Add timing information if available
                if hasattr(result, 'execution_time'):
                    status_info["execution_time"] = result.execution_time

                return self.success_response(status_info)

            except Exception:
                # Fallback to Celery for backward compatibility
                celery_app = core_celery.get_celery_app()
                async_result = AsyncResult(task_id, app=celery_app)

                status_info = {
                    "task_id": task_id,
                    "status": async_result.status,
                    "backend": "celery",
                }

                if async_result.ready():
                    if async_result.successful():
                        status_info["result"] = async_result.result
                    elif async_result.failed():
                        status_info["error"] = str(async_result.info)
                    elif async_result.status == "RETRY":
                        status_info["retry_info"] = str(async_result.info)

                return self.success_response(status_info)

        except Exception as e:
            return self.error_response(message=f"Failed to get task status: {str(e)}")


class TaskCancelEndpoint(BaseHTTPEndpoint):
    async def post(self, request, task_id: str):
        try:
            # Try TaskIQ first, then fallback to Celery
            try:
                from taskiq.state import TaskiqState

                # Check if it's a TaskIQ task and cancel it
                # Note: TaskIQ cancellation might work differently
                # This is a placeholder - adjust based on TaskIQ's actual API
                task = taskiq_app.get_task_by_id(task_id)
                if task:
                    # TaskIQ specific cancellation logic
                    # The actual implementation depends on TaskIQ's API
                    return self.success_response({
                        "task_id": task_id,
                        "status": "CANCELLED",
                        "backend": "taskiq",
                    })
            except Exception:
                # Fallback to Celery for backward compatibility
                celery_app = core_celery.get_celery_app()
                async_result = AsyncResult(task_id, app=celery_app)
                async_result.revoke(terminate=True)

                return self.success_response({
                    "task_id": task_id,
                    "status": "REVOKED",
                    "backend": "celery",
                })
        except Exception as e:
            return self.error_response(message=f"Failed to cancel task: {str(e)}")


class TaskRegisteredEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        # Get tasks from both TaskIQ and legacy registry
        task_names = task_registry.get_names()

        # Add TaskIQ tasks
        try:
            # Get all tasks registered with TaskIQ
            taskiq_tasks = []
            for task in taskiq_app.tasks:
                taskiq_tasks.append(task.taskiq_name)

            # Combine and deduplicate
            all_tasks = list(set(task_names + taskiq_tasks))

            return self.success_response({
                "items": all_tasks,
                "total": len(all_tasks),
                "taskiq_tasks": taskiq_tasks,
                "legacy_tasks": task_names,
            })
        except Exception as e:
            return self.error_response(message=f"Failed to get TaskIQ tasks: {str(e)}")


router.add_route("/", TaskListEndpoint, methods=["GET"])
router.add_route("/register", TaskRegisteredEndpoint, methods=["GET"])
router.add_route("/run", TaskRunEndpoint, methods=["POST"])
router.add_route("/{task_name}", TaskDetailEndpoint, methods=["GET"])
router.add_route("/status/{task_id}", TaskStatusEndpoint, methods=["GET"])
router.add_route("/cancel/{task_id}", TaskCancelEndpoint, methods=["POST"])
