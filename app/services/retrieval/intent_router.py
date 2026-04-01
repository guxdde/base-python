import re
import json
import logging
import asyncio
from typing import Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_api_key = settings.research_report.api_key if settings.research_report else None
_text_api_url = settings.research_report.text_analyze_url if settings.research_report else None
_table_model = settings.research_report.text_analyze_model if settings.research_report else "qwen-plus"
_rate_limiter = None


async def analyze_query_intent(user_query: str) -> Dict[str, str]:
    """
    调用 LLM 分析用户问题，提取关键信息
    
    Args:
        user_query: 用户问题
        
    Returns:
        {
            "company_code": "600519" 或 "NONE",
            "industry_name": "新能源汽车" 或 "NONE",
            "search_keywords": "重写后的搜索关键词"
        }
    """
    prompt = f"""请分析以下用户查询，提取关键信息。

用户查询：{user_query}

请直接返回JSON，不要其他内容：
{{
    "company_code": "提取的股票代码，如果没有则为NONE",
    "industry_name": "提取的行业名称，如果没有则为NONE",
    "search_keywords": "重写后的搜索关键词，用于语义检索"
}}
"""

    try:
        import dashscope
        from dashscope import Generation
        dashscope.api_key = _api_key

        global _rate_limiter
        if _rate_limiter is None:
            from aiolimiter import AsyncLimiter
            _rate_limiter = AsyncLimiter(settings.research_report.rate_limiter, 1)

        async with _rate_limiter:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: Generation.call(
                    model=_table_model,
                    prompt=prompt,
                    result_format='message',
                    stream=False
                )
            )

            if response.status_code == 200:
                content = response.output.text if hasattr(response.output, 'text') else str(response.output)
                return _parse_intent_result(content)
            else:
                logger.warning(f"意图识别失败: {response.message}")
                return _default_intent(user_query)

    except ImportError:
        return await _analyze_intent_http(user_query, prompt)
    except Exception as e:
        logger.error(f"意图识别异常: {e}")
        return _default_intent(user_query)


async def _analyze_intent_http(user_query: str, prompt: str) -> Dict[str, str]:
    """通过 HTTP 调用 LLM 进行意图识别"""
    try:
        import aiohttp
        headers = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": _table_model,
            "input": {"prompt": prompt},
            "parameters": {"stream": False}
        }

        global _rate_limiter
        if _rate_limiter is None:
            from aiolimiter import AsyncLimiter
            _rate_limiter = AsyncLimiter(settings.research_report.rate_limiter, 1)

        async with _rate_limiter:
            async with aiohttp.ClientSession() as session:
                async with session.post(_text_api_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        return _default_intent(user_query)
                    result = await resp.json()
                    if 'output' in result and 'text' in result['output']:
                        return _parse_intent_result(result['output']['text'])
                    return _default_intent(user_query)
    except Exception as e:
        logger.error(f"HTTP 意图识别失败: {e}")
        return _default_intent(user_query)


def _parse_intent_result(content: str) -> Dict[str, str]:
    """解析 LLM 返回的意图结果"""
    try:
        content = content.strip()
        content = re.sub(r'^[^{]*', '', content)
        content = re.sub(r'[^}]*$', '', content)
        data = json.loads(content)
        return {
            "company_code": data.get("company_code", "NONE"),
            "industry_name": data.get("industry_name", "NONE"),
            "search_keywords": data.get("search_keywords", "") or data.get("search_keywords", "NONE")
        }
    except json.JSONDecodeError:
        logger.warning(f"意图解析 JSON 失败: {content}")
        return _default_intent(content)


def _default_intent(query: str) -> Dict[str, str]:
    """默认意图处理：提取常见股票代码格式"""
    ts_code_pattern = r'(\d{6}\.[A-Z]{2,4})'
    match = re.search(ts_code_pattern, query)
    
    company_code = match.group(1) if match else "NONE"
    
    industries = [
        "新能源", "汽车", "电子", "医药", "消费", "互联网", 
        "房地产", "金融", "半导体", "军工", "化工", "钢铁",
        "游戏", "传媒", "通信", "电力", "钢铁", "煤炭",
        "有色", "建材", "农业", "交运", "旅游", "银行",
        "保险", "券商", "地产", "物业", "教育", "医疗"
    ]
    industry_name = "NONE"
    for ind in industries:
        if ind in query:
            industry_name = ind
            logger.info(f"默认意图识别到行业: {ind}")
            break
    
    return {
        "company_code": company_code,
        "industry_name": industry_name,
        "search_keywords": query
    }
