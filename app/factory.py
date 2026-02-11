from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_databases, close_databases
from app.core.redis import redis_service
from starlette.staticfiles import StaticFiles
# from app.core.scheduler import get_scheduler
# from app.jobs import register_all

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    print("应用启动中...")
    
    # 初始化多数据库连接
    await init_databases()
    print("多数据库连接初始化完成")
    
    # # 初始化数据库表（如果需要）
    # await init_db()
    # print("数据库表初始化完成")
    
    # 初始化Redis
    await redis_service.init_redis()
    print("Redis连接初始化完成")

    # await register_all()  # 扫描并注册任务
    # await get_scheduler()  # 确保调度器启动

    yield

    # scheduler = await get_scheduler()
    # scheduler.shutdown(wait=False)
    # 关闭时执行
    print("应用关闭中...")
    
    # 关闭所有数据库连接
    await close_databases()
    print("所有数据库连接已关闭")
    
    # 关闭Redis连接
    await redis_service.close_redis()
    print("Redis连接已关闭")


def create_app() -> FastAPI:
    """应用工厂函数"""
    app = FastAPI(
        title="FastAPI Factory Pattern Project",
        description="A FastAPI project using factory pattern with JWT, SQLAlchemy async, and Redis",
        version="1.0.0",
        debug=True,
        lifespan=lifespan
    )
    
    # 配置CORS跨域
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # 从配置文件读取允许的来源
        allow_credentials=settings.cors_allow_credentials,  # 从配置文件读取是否允许凭证
        allow_methods=settings.cors_allow_methods,  # 从配置文件读取允许的方法
        allow_headers=settings.cors_allow_headers,  # 从配置文件读取允许的请求头
    )
    
    # 添加API路由
    setup_routes(app)
    if settings.attachment.access_type == 'local':
        # 添加静态文件服务
        app.mount("/avatars", StaticFiles(directory="avatars"), name="avatars")
    return app


def setup_routes(app: FastAPI):
    """设置路由"""
    from app.api import router as api_router
    
    # 包含API路由
    app.include_router(
        api_router,
        prefix="/api",
        tags=["API"]
    ) 