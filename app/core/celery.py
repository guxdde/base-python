from typing import Optional, Callable, Any
from celery import Celery
from urllib.parse import quote_plus
from .config import settings


def _build_broker_url() -> str:
    """Build RabbitMQ AMQP URL from settings"""
    vh = settings.rabbitmq.virtual_host or "/"
    if not str(vh).startswith("/"):
        vh = f"/{vh}"
    user = settings.rabbitmq.username or ""
    password = settings.rabbitmq.password or ""
    host = settings.rabbitmq.host
    port = settings.rabbitmq.port
    user_enc = quote_plus(str(user))
    pass_enc = quote_plus(str(password))
    return f"amqp://{user_enc}:{pass_enc}@{host}:{port}{vh}"


class _CeleryApp:
    _app: Optional[Celery] = None

    @classmethod
    def get_app(cls) -> Celery:
        if cls._app is None:
            broker_url = _build_broker_url()
            cls._app = Celery("app_tasks", broker=broker_url, backend="rpc://")
            cls._app.conf.update(
                task_serializer="json",
                accept_content=["json"],
                result_serializer="json",
                timezone="Asia/Shanghai",
                enable_utc=False,
                task_default_queue="default",
                task_track_started=True,
            )
        return cls._app


def celery_task(queue: Optional[str] = None, **task_kwargs):
    """
    Celery 任务装饰器封装。
    - queue: 指定任务队列名称
    - 其余参数将直接传递给 Celery 的 task() 装饰器
    使用示例:
    @celery_task(queue="high_priority")
    def my_task(...):
        ...
    """
    def _decorator(func: Callable[..., Any]):
        app = _CeleryApp.get_app()
        if queue:
            task_kwargs["queue"] = queue
        return app.task(func, **task_kwargs)
    return _decorator

# 兼容 Celery CLI 使用方式，暴露一个 module-level app
celery = _CeleryApp.get_app()
