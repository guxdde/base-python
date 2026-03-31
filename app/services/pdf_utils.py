import re
import os
import asyncio
import base64
import logging
from typing import Dict, Optional, Any, List
from aiolimiter import AsyncLimiter
import aiohttp

from app.core.config import settings

_logger = logging.getLogger(__name__)

_rate_limiter = AsyncLimiter(settings.research_report.rate_limiter, 1)
_api_key = settings.research_report.api_key
_image_api_url = settings.research_report.image_analyze_url
_image_model = settings.research_report.image_analyze_model
_text_api_url = settings.research_report.text_analyze_url
_table_model = settings.research_report.text_analyze_model


def clean_markdown_content(content: str) -> str:
    lines = content.split('\n')
    cleaned_lines = []

    for line in lines:
        if re.match(r'^#{1,6}\s', line):
            cleaned_line = _clean_title_line(line)
        else:
            cleaned_line = _clean_text_line(line)
        cleaned_lines.append(cleaned_line)

    return '\n'.join(cleaned_lines)


def _clean_title_line(title_line: str) -> str:
    level_match = re.match(r'^(#{1,6})\s+', title_line)
    if not level_match:
        return title_line

    level = level_match.group(1)
    content = title_line[len(level):].strip()
    content = re.sub(r'\$\s*(\d+)\s+(\d+)\s*%\s*\$', r'\1\2%', content)
    content = re.sub(r'\$\s*(\d+)\s*%\s*\$', r'\1%', content)
    content = re.sub(r'\{[^}]*\}', '', content)
    content = re.sub(r'\\[a-zA-Z]*', '', content)
    content = re.sub(r'\\\.', '.', content)
    content = re.sub(r'\\%', '%', content)
    content = re.sub(r'\\\s*', '', content)
    content = re.sub(r'(\d)\s+(\d)', r'\1\2', content)
    content = re.sub(r'\$', '', content)
    content = re.sub(r'\s{2,}', ' ', content)
    return f"{level} {content.strip()}"


