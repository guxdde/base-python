import json
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.response import ResponseCode, error_massage, success_response
from app.core import get_redis
from app.core.database import get_db, get_db_session
from app.utils import ModelClient
import logging

_logger = logging.getLogger(__name__)


class BaseHTTPEndpoint(HTTPEndpoint):
    """基础HTTP端点类，提供数据库会话管理"""

    @asynccontextmanager
    async def get_db_session(self, db_type: str = "default"):
        """获取数据库会话的上下文管理器

        Args:
            db_type: 数据库类型，可选值: "default", "news", "market", "ai_interpretation"

        这个方法只在需要时创建数据库会话，避免资源浪费
        使用方式：
        async with self.get_db_session("ai_interpretation") as db:
            # 使用数据库会话
            pass
        """
        if db_type == "default":
            # 兼容原有代码，使用依赖注入方式的默认数据库
            async for session in get_db():
                try:
                    yield session
                except Exception as ex:
                    _logger.error("Error in db session:%s"%str(ex), exc_info=True)
                    # get_db() 已经处理了回滚，这里不需要重复处理
                    raise
        else:
            # 使用新的多数据库支持
            async with get_db_session(db_type) as session:
                yield session

    async def parse_json_body(self, request: Request) -> Dict[str, Any]:
        """解析JSON请求体"""
        try:
            body = await request.body()
            if not body:
                return {}
            return json.loads(body)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format")

    def error_response(
        self, code: ResponseCode, message: Optional[str] = None
    ) -> JSONResponse:
        """创建错误响应

        Args:
            code: 错误代码
            message: 自定义错误消息，如果为None则使用默认消息

        Returns:
            JSONResponse: 格式化的错误响应，始终返回HTTP 200状态码
        """
        error_msg = message if message else error_massage.get(code.value, "")
        return JSONResponse(
            content={"code": code.value, "message": error_msg}, status_code=200
        )

    def success_response(
        self, data: Any, status_code: int = status.HTTP_200_OK
    ) -> JSONResponse:
        """创建成功响应"""

        custom_encoder = {Decimal: lambda d: str(d)}
        encoded_data = jsonable_encoder(
            {"code": ResponseCode.normal.value, "message": "ok", "response": data},
            custom_encoder=custom_encoder,
        )
        return JSONResponse(content=encoded_data, status_code=status_code)




