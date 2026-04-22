"""
TaskIQ scheduler module.

定时任务现在由 taskiq-scheduler 容器独立运行。
此文件保留用于兼容性。
"""

import logging

logger = logging.getLogger(__name__)


def add_schedule(task_name: str, schedule, name: str = None, description: str = None):
    """手动添加定时任务"""
    logger.info(f"Schedule added: {task_name}, cron: {schedule}")


def get_schedules():
    """获取所有定时任务"""
    return []
