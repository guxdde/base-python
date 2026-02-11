from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.base_endpoint import BaseHTTPEndpoint

router = APIRouter()

TASK_REGISTRY = {}


class TaskRegisterEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        data = await request.json()
        name = data.get("name") if isinstance(data, dict) else None
        if not name:
            return self.error_response()
        TASK_REGISTRY[name] = {"name": name}
        return self.success_response({"registered": name})

class TaskRunEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        data = await request.json()
        # placeholder behavior
        return self.success_response({"task_id": "mock-task-id"})

class TaskStatusEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        # path param not easily captured here; provide generic response
        return self.success_response({"task_id": request.path_params.get("task_id"), "status": "PENDING"})

class TasksRegisteredEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        return self.success_response(list(TASK_REGISTRY.keys()))


router.add_route("/register", TaskRegisterEndpoint, methods=["POST"])
router.add_route("/run", TaskRunEndpoint, methods=["POST"])
router.add_route("/status", TaskStatusEndpoint, methods=["GET"])
router.add_route("/registered", TasksRegisteredEndpoint, methods=["GET"])
