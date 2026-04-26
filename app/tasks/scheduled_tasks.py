"""
TaskIQ 定时任务定义

定时任务通过 taskiq-scheduler 容器运行。
队列优先级: high_priority > default > low_priority
"""

import asyncio
import logging

from app.core.taskiq import broker, QUEUE_DEFAULT, QUEUE_HIGH, QUEUE_LOW

_logger = logging.getLogger(__name__)


# 高优先级队列任务
@broker.task(queue_name=QUEUE_HIGH, priority=5, timeout=60)
async def sync_market_data():
    """同步市场数据任务 - 高优先级"""
    _logger.info("开始执行市场数据同步任务")
    _logger.info("市场数据同步任务完成")
    return {"status": "success", "task": "sync_market_data"}


@broker.task(queue_name=QUEUE_HIGH, priority=5, timeout=600)
async def morning_notification():
    """早间通知任务 - 高优先级"""
    _logger.info("发送早间通知")
    return {"status": "success", "task": "morning notification"}


# 默认队列任务（中优先级）
@broker.task(queue_name=QUEUE_DEFAULT, priority=5, timeout=120)
async def sync_user_data_task():
    """用户数据同步任务 - 默认优先级"""
    _logger.info("开始同步用户数据")
    _logger.info("用户数据同步完成")
    return {"status": "success", "task": "sync_user_data"}


@broker.task(queue_name=QUEUE_DEFAULT, priority=5, timeout=120)
async def io_blocking_task(task_id: int):
    """IO阻塞测试任务 - 默认优先级"""
    _logger.info(f"[Task {task_id}] 开始执行 IO 模拟任务")
    
    for i in range(5):
        _logger.info(f"[Task {task_id}] 第 {i+1}/5 次 Sleep，模拟IO阻塞...")
        await asyncio.sleep(2)
        _logger.info(f"[Task {task_id}] 第 {i+1}/5 次 Sleep 完成")
    
    _logger.info(f"[Task {task_id}] IO 模拟任务完成")
    return {"status": "success", "task_id": task_id}


# 低优先级队列任务
@broker.task(queue_name=QUEUE_LOW, priority=5, timeout=300)
async def generate_daily_report():
    """生成每日报告任务 - 低优先级"""
    _logger.info("开始生成每日报告")
    _logger.info("每日报告生成完成")
    return {"status": "success", "task": "generate_daily_report"}


@broker.task(queue_name=QUEUE_LOW, priority=5, timeout=300)
async def evening_summary():
    """晚间汇总任务 - 低优先级"""
    _logger.info("生成晚间汇总")
    return {"status": "success", "task": "evening_summary"}


@broker.task(queue_name=QUEUE_LOW, priority=5, timeout=1800)
async def weekly_data_cleanup():
    """周数据清理任务 - 低优先级"""
    _logger.info("开始周数据清理")
    _logger.info("周数据清理完成")
    return {"status": "success", "task": "weekly_data_cleanup"}


@broker.task(queue_name=QUEUE_LOW, priority=5, timeout=600)
async def backup_database_task():
    """数据库备份任务 - 低优先级"""
    _logger.info("开始数据库备份")
    _logger.info("数据库备份完成")
    return {"status": "success", "task": "backup_database"}