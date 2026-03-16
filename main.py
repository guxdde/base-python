from app.factory import create_app
from app.factory import get_celery_app

# 使用工厂模式创建应用实例
app = create_app()

celery_app = get_celery_app()

if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        workers=1,
    )