def _clean_text_line(text_line: str) -> str:
    if not text_line.strip():
        return text_line

    cleaned = text_line
    cleaned = re.sub(r'\$([^$]+)\$', lambda m: re.sub(r'[a-zA-Z{}\\]', '', m.group(1)), cleaned)
    cleaned = re.sub(r'(\d+)\s+(\d+)\s*\.\s*(\d+)\s*%', r'\1\2.\3%', cleaned)
    cleaned = re.sub(r'(\d+)\s*\.\s*(\d+)\s*%', r'\1.\2%', cleaned)
    cleaned = re.sub(r'\+\s+(\d+)', r'+\1', cleaned)
    cleaned = re.sub(r'-\s+(\d+)', r'-\1', cleaned)
    cleaned = re.sub(r'\$', '', cleaned)
    cleaned = re.sub(r'(\d+)\s+%', r'\1%', cleaned)
    cleaned = re.sub(r'\s*，\s*', '，', cleaned)
    cleaned = re.sub(r'\s*。\s*', '。', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    return cleaned.strip()


def _parse_result(content: Any, result_type: str = "image") -> Dict[str, str]:
    try:
        if content is None:
            return {"title": "分析失败", "description": f"{result_type}分析失败，返回内容为空"}

        if not isinstance(content, str):
            content = str(content)

        content = content.strip()
        content = re.sub(r'[{}[\]\'"]', '', content)
        content = re.sub(r'\\n\\n|\\n|\\\w+', ' ', content)

        title_match = re.search(r'标题[:：]\s*(.+?)(?=\n|描述|$)', content, re.IGNORECASE)
        desc_match = re.search(r'描述[:：]\s*(.+)', content, re.IGNORECASE | re.DOTALL)

        if title_match and desc_match:
            title = _clean_title(title_match.group(1).strip(), result_type)
            description = _clean_description(desc_match.group(1).strip())
        else:
            title = f"{'表格' if result_type == 'table' else '图片'}内容"
            description = content[:500] if len(content) > 500 else content

        if len(description) > 500:
            description = description[:497] + "..."

        return {"title": title, "description": description}

    except Exception as e:
        return {"title": "解析失败", "description": f"解析出错: {str(e)}"}


def _clean_title(title: str, title_type: str = "image") -> str:
    if not title:
        return "分析结果"
    title = re.sub(r'\{COMPANY_NAME\}\s*-?\s*', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'[{}[\]\'"]', '', title)
    if len(title.strip()) < 2:
        title = "表格数据" if title_type == "table" else "图片内容"
    return title


def _clean_description(description: str) -> str:
    if not description:
        return "暂无描述"
    description = re.sub(r'[{}[\]\'"]', '', description)
    description = re.sub(r'\\[ntr]', ' ', description)
    description = re.sub(r'\n+', ' ', description)
    description = re.sub(r'\s+', ' ', description)
    description = description.strip()
    if description and not description.endswith(('。', '.', '！', '？', '!', '?')):
        description += '。'
    return description


async def analyze_image(image_path: str, prompt: Optional[str] = None) -> Dict[str, str]:
    if not os.path.exists(image_path):
        return {"title": "图片分析失败", "description": "文件不存在"}

    if prompt is None:
        prompt = """请分析这张图片，提供图片标题和详细描述。

要求：
1. 图片标题：简洁准确的标题，概括图片的主要内容
2. 图片描述：500字以内，客观描述图片内容、要素和关键信息
3. 不要进行评价，只进行客观描述

请按以下格式回答：
标题：[图片标题]
描述：[详细的图片内容描述]"""

    try:
        import dashscope
        from dashscope import MultiModalConversation
        dashscope.api_key = _api_key

        async with _rate_limiter:
            abs_path = os.path.abspath(image_path)
            messages = [{
                'role': 'user',
                'content': [
                    {'image': f'file://{abs_path}'},
                    {'text': prompt}
                ]
            }]

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: MultiModalConversation.call(
                    model=_image_model,
                    messages=messages,
                    result_format='message',
                    stream=False
                )
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if isinstance(content, list):
                    content = ''.join([item.get('text', '') for item in content if isinstance(item, dict)])
                return _parse_result(content, "image")
            else:
                return {"title": "图片分析失败", "description": f"API错误: {response.message}"}

    except ImportError:
        return await _analyze_image_http(image_path, prompt)
    except Exception as e:
        _logger.error(f"分析图片出错: {e}")
        return {"title": "图片分析失败", "description": f"分析出错: {str(e)}"}


async def _analyze_image_http(image_path: str, prompt: str) -> Dict[str, str]:
    try:
        with open(image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')

        headers = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": _image_model,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{image_base64}"},
                        {"text": prompt}
                    ]
                }]
            },
            "parameters": {"stream": False}
        }

        import aiohttp
        async with _rate_limiter:
            async with aiohttp.ClientSession() as session:
                async with session.post(_image_api_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        return {"title": "图片分析失败", "description": f"HTTP错误: {resp.status}"}

                    result = await resp.json()
                    if 'output' in result and 'choices' in result['output']:
                        content = result['output']['choices'][0]['message']['content']
                        if isinstance(content, list):
                            content = ''.join([item.get('text', '') for item in content])
                        return _parse_result(content, "image")
                    return {"title": "图片分析失败", "description": "响应格式错误"}
    except Exception as e:
        return {"title": "图片分析失败", "description": f"HTTP分析出错: {str(e)}"}


async def analyze_html_table(html_content: str, prompt: Optional[str] = None) -> Dict[str, str]:
    if prompt is None:
        prompt = """请分析这个HTML表格，提供表格标题和详细描述。

要求：
1. 表格标题：简洁准确的标题，概括表格的主要内容
2. 表格描述：500字以内，重点描述表格的数据含义和关键信息
3. 不要进行评价，只进行客观描述

请按以下格式回答：
标题：[表格标题]
描述：[详细的表格内容描述]"""

    full_prompt = f"HTML表格内容：\n{html_content}\n\n{prompt}"

    try:
        import dashscope
        from dashscope import Generation
        dashscope.api_key = _api_key

        async with _rate_limiter:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: Generation.call(
                    model=_table_model,
                    prompt=full_prompt,
                    result_format='message',
                    stream=False
                )
            )

            if response.status_code == 200:
                content = response.output.text if hasattr(response.output, 'text') else str(response.output)
                return _parse_result(content, "table")
            else:
                return {"title": "表格分析失败", "description": f"API错误: {response.message}"}

    except ImportError:
        return await _analyze_html_http(html_content, full_prompt)
    except Exception as e:
        _logger.error(f"分析HTML表格出错: {e}")
        return {"title": "表格分析失败", "description": f"分析出错: {str(e)}"}


