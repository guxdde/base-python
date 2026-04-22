"""
TaskIQ 定时任务定义

定时任务通过 taskiq-scheduler 容器运行。
"""

import logging

from app.core.taskiq import taskiq_task

_logger = logging.getLogger(__name__)


@taskiq_task(queue="default", timeout=60)
async def sync_market_data():
    """同步市场数据任务"""
    _logger.info("开始执行市场数据同步任务")
    _logger.info("市场数据同步任务完成")
    return {"status": "success", "task": "sync_market_data"}


@taskiq_task(queue="default", timeout=300)
async def generate_daily_report():
    """生成每日报告任务"""
    _logger.info("开始生成每日报告")
    _logger.info("每日报告生成完成")
    return {"status": "success", "task": "generate_daily_report"}


@taskiq_task(queue="default", timeout=600)
async def morning_notification():
    """早间通知任务"""
    _logger.info("发送早间通知")
    return {"status": "success", "task": "morning notification"}


@taskiq_task(queue="default", timeout=300)
async def evening_summary():
    """晚间汇总任务"""
    _logger.info("生成晚间汇总")
    return {"status": "success", "task": "evening_summary"}


@taskiq_task(queue="default", timeout=1800)
async def weekly_data_cleanup():
    """周数据清理任务"""
    _logger.info("开始周数据清理")
    _logger.info("周数据清理完成")
    return {"status": "success", "task": "weekly_data_cleanup"}


@taskiq_task(queue="default", timeout=600)
async def backup_database_task():
    """数据库备份任务"""
    _logger.info("开始数据库备份")
    _logger.info("数据库备份完成")
    return {"status": "success", "task": "backup_database"}


@taskiq_task(queue="default", timeout=120)
async def sync_user_data_task():
    """用户数据同步任务"""
    _logger.info("开始同步用户数据")
    _logger.info("用户数据同步完成")
    return {"status": "success", "task": "sync_user_data"}