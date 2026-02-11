from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.base_endpoint import BaseHTTPEndpoint
router = APIRouter()

class HealthEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        # MVP: simple health check
        return self.success_response({"status": "ok"})

router.add_route("/get", HealthEndpoint, methods=["GET"])