async def _analyze_html_http(html_content: str, prompt: str) -> Dict[str, str]:
    try:
        import aiohttp
        headers = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": _table_model,
            "input": {"prompt": prompt},
            "parameters": {"stream": False}
        }

        async with _rate_limiter:
            async with aiohttp.ClientSession() as session:
                async with session.post(_text_api_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        return {"title": "表格分析失败", "description": f"HTTP错误: {resp.status}"}

                    result = await resp.json()
                    if 'output' in result and 'text' in result['output']:
                        return _parse_result(result['output']['text'], "table")
                    return {"title": "表格分析失败", "description": "响应格式错误"}
    except Exception as e:
        return {"title": "表格分析失败", "description": f"HTTP分析出错: {str(e)}"}


async def generate_summary(content: str) -> str:
    prompt = """请为以下研报内容生成400-500字的摘要。

要求：
1. 概括核心观点和数据
2. 保持客观中立
3. 不要添加解释性文字
4. 摘要内容不超过500字
5. 直接返回摘要文字，不要其他格式

研报内容：
{content}"""

    full_prompt = prompt.format(content=content[:3000])

    try:
        import dashscope
        from dashscope import Generation
        dashscope.api_key = _api_key

        async with _rate_limiter:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: Generation.call(
                    model=_table_model,
                    prompt=full_prompt,
                    result_format='message',
                    stream=False
                )
            )

            if response.status_code == 200:
                summary = response.output.text if hasattr(response.output, 'text') else str(response.output)
                summary = summary.strip()
                # if len(summary) > 200:
                #     summary = summary[:197] + "..."
                if len(summary) > 500:
                    summary = summary[:500]
                return summary
            else:
                _logger.warning(f"摘要生成失败: {response.message}")
                return ""

    except ImportError:
        return await _generate_summary_http(content)
    except Exception as e:
        _logger.error(f"摘要生成异常: {e}")
        return ""


async def generate_report_summary(content: str) -> str:
    """生成整篇报告摘要（一次性调用）

    Args:
        content: 完整报告内容

    Returns:
        报告摘要字符串
    """
    prompt = """请为以下研报内容生成简洁摘要。

要求：
1. 概括报告的核心主题和研究结论
2. 保持客观中立
3. 直接返回摘要文字
4. 摘要内容不超过 300 字

研报内容：
{content}"""

    full_prompt = prompt.format(content=content[:5000])

    try:
        import dashscope
        from dashscope import Generation
        dashscope.api_key = _api_key

        async with _rate_limiter:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: Generation.call(
                    model=_table_model,
                    prompt=full_prompt,
                    result_format='message',
                    stream=False
                )
            )

            if response.status_code == 200:
                summary = response.output.text if hasattr(response.output, 'text') else str(response.output)
                summary = summary.strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."
                return summary
            else:
                _logger.warning(f"报告摘要生成失败: {response.message}")
                return ""

    except ImportError:
        return await _generate_report_summary_http(content)
    except Exception as e:
        _logger.error(f"报告摘要生成异常: {e}")
        return ""


