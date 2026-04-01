import math
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_LAMBDA_MONTHLY = 0.01


def parse_trade_date(trade_date_str: str) -> Optional[int]:
    """将 trade_date 字符串转为时间戳"""
    if not trade_date_str:
        return None
    
    try:
        if len(trade_date_str) == 10:
            dt = datetime.strptime(trade_date_str, "%Y-%m-%d")
        elif len(trade_date_str) == 7:
            dt = datetime.strptime(trade_date_str + "-01", "%Y-%m-%d")
        else:
            dt = datetime.strptime(trade_date_str, "%Y%m%d")
        return int(dt.timestamp())
    except ValueError:
        logger.warning(f"无法解析日期: {trade_date_str}")
        return None


def calculate_months_diff(publish_timestamp: int, current_timestamp: int) -> float:
    """计算月份差"""
    publish_date = datetime.fromtimestamp(publish_timestamp)
    current_date = datetime.fromtimestamp(current_timestamp)
    
    months = (current_date.year - publish_date.year) * 12 + (current_date.month - publish_date.month)
    return max(0, months)


def apply_time_decay(
    search_results: List[Dict[str, Any]],
    current_timestamp: Optional[int] = None,
    lambda_monthly: float = DEFAULT_LAMBDA_MONTHLY,
    top_k: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    应用时效性衰减
    
    公式: S_final = S_vector × exp(-λ × Δ月)
    
    Args:
        search_results: 检索结果列表
        current_timestamp: 当前时间戳，默认使用当前时间
        lambda_monthly: 月衰减系数，默认 0.01 (每满1月分数降低约1%)
        top_k: 返回结果数量，默认返回全部
        
    Returns:
        按最终得分降序排列的结果列表
    """
    if not search_results:
        return []
    
    if current_timestamp is None:
        current_timestamp = int(datetime.now().timestamp())
    
    results_with_decay = []
    
    for result in search_results:
        trade_date_str = result.get("trade_date", "")
        publish_timestamp = parse_trade_date(trade_date_str)
        
        if publish_timestamp is None:
            months_diff = 0
        else:
            months_diff = calculate_months_diff(publish_timestamp, current_timestamp)
        
        original_score = result.get("score", 0)
        
        decay_factor = math.exp(-lambda_monthly * months_diff)
        final_score = original_score * decay_factor
        
        result["final_score"] = final_score
        result["months_diff"] = months_diff
        result["decay_factor"] = decay_factor
        
        results_with_decay.append(result)
    
    results_with_decay.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    
    if top_k is not None and top_k > 0:
        results_with_decay = results_with_decay[:top_k]
    
    logger.info(
        f"时效性衰减完成: 原始结果 {len(search_results)} 条, "
        f"衰减后 {len(results_with_decay)} 条, λ={lambda_monthly}"
    )
    
    return results_with_decay


def apply_time_decay_with_threshold(
    search_results: List[Dict[str, Any]],
    current_timestamp: Optional[int] = None,
    lambda_monthly: float = DEFAULT_LAMBDA_MONTHLY,
    max_months: int = 24
) -> List[Dict[str, Any]]:
    """
    带时间阈值的时效性衰减
    
    超过 max_months 的结果直接过滤掉
    
    Args:
        search_results: 检索结果列表
        current_timestamp: 当前时间戳
        lambda_monthly: 月衰减系数
        max_months: 最大允许的月数
        
    Returns:
        过滤并衰减后的结果列表
    """
    if not search_results:
        return []
    
    if current_timestamp is None:
        current_timestamp = int(datetime.now().timestamp())
    
    results_filtered = []
    
    for result in search_results:
        trade_date_str = result.get("trade_date", "")
        publish_timestamp = parse_trade_date(trade_date_str)
        
        if publish_timestamp is None:
            months_diff = 0
        else:
            months_diff = calculate_months_diff(publish_timestamp, current_timestamp)
        
        if months_diff > max_months:
            continue
        
        original_score = result.get("score", 0)
        decay_factor = math.exp(-lambda_monthly * months_diff)
        final_score = original_score * decay_factor
        
        result["final_score"] = final_score
        result["months_diff"] = months_diff
        result["decay_factor"] = decay_factor
        
        results_filtered.append(result)
    
    results_filtered.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    
    logger.info(
        f"时效性衰减(带阈值)完成: 原始 {len(search_results)} 条, "
        f"过滤后 {len(results_filtered)} 条 (max_months={max_months})"
    )
    
    return results_filtered
