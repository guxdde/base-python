from fastapi import APIRouter

from app.core.base_endpoint import BaseHTTPEndpoint
from app.core.taskiq import taskiq_app

router = APIRouter()


def _get_all_tasks():
    """获取所有任务"""
    try:
        return taskiq_app.get_all_tasks()
    except Exception:
        return {}


def _find_task(name):
    """查找任务"""
    try:
        return taskiq_app.find_task(name)
    except Exception:
        return None


class TaskListEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        queue = request.query_params.get("queue")

        try:
            task_dict = _get_all_tasks()
            task_list = []
            for task_name, task_func in task_dict.items():
                task_info = {
                    "name": task_name,
                    "queue": getattr(task_func, 'queue', 'default'),
                }

                if queue and task_info['queue'] != queue:
                    continue

                task_list.append(task_info)

            return self.success_response({
                "items": task_list,
                "total": len(task_list),
            })
        except Exception as e:
            return self.error_response(message=f"Failed to get tasks: {str(e)}")


class TaskDetailEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_name: str):
        try:
            task_func = _find_task(task_name)
            if task_func:
                return self.success_response({
                    "name": task_name,
                    "queue": getattr(task_func, 'queue', 'default'),
                })
        except Exception as e:
            return self.error_response(message=f"Failed to get task: {str(e)}")

        return self.error_response(message=f"Task {task_name} not found")


class TaskRunEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        data = await request.json()

        task_name = data.get("task_name")
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        queue = data.get("queue")

        try:
            task_func = _find_task(task_name)

            if not task_func:
                return self.error_response(message=f"Task {task_name} not found")

            send_kwargs = {}
            if queue:
                send_kwargs['queue'] = queue

            task = task_func.kiq(*args, **kwargs, **send_kwargs)

            return self.success_response({
                "task_id": task.task_id,
                "task_name": task_name,
                "status": "PENDING",
            })

        except Exception as e:
            return self.error_response(message=f"Failed to run task: {str(e)}")


class TaskStatusEndpoint(BaseHTTPEndpoint):
    async def get(self, request, task_id: str):
        try:
            from taskiq.result import TaskiqResult

            result = TaskiqResult(task_id)

            status_info = {
                "task_id": task_id,
                "status": result.status,
            }

            if result.is_success:
                status_info["result"] = result.return_value
            elif result.is_err:
                status_info["error"] = str(result.error)

            return self.success_response(status_info)

        except Exception as e:
            return self.error_response(message=f"Failed to get task status: {str(e)}")


class TaskCancelEndpoint(BaseHTTPEndpoint):
    async def post(self, request, task_id: str):
        try:
            return self.success_response({
                "task_id": task_id,
                "status": "CANCELLED",
            })
        except Exception as e:
            return self.error_response(message=f"Failed to cancel task: {str(e)}")


class TaskRegisteredEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        try:
            task_dict = _get_all_tasks()
            task_list = list(task_dict.keys())

            return self.success_response({
                "items": task_list,
                "total": len(task_list),
            })
        except Exception as e:
            return self.error_response(message=f"Failed to get tasks: {str(e)}")


router.add_route("/", TaskListEndpoint, methods=["GET"])
router.add_route("/register", TaskRegisteredEndpoint, methods=["GET"])
router.add_route("/run", TaskRunEndpoint, methods=["POST"])
router.add_route("/{task_name}", TaskDetailEndpoint, methods=["GET"])
router.add_route("/status/{task_id}", TaskStatusEndpoint, methods=["GET"])
router.add_route("/cancel/{task_id}", TaskCancelEndpoint, methods=["POST"])