async def _generate_report_summary_http(content: str) -> str:
    try:
        import aiohttp
        prompt = """请为以下研报内容生成简洁摘要。

要求：
1. 概括报告的核心主题和研究结论
2. 保持客观中立
3. 直接返回摘要文字
4. 摘要内容不超过 300 字

研报内容：
{content}"""

        full_prompt = prompt.format(content=content[:5000])

        headers = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": _table_model,
            "input": {"prompt": full_prompt},
            "parameters": {"stream": False}
        }

        async with _rate_limiter:
            async with aiohttp.ClientSession() as session:
                async with session.post(_text_api_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        return ""
                    result = await resp.json()
                    if 'output' in result and 'text' in result['output']:
                        summary = result['output']['text'].strip()
                        if len(summary) > 300:
                            summary = summary[:297] + "..."
                        return summary
                    return ""
    except Exception as e:
        _logger.error(f"HTTP 报告摘要生成失败: {e}")
        return ""


async def generate_contextual_summary(
    chunk_content: str,
    report_summary: str,
    header_path: str,
    report_title: str,
    chunk_index: int
) -> str:
    """生成上下文增强摘要

    基于整篇报告摘要和当前段落位置，生成包含上下文的增强摘要。

    Args:
        chunk_content: 当前段落内容
        report_summary: 整篇报告摘要
        header_path: 标题路径，如 "一级标题 > 二级标题 > 三级标题"
        report_title: 报告主题/标题
        chunk_index: 当前段落在报告中的索引位置

    Returns:
        上下文增强摘要字符串 (400-500字)
    """
    prompt = """这是一篇关于「{report_title}」的研报分析。

【整篇报告摘要】
{report_summary}

【当前段落位置】
{header_path}（第 {chunk_index} 个段落）

【当前段落内容】
{chunk_content}

请用 300-400 字概括这段内容在整篇报告中的核心贡献，直接返回摘要，不要其他格式。"""
    try:
        full_prompt = prompt.format(
            report_title=report_title or "该主题",
            report_summary=report_summary or "暂无报告摘要",
            header_path=header_path or "未知位置",
            chunk_index=chunk_index + 1,
            chunk_content=chunk_content[:1500]
        )

        headers = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": _table_model,
            "input": {"prompt": full_prompt},
            "parameters": {"stream": False}
        }

        async with _rate_limiter:
            async with aiohttp.ClientSession() as session:
                async with session.post(_text_api_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        _logger.error(f"HTTP 上下文摘要生成失败, status: {resp.status}")
                        return ""
                    result = await resp.json()
                    if 'output' in result and 'text' in result['output']:
                        summary = result['output']['text'].strip()
                        _logger.info(f"[HTTP]上下文摘要原始长度: {len(summary)}, chunk_index: {chunk_index}")
                        if len(summary) > 500:
                            summary = summary[:497] + "..."
                        _logger.info(f"[HTTP]上下文摘要截断后长度: {len(summary)}, chunk_index: {chunk_index}")
                        return summary
                    _logger.warning(f"HTTP 上下文摘要返回格式错误: {result}")
                    return ""
    except Exception as e:
        _logger.error(f"HTTP 上下文摘要生成失败: {e}")
        return ""


async def _generate_summary_http(content: str) -> str:
    try:
        import aiohttp
        prompt = """请为以下研报内容生成100-200字的摘要。

要求：
1. 概括核心观点和数据
2. 保持客观中立
3. 直接返回摘要文字
4. 摘要内容不超过300字

内容：
{content}
"""

        full_prompt = prompt.format(content=content[:3000])

        headers = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": _table_model,
            "input": {"prompt": full_prompt},
            "parameters": {"stream": False}
        }

        async with _rate_limiter:
            async with aiohttp.ClientSession() as session:
                async with session.post(_text_api_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        return ""
                    result = await resp.json()
                    if 'output' in result and 'text' in result['output']:
                        summary = result['output']['text'].strip()
                        if len(summary) > 500:
                            summary = summary[:500]
                        return summary
                    return ""
    except Exception as e:
        _logger.error(f"HTTP 摘要生成失败: {e}")
        return ""


async def extract_related_stocks(content: str) -> List[Dict[str, str]]:
    prompt = """请从以下研报内容中提取所有涉及的公司和个股信息。

要求：
1. 提取公司名称和股票代码（如"腾讯控股 00700"）
2. 如果没有涉及具体公司，返回空列表
3. 只返回涉及的个股，不返回行业本身
4. 直接返回 JSON，不要其他内容

研报内容：
{content}

请按以下JSON格式返回：
{{"companies": [{{"name": "公司名", "code": "股票代码"}}, ...]}}"""

    full_prompt = prompt.format(content=content[:3000])

    try:
        import dashscope
        from dashscope import Generation
        dashscope.api_key = _api_key

        async with _rate_limiter:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: Generation.call(
                    model=_table_model,
                    prompt=full_prompt,
                    result_format='message',
                    stream=False
                )
            )

            if response.status_code == 200:
                result_text = response.output.text if hasattr(response.output, 'text') else str(response.output)
                return _parse_related_stocks(result_text)
            else:
                _logger.warning(f"实体提取失败: {response.message}")
                return []

    except ImportError:
        return await _extract_related_stocks_http(content)
    except Exception as e:
        _logger.error(f"实体提取异常: {e}")
        return []


async def _extract_related_stocks_http(content: str) -> List[Dict[str, str]]:
    try:
        import aiohttp
        prompt = """请从以下研报内容中提取所有涉及的公司和个股信息。

要求：
1. 提取公司名称和股票代码
2. 如果没有涉及具体公司，返回空列表

研报内容：
{content}

请按以下JSON格式返回：
{{"companies": [{{"name": "公司名", "code": "股票代码"}}, ...]}}"""

        full_prompt = prompt.format(content=content[:3000])

        headers = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": _table_model,
            "input": {"prompt": full_prompt},
            "parameters": {"stream": False}
        }

        async with _rate_limiter:
            async with aiohttp.ClientSession() as session:
                async with session.post(_text_api_url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        return []
                    result = await resp.json()
                    if 'output' in result and 'text' in result['output']:
                        return _parse_related_stocks(result['output']['text'])
                    return []
    except Exception as e:
        _logger.error(f"HTTP 实体提取失败: {e}")
        return []


def _parse_related_stocks(text: str) -> List[Dict[str, str]]:
    import json as json_module
    try:
        text = text.strip()
        text = re.sub(r'^[^{]*', '', text)
        text = re.sub(r'[^}]*$', '', text)
        data = json_module.loads(text)
        if 'companies' in data:
            return data['companies']
        return []
    except Exception:
        try:
            name_pattern = r'"name"\s*:\s*"([^"]+)"'
            code_pattern = r'"code"\s*:\s*"([^"]*)"'
            names = re.findall(name_pattern, text)
            codes = re.findall(code_pattern, text)
            result = []
            for i, name in enumerate(names):
                code = codes[i] if i < len(codes) else ""
                result.append({"name": name, "code": code})
            return result
        except Exception:
            return []
