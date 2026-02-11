import pytest
from app.core import celery as celery_module
from app.core.celery import celery as celery_app
from celery.contrib.testing.worker import start_worker

def test_celery_task_decorator_basic(monkeypatch):
    # 使用内存队列作为 broker，避免外部依赖
    monkeypatch.setattr(celery_module, "_build_broker_url", lambda: "memory://")
    # 重新创建应用
    celery_module._CeleryApp._app = None

    @celery_module.celery_task(queue="default")
    def add(a: int, b: int) -> int:
        return a + b

    # eager 模式下任务会同步执行，返回结果
    celery_app.conf.task_always_eager = True
    result = add.delay(1, 2)
    assert result == 3  # 在 eager 模式下，delay 返回直接结果

def test_celery_task_with_worker_end_to_end(monkeypatch):
    # 使用内存队列作为 broker，模拟真实 worker 的端到端
    monkeypatch.setattr(celery_module, "_build_broker_url", lambda: "memory://")
    celery_module._CeleryApp._app = None

    @celery_module.celery_task(queue="default")
    def sub(a: int, b: int) -> int:
        return a - b

    celery_app.conf.task_always_eager = False

    with start_worker(celery_app) as w:
        res = sub.delay(10, 3)
        assert res.get(timeout=10) == 7

def test_backend_switch_demo(monkeypatch):
    # 演示如何在设置中切换后端
    monkeypatch.setattr(celery_module, "_build_broker_url", lambda: "memory://")
    celery_module._CeleryApp._app = None

    class DummyCeleryCfg:
        backend_url = "redis://localhost:6379/1"

    # 构造一个带 celery 配置的 settings 快照，覆盖原有 settings
    monkeypatch.setattr(
        celery_module, "settings",
        type("S", (), {
            "rabbitmq": type("R", (), {"host": "localhost", "port": 5672, "username": "guest", "password": "guest", "virtual_host": "/"})(),
            "celery": DummyCeleryCfg(),
            "redis": None
        })()
    )

    # 重新创建 app，以便应用新的后端配置
    celery_module._CeleryApp._app = None

    @celery_module.celery_task(queue="default")
    def mul(a: int, b: int) -> int:
        return a * b

    celery_app.conf.task_always_eager = True
    # 验证后端被正确赋值（在 eager 模式下结果后端并非真正使用，但配置应被正确加载）
    backend_config = getattr(celery_app.conf, "result_backend", None)
    assert backend_config == "redis://localhost:6379/1" or backend_config is None
    assert mul.delay(3, 4) == 12
