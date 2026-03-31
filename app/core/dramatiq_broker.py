"""
Dramatiq Broker 配置

使用 RabbitMQ 作为消息代理，支持定时任务 (Periodiq)
"""
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
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


def get_broker() -> RabbitmqBroker:
    """
    获取或创建 Dramatiq Broker 实例
    使用单例模式确保全局只有一个 Broker 实例
    """
    global _broker
    
    if _broker is None:
        amqp_url = _build_amqp_url()
        
        _broker = RabbitmqBroker(url=amqp_url)
        
        periodiq_middleware = PeriodiqMiddleware(skip_delay=30)
        _broker.add_middleware(periodiq_middleware)
        
        dramatiq.set_broker(_broker)
    
    return _broker


def initialize() -> RabbitmqBroker:
    """初始化 Dramatiq Broker"""
    return get_broker()
