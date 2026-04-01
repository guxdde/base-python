"""
Dramatiq Broker 配置

使用 RabbitMQ 作为消息代理，支持定时任务 (Periodiq)
支持纯异步任务 (AsyncIO 中间件)
"""
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.middleware import AsyncIO, Retries
from periodiq import PeriodiqMiddleware
from typing import Optional
from urllib.parse import quote_plus

from app.core.config import settings

_broker: Optional[RabbitmqBroker] = None


def _build_amqp_url() -> str:
    """构建 AMQP URL"""
    conf = settings.rabbitmq
    user_enc = quote_plus(str(conf.username or ""))
    pass_enc = quote_plus(str(conf.password or ""))
    vh = conf.virtual_host or "/"
    if not vh.startswith("/"):
        vh = f"/{vh}"
    return f"amqp://{user_enc}:{pass_enc}@{conf.host}:{conf.port}{vh}"


# 初始化时先清空中间件防止重复警告
broker = RabbitmqBroker(url=_build_amqp_url())
broker.middleware = []

broker.add_middleware(AsyncIO())
broker.add_middleware(Retries(max_retries=3))
broker.add_middleware(PeriodiqMiddleware())

# 设置为全局默认 Broker
dramatiq.set_broker(broker)

# 这个变量供其他地方引用（如果需要）
rabbitmq_broker = broker