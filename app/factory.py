from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_databases, close_databases
from app.core.redis import redis_service
from app.core.milvus import milvus_service
from app.core.dramatiq_broker import initialize as init_dramatiq

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("应用启动中...")
    
    await init_databases()
    print("多数据库连接初始化完成")

    await redis_service.init_redis()
    print("Redis连接初始化完成")

    # 初始化 Milvus
    await milvus_service.connect()
    await milvus_service.create_collection_if_not_exists()
    print("Milvus 连接初始化完成")

    # await register_all()  # 扫描并注册任务
    # await get_scheduler()  # 确保调度器启动

    init_dramatiq()
    print("Dramatiq Broker 初始化完成")
    
    yield

    print("应用关闭中...")
    
    await close_databases()
    print("所有数据库连接已关闭")
    
    await redis_service.close_redis()
    print("Redis连接已关闭")

    # 关闭 Milvus 连接
    await milvus_service.close()
    print("Milvus 连接已关闭")


def create_app() -> FastAPI:
    """应用工厂函数"""
    app = FastAPI(
        title="FastAPI Factory Pattern Project",
        description="A FastAPI project using factory pattern with JWT, SQLAlchemy async, Redis and Dramatiq",
        version="1.0.0",
        debug=True,
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    
    setup_routes(app)
    if settings.attachment.access_type == 'local':
        app.mount("/avatars", StaticFiles(directory="avatars"), name="avatars")
    return app


def setup_routes(app: FastAPI):
    """设置路由"""
    from app.api import router as api_router
    
    app.include_router(
        api_router,
        prefix="/api",
        tags=["API"]
    )


from starlette.staticfiles import StaticFiles
