import logging
from typing import Optional

from fastapi import APIRouter

from app.api.response import ResponseCode
from app.core.base_endpoint import BaseHTTPEndpoint
from app.core.taskiq import QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW
from app.tasks.scheduled_tasks import io_blocking_task

router = APIRouter()
_logger = logging.getLogger(__name__)


def _get_all_tasks():
    """获取所有已注册任务"""
    return task_map


def _find_task(name):
    """查找任务"""
    return task_map.get(name)


task_map = {
    "io_blocking_task": io_blocking_task,
}


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
            return self.error_response(ResponseCode.server_error, message=f"Failed to get tasks: {str(e)}")


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
            return self.error_response(ResponseCode.server_error, message=f"Failed to get task: {str(e)}")

        return self.error_response(ResponseCode.not_found, message=f"Task {task_name} not found")


class TaskRunEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        data = await request.json()

        task_name = data.get("task_name")
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        queue = data.get("queue")
        priority = data.get("priority")

        try:
            task_func = _find_task(task_name)

            if not task_func:
                return self.error_response(message=f"Task {task_name} not found")

            send_labels = {}
            if queue:
                send_labels["queue_name"] = queue
            if priority is not None:
                send_labels["priority"] = priority

            kicker = task_func.kicker()
            if send_labels:
                kicker = kicker.with_labels(**send_labels)

            task = await kicker.kiq(*args, **kwargs)
            _logger.info(
                f"Task dispatched: task_id={task.task_id}, task_name={task_name}, "
                f"queue={queue or 'default'}, priority={priority}"
            )

            return self.success_response({
                "task_id": task.task_id,
                "task_name": task_name,
                "queue": queue or QUEUE_DEFAULT,
                "priority": priority,
                "status": "PENDING",
            })

        except Exception as e:
            _logger.exception(f"Failed to run task {task_name}: {e}")
            return self.error_response(ResponseCode.server_error, message=f"Failed to run task: {str(e)}")


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
            return self.error_response(ResponseCode.server_error, message=f"Failed to get task status: {str(e)}")


class TaskCancelEndpoint(BaseHTTPEndpoint):
    async def post(self, request, task_id: str):
        try:
            return self.success_response({
                "task_id": task_id,
                "status": "CANCELLED",
            })
        except Exception as e:
            return self.error_response(ResponseCode.server_error, message=f"Failed to cancel task: {str(e)}")


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
            return self.error_response(ResponseCode.server_error, message=f"Failed to get tasks: {str(e)}")


class BatchTaskRunEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        task_map = {
            "io_blocking_task": io_blocking_task,
        }

        data = await request.json()
        task_name = data.get("task_name", "io_blocking_task")
        task_func = task_map.get(task_name)

        if not task_func:
            return self.error_response(ResponseCode.not_found, message=f"Task {task_name} not found")

        count = data.get("count", 10)

        task_ids = []
        errors = []

        for i in range(count):
            try:
                task = await task_func.kiq(i + 1)
                task_ids.append(task.task_id)

                if i < 3 or i == count - 1:
                    _logger.debug(
                        f"  [{i+1}/{count}] Dispatched task_id={task.task_id}"
                    )
            except Exception as e:
                error_msg = f"Task {i+1} failed: {str(e)}"
                _logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        _logger.info(
            f"Batch complete: success={len(task_ids)}, failed={len(errors)}"
        )

        return self.success_response({
            "task_name": task_name,
            "task_ids": task_ids,
            "count": len(task_ids),
            "errors": errors if errors else None,
        })


router.add_route("/", TaskListEndpoint, methods=["GET"])
router.add_route("/register", TaskRegisteredEndpoint, methods=["GET"])
router.add_route("/run", TaskRunEndpoint, methods=["POST"])
router.add_route("/batch", BatchTaskRunEndpoint, methods=["POST"])
router.add_route("/{task_name}", TaskDetailEndpoint, methods=["GET"])
router.add_route("/status/{task_id}", TaskStatusEndpoint, methods=["GET"])
router.add_route("/cancel/{task_id}", TaskCancelEndpoint, methods=["POST"])