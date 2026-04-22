"""
TaskIQ 定时任务模块

此模块用于定义 TaskIQ 定时任务。
定时任务通过 @taskiq_task 装饰器注册。
"""

import logging

from app.tasks import scheduled_tasks  # noqa: F401 导入即注册任务

_logger = logging.getLogger(__name__)