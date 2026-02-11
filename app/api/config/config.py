from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.base_endpoint import BaseHTTPEndpoint

router = APIRouter()


class ConfigEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        return self.success_response({
            "config": {
                "databases": ["postgres_main"],
                "redis": {"url": "redis://localhost:6379/0"},
                "celery": {"broker": "amqp://guest@localhost//", "backend": "redis://localhost:6379/0"}
            }
        })

router.add_route("/get", ConfigEndpoint, methods=["GET"])
