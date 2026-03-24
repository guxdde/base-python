import datetime
from sqlalchemy import select, and_
from mineru.cli.common import aio_do_parse, read_fn
import logging
import os
import re
from typing import Dict, Optional, Any
import asyncio
import base64
from aiolimiter import AsyncLimiter
from pathlib import Path

from app.core.config import settings
from app.models import IndustryResearchReportRecord
from app.models.chunk import ProcessStatusEnum, StockResearchReportRecord
from app.models.report import StockResearchReport, DownloadStatusEnum, IndustryResearchReport
from app.core.database import dbm
from app.services.markdown_splitter import MarkdownReportSplitter

_logger = logging.getLogger(__name__)

class PDFService:

    def __init__(self):
        self.report_dir = settings.research_report.report_dir
        self.output_dir = settings.research_report.output_dir
        self.mineru_server = settings.research_report.mineru_server

        # 初始化通义千问图片分析器

        self.api_key = settings.research_report.api_key

        # if not self.api_key:
        #     raise ValueError("研报PDF处理需要提供api_key参数")

        # 设置图片分析API URL和模型

        self.image_api_url = settings.research_report.image_analyze_url
        #"https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

        self.image_model = settings.research_report.image_analyze_model
        #"qwen-vl-max"  # 可选: qwen-vl-max, qwen-vl-plus, qwen-vl-chat, qvq-max

        # 设置表格分析API URL和模型

        self.text_api_url = settings.research_report.text_analyze_url
        #"https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

        self.table_model = settings.research_report.text_analyze_model
        #"qwen-plus-latest"  # 使用纯文本模型分析表格

        # 创建速率限制器，每秒最多2个请求

        self.rate_limiter = AsyncLimiter(settings.research_report.rate_limiter, 1)

        # 初始化 Markdown 分块器
        self._splitter: Optional[MarkdownReportSplitter] = None

    @property
    def splitter(self) -> MarkdownReportSplitter:
        if self._splitter is None:
            self._splitter = MarkdownReportSplitter(concurrency=5)
        return self._splitter

    async def process_pdf(self, report_type: str, report_id: int):
        """
        处理 PDF
        """
        async with dbm.session() as db:
            async with dbm.session('report_db') as report_db:
                if report_type == "stock":
                    query = select(StockResearchReport).where(and_(StockResearchReport.id == report_id, StockResearchReport.download == DownloadStatusEnum.yes))
                else:
                    query = select(IndustryResearchReport).where(and_(IndustryResearchReport.id == report_id, IndustryResearchReport.download == DownloadStatusEnum.yes))
                report = await report_db.execute(query)
                report = report.scalars().first()
                if not report:
                    return None, '研报不存在'
                file_path = self.get_file_path(report_type, report.title, report.trade_date.strftime("%Y-%m-%d"))
                # 检查 PDF 文件是否存在
                if not os.path.exists(file_path):
                    _logger.warning(f"PDF 文件不存在：{file_path}")
                    return None, f'PDF文件不存在：{report.title}'
                if report_type == "stock":
                    record_query = select(StockResearchReportRecord).where(StockResearchReportRecord.report_id == report_id)
                else:
                    record_query = select(IndustryResearchReportRecord).where(IndustryResearchReportRecord.report_id == report_id)
                record = await db.execute(record_query)
                record = record.scalars().first()
                if record and record.process_status == ProcessStatusEnum.done:
                    return record.output_path, '研报已处理'
                elif record and record.process_status in (ProcessStatusEnum.pdf_analyzed,
                                                          ProcessStatusEnum.image_analyzed,
                                                          ProcessStatusEnum.integrated, ProcessStatusEnum.chunked,
                                                          ProcessStatusEnum.chunked_to_db):
                    return record.output_path, '研报处理中'
                elif record and record.process_status in (ProcessStatusEnum.failed, ProcessStatusEnum.no):
                    record.process_status = ProcessStatusEnum.no
                    record.process_start = datetime.datetime.now()
                    await db.commit()
                else:
                    if report_type == "stock":
                        record = StockResearchReportRecord(report_id=report.id, filename=report.title, trade_date=report.trade_date,
                                                           file_path=file_path, process_start=datetime.datetime.now(),
                                                           ts_code=report.ts_code, symbol=report.symbol, company_name=report.company_name,
                                                           org_name=report.org_name, org_code=report.org_code,
                                                           info_code=report.info_code, process_status=ProcessStatusEnum.no)
                    else:
                        record = IndustryResearchReportRecord(report_id=report.id, filename=report.title, trade_date=report.trade_date,
                                                              file_path=file_path, process_start=datetime.datetime.now(),
                                                              industry_name=report.industry_name, org_name=report.org_name, org_code=report.org_code,
                                                              info_code=report.info_code, process_status=ProcessStatusEnum.no)
                    db.add(record)
                    await db.commit()
                await self.process_single_pdf(report_type, report.id, report.title, report.trade_date.strftime("%Y-%m-%d"))
                return True, '处理成功'

    def get_file_path(self, report_type:str, filename: str, trade_date: str):
        """
        获取文件路径
        """
        file_path = self.report_dir + report_type + "/" + trade_date + "/" + filename
        if file_path.endswith(".pdf"):
            return file_path
        return file_path + ".pdf"

    def generate_output_path(self, report_type:str, report_id: str):
        """
        获取输出路径
        """
        output_path = self.output_dir + report_type + "/" + report_id
        return output_path

    async def process_single_pdf(self, report_type:str, report_id:int, filename: str, trade_date: str):
        """
        异步处理单个 PDF（对应命令行：mineru -p "$file" -o "$0/$name" -b vlm-http-client -u http://192.168.1.119:30000）
        """
        file_path = self.get_file_path(report_type, filename, trade_date)
        output_dir = self.generate_output_path(report_type, str(report_id))
        # 读取 PDF 字节
        pdf_bytes = read_fn(file_path)

        # 异步调用 vlm-http-client 后端
        await aio_do_parse(
            output_dir=output_dir,
            pdf_file_names=[filename],  # 文件名（不含扩展名）
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=["ch"],  # 语言：中文
            backend="vlm-http-client",  # 远程 VLM 后端
            server_url=self.mineru_server,  # 远程服务地址
            formula_enable=True,  # 启用公式识别
            table_enable=True,  # 启用表格识别
            f_dump_md=True,  # 输出 Markdown
            f_dump_content_list=True,  # 输出结构化内容
            f_draw_layout_bbox=False,  # 不绘制布局框（提升速度）
            f_draw_span_bbox=False  # 不绘制文本框
        )

        _logger.info(f"✅ 完成: {filename} -> {output_dir}/{filename}.md")
        async with dbm.session() as db:
            if report_type == "stock":
                query = select(StockResearchReportRecord).where(StockResearchReportRecord.report_id == report_id)
            else:
                query = select(IndustryResearchReportRecord).where(IndustryResearchReportRecord.report_id == report_id)
            record = await db.execute(query)
            record = record.scalars().first()
            record.process_status = ProcessStatusEnum.pdf_analyzed
            record.output_path = output_dir
            await db.commit()
        # markdown_file_path = f'{output_dir}/{filename}.md'
        await self.process_image_analyze(report_type, report_id,f'{output_dir}/{filename}/vlm')

        return f'{output_dir}/{filename}.md'

    def clean_markdown_content(self, content):

        """清理Markdown内容中的格式问题"""

        lines = content.split('\n')

        cleaned_lines = []

        for line in lines:

            # 处理标题行

            if re.match(r'^#{1,6}\s', line):

                cleaned_line = self._clean_title_line(line)

            else:

                # 处理普通文本行

                cleaned_line = self._clean_text_line(line)

            cleaned_lines.append(cleaned_line)

        return '\n'.join(cleaned_lines)

    async def analyze_image(self, image_path: str, prompt: Optional[str] = None) -> Dict[str, str]:
        """
        分析单张图片

        Args:
            image_path: 图片文件路径
            prompt: 自定义提示词 (可选)

        Returns:
            包含 title 和 description 的字典
        """
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
            dashscope.api_key = self.api_key

            async with self.rate_limiter:
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
                        model=self.image_model,
                        messages=messages,
                        result_format='message',
                        stream=False
                    )
                )

                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    if isinstance(content, list):
                        content = ''.join([item.get('text', '') for item in content if isinstance(item, dict)])
                    return self._parse_result(content, "image")
                else:
                    return {"title": "图片分析失败", "description": f"API错误: {response.message}"}

        except ImportError:
            return await self._analyze_image_http(image_path, prompt)
        except Exception as e:
            _logger.error(f"分析图片出错: {e}")
            return {"title": "图片分析失败", "description": f"分析出错: {str(e)}"}

    async def _analyze_image_http(self, image_path: str, prompt: str) -> Dict[str, str]:
        """使用HTTP方式分析图片"""
        try:
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')

            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.image_model,
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
            async with self.rate_limiter:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.image_api_url, headers=headers, json=payload) as resp:
                        if resp.status != 200:
                            return {"title": "图片分析失败", "description": f"HTTP错误: {resp.status}"}

                        result = await resp.json()
                        if 'output' in result and 'choices' in result['output']:
                            content = result['output']['choices'][0]['message']['content']
                            if isinstance(content, list):
                                content = ''.join([item.get('text', '') for item in content])
                            return self._parse_result(content, "image")
                        return {"title": "图片分析失败", "description": "响应格式错误"}
        except Exception as e:
            return {"title": "图片分析失败", "description": f"HTTP分析出错: {str(e)}"}

    async def analyze_html_table(self, html_content: str, prompt: Optional[str] = None) -> Dict[str, str]:
        """
        分析HTML表格

        Args:
            html_content: HTML表格内容
            prompt: 自定义提示词 (可选)

        Returns:
            包含 title 和 description 的字典
        """
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
            dashscope.api_key = self.api_key

            async with self.rate_limiter:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: Generation.call(
                        model=self.table_model,
                        prompt=full_prompt,
                        result_format='message',
                        stream=False
                    )
                )

                if response.status_code == 200:
                    content = response.output.text if hasattr(response.output, 'text') else str(response.output)
                    return self._parse_result(content, "table")
                else:
                    return {"title": "表格分析失败", "description": f"API错误: {response.message}"}

        except ImportError:
            return await self._analyze_html_http(html_content, full_prompt)
        except Exception as e:
            _logger.error(f"分析HTML表格出错: {e}")
            return {"title": "表格分析失败", "description": f"分析出错: {str(e)}"}

    async def _analyze_html_http(self, html_content: str, prompt: str) -> Dict[str, str]:
        """使用HTTP方式分析HTML表格"""
        try:
            import aiohttp
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.table_model,
                "input": {"prompt": prompt},
                "parameters": {"stream": False}
            }

            async with self.rate_limiter:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.text_api_url, headers=headers, json=payload) as resp:
                        if resp.status != 200:
                            return {"title": "表格分析失败", "description": f"HTTP错误: {resp.status}"}

                        result = await resp.json()
                        if 'output' in result and 'text' in result['output']:
                            return self._parse_result(result['output']['text'], "table")
                        return {"title": "表格分析失败", "description": "响应格式错误"}
        except Exception as e:
            return {"title": "表格分析失败", "description": f"HTTP分析出错: {str(e)}"}

    def _parse_result(self, content: Any, result_type: str = "image") -> Dict[str, str]:
        """
        解析API返回结果

        Args:
            content: API返回的原始内容
            result_type: 结果类型，"image" 或 "table"

        Returns:
            包含 title 和 description 的字典
        """
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
                title = self._clean_title(title_match.group(1).strip(), result_type)
                description = self._clean_description(desc_match.group(1).strip())
            else:
                title = f"{'表格' if result_type == 'table' else '图片'}内容"
                description = content[:500] if len(content) > 500 else content

            if len(description) > 500:
                description = description[:497] + "..."

            return {"title": title, "description": description}

        except Exception as e:
            return {"title": "解析失败", "description": f"解析出错: {str(e)}"}

    def _clean_title(self, title: str, title_type: str = "image") -> str:
        """清理标题"""
        if not title:
            return "分析结果"
        title = re.sub(r'\{COMPANY_NAME\}\s*-?\s*', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'[{}[\]\'"]', '', title)
        if len(title.strip()) < 2:
            title = "表格数据" if title_type == "table" else "图片内容"
        return title

    def _clean_description(self, description: str) -> str:
        """清理描述"""
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

    def _clean_title_line(self, title_line: str) -> str:
        """清理标题行"""
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

    def _clean_text_line(self, text_line: str) -> str:
        """清理文本行"""
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

    async def process_markdown_file(self, report_type: str, report_id: int, md_file_path: str,
                                    output_file_path: Optional[str] = None,
                                    image_dir: Optional[str] = None,
                                    concurrency: int = 5) -> bool:
        """
        处理单个Markdown文件

        Args:
            md_file_path: Markdown文件路径
            output_file_path: 输出文件路径 (默认覆盖原文件)
            image_dir: 图片目录路径 (可选)
            concurrency: 并发处理数 (默认: 5)

        Returns:
            处理是否成功
        """
        if output_file_path is None:
            output_file_path = md_file_path

        if not os.path.exists(md_file_path):
            _logger.error(f"文件不存在: {md_file_path}")
            return False

        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = self.clean_markdown_content(content)

        html_pattern = r'<html><body><table>.*?</table></body></html>'
        html_matches = list(re.finditer(html_pattern, content, re.DOTALL))

        img_pattern = r'!\[([^\]]*)\]\(([^)]*\.jpg)\)'
        img_matches = list(re.finditer(img_pattern, content))

        if not html_matches and not img_matches:
            _logger.info(f"未找到HTML表格或图片: {md_file_path}")
            return False

        md_dir = os.path.dirname(os.path.abspath(md_file_path))
        tasks = []

        for match in reversed(html_matches):
            html_content = match.group(0)
            start_pos = match.start()
            end_pos = match.end()

            after_html = content[end_pos:end_pos + 500]
            if "<!-- 表格图片版本 -->" in after_html:
                img_match = re.search(r'!\[([^\]]*)\]\(([^)]*\.jpg)\)', after_html)
                if img_match:
                    img_start = end_pos + after_html.find(img_match.group(0))
                    img_end = img_start + len(img_match.group(0))
                    tasks.append({
                        'type': 'html_table',
                        'html_content': html_content,
                        'html_start': start_pos, 'html_end': end_pos,
                        'comment_start': end_pos + after_html.find("<!-- 表格图片版本 -->"),
                        'img_start': img_start, 'img_end': img_end,
                        'img_tag': img_match.group(0)
                    })
                    continue

            tasks.append({
                'type': 'html_table_only',
                'html_content': html_content,
                'start_pos': start_pos, 'end_pos': end_pos
            })

        for match in reversed(img_matches):
            img_tag = match.group(0)
            img_path = match.group(2)
            start_pos = match.start()
            end_pos = match.end()

            if img_path.startswith('http'):
                continue

            possible_paths = []
            if image_dir:
                possible_paths.append(os.path.join(image_dir, os.path.basename(img_path)))
            possible_paths.append(os.path.join(md_dir, img_path))
            if os.path.isabs(img_path):
                possible_paths.append(img_path)
            possible_paths.append(os.path.join(md_dir, img_path.lstrip('.' + os.path.sep)))

            full_img_path = None
            for path in possible_paths:
                if os.path.exists(os.path.normpath(path)):
                    full_img_path = os.path.normpath(path)
                    break

            if not full_img_path:
                continue

            preceding_text = content[:start_pos]
            if "<!-- 表格图片版本 -->" in preceding_text[-200:]:
                continue

            tasks.append({
                'type': 'image',
                'img_path': full_img_path,
                'img_tag': img_tag,
                'start_pos': start_pos, 'end_pos': end_pos
            })

        if not tasks:
            return False

        semaphore = asyncio.Semaphore(concurrency)

        async def process_item(task):
            async with semaphore:
                if task['type'] == 'html_table' or task['type'] == 'html_table_only':
                    return task, await self.analyze_html_table(task['html_content'])
                elif task['type'] == 'image':
                    return task, await self.analyze_image(task['img_path'])

        results = await asyncio.gather(*[process_item(t) for t in tasks])

        results.sort(key=lambda x: x[0].get('start_pos', x[0].get('html_start', 0)), reverse=True)

        for task, analysis_result in results:
            task_type = task['type']
            if task_type == 'html_table':
                insert_text = f"### 表格标题：{analysis_result['title']}\n表格描述：{analysis_result['description']}\n{task['img_tag']}"
                content = content[:task['html_start']] + insert_text + content[task['img_end']:]
            elif task_type == 'html_table_only':
                insert_text = f"### 表格标题：{analysis_result['title']}\n表格描述：{analysis_result['description']}\n"
                content = content[:task['start_pos']] + insert_text + content[task['end_pos']:]
            elif task_type == 'image':
                insert_text = f"### 图片标题：{analysis_result['title']}\n图片描述：{analysis_result['description']}\n{task['img_tag']}"
                content = content[:task['start_pos']] + insert_text + content[task['end_pos']:]

        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        _logger.info(f"处理完成: {output_file_path}")
        async with dbm.session() as db:
            if report_type == "stock":
                query = select(StockResearchReportRecord).where(StockResearchReportRecord.report_id == report_id)
            else:
                query = select(IndustryResearchReportRecord).where(IndustryResearchReportRecord.report_id == report_id)
            record = await db.execute(query)
            record = record.scalars().first()
            record.process_status = ProcessStatusEnum.integrated
            await db.commit()
        return True

    async def process_image_analyze(self, report_type: str, report_id: int, directory: str, recursive: bool = True,
                                    output_dir: Optional[str] = None, concurrency: int = 5) -> int:
        """
        批量处理目录中的Markdown文件

        Args:
            directory: 目录路径
            recursive: 是否递归处理子目录
            output_dir: 输出目录 (默认覆盖原文件)
            concurrency: 并发处理数

        Returns:
            处理成功的文件数量
        """
        directory = Path(directory)
        if not directory.exists():
            _logger.error(f"目录不存在: {directory}")
            return 0

        pattern = '**/*.md' if recursive else '*.md'
        md_files = list(directory.glob(pattern))

        if not md_files:
            _logger.warning(f"未找到Markdown文件: {directory}")
            return 0

        semaphore = asyncio.Semaphore(concurrency)

        async def process_file(report_type, report_id, md_file):
            async with semaphore:
                output_path = None
                if output_dir:
                    rel_path = md_file.relative_to(directory)
                    output_path = Path(output_dir) / rel_path
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                img_dir = md_file.parent / "images"
                return await self.process_markdown_file(
                    report_type, report_id, str(md_file),
                    str(output_path) if output_path else None,
                    str(img_dir) if img_dir.exists() else None,
                    concurrency=1
                )

        results = await asyncio.gather(*[process_file(report_type, report_id, f) for f in md_files])
        success_count = sum(results)
        _logger.info(f"处理完成: {success_count}/{len(md_files)} 个文件")
        return success_count

    async def extract_company_info(self, report_type: str, report_id: int):
        if report_type == "industry":
            return {}
        async with dbm.session() as db:
            query = select(StockResearchReportRecord).where(StockResearchReportRecord.report_id == report_id)
            record = await db.execute(query)
            record = record.scalars().first()
            if not record:
                return {}
            return {
                'ts_code': record.ts_code,
                'company_name': record.company_name,
            }

    async def extract_industry_info(self, report_type: str, report_id: int):
        async with dbm.session() as db:
            if report_type == "stock":
                query = select(StockResearchReportRecord).where(StockResearchReportRecord.report_id == report_id)
            else:
                query = select(IndustryResearchReportRecord).where(IndustryResearchReportRecord.report_id == report_id)
            record = await db.execute(query)
            record = record.scalars().first()
            if not record:
                return {}
            return {
                'industry_name': record.industry_name,
            }

    async def chunk_markdown(self, report_type: str, report_id: int) -> dict:
        """对研报 Markdown 进行分块处理

        Args:
            report_type: 研报类型，"stock" 或 "industry"
            report_id: 研报 ID

        Returns:
            处理结果 dict
        """
        async with dbm.session() as db:
            if report_type == "stock":
                record_query = select(StockResearchReportRecord).where(
                    StockResearchReportRecord.report_id == report_id
                )
            else:
                record_query = select(IndustryResearchReportRecord).where(
                    IndustryResearchReportRecord.report_id == report_id
                )

            result = await db.execute(record_query)
            record = result.scalars().first()

            if not record:
                return {"success": False, "message": "研报记录不存在"}

            if record.process_status != ProcessStatusEnum.integrated:
                return {"success": False, "message": f"当前状态为 {record.process_status}，需要先完成 integrated 状态"}

            output_path = record.output_path
            if not output_path or not os.path.exists(output_path):
                return {"success": False, "message": "输出路径不存在"}

            md_filename = record.filename
            md_file_path = os.path.join(output_path, md_filename, "vlm", f"{md_filename}.md")

            if not os.path.exists(md_file_path):
                md_file_path = os.path.join(output_path, md_filename, f"{md_filename}.md")

            if not os.path.exists(md_file_path):
                return {"success": False, "message": f"Markdown 文件不存在: {md_file_path}"}

            try:
                chunks = self.splitter.split_file(md_file_path)
                if not chunks:
                    return {"success": False, "message": "分块结果为空"}

                json_output_path = os.path.join(output_path, "chunks.json")
                save_success = self.splitter.save_chunks_json(chunks, json_output_path)

                if not save_success:
                    return {"success": False, "message": "保存 JSON 失败"}

                record.process_status = ProcessStatusEnum.chunked
                await db.commit()

                return {
                    "success": True,
                    "message": "分块成功",
                    "chunk_count": len(chunks),
                    "output_path": json_output_path,
                }

            except Exception as e:
                _logger.error(f"分块处理失败: {e}")
                return {"success": False, "message": f"分块失败: {str(e)}"}

    async def chunk_batch(self, report_type: str, report_ids: list[int]) -> list[dict]:
        """批量并行处理研报分块

        Args:
            report_type: 研报类型，"stock" 或 "industry"
            report_ids: 研报 ID 列表

        Returns:
            处理结果列表
        """
        semaphore = asyncio.Semaphore(self.splitter.concurrency)

        async def process_one(report_id: int) -> dict:
            async with semaphore:
                return await self.chunk_markdown(report_type, report_id)

        results = await asyncio.gather(
            *[process_one(rid) for rid in report_ids],
            return_exceptions=True
        )

        processed_results = []
        for rid, result in zip(report_ids, results):
            if isinstance(result, Exception):
                processed_results.append({
                    "report_id": rid,
                    "success": False,
                    "message": str(result),
                })
            else:
                processed_results.append({
                    "report_id": rid,
                    **result,
                })

        success_count = sum(1 for r in processed_results if r.get("success", False))
        _logger.info(f"批量分块完成: {success_count}/{len(report_ids)} 成功")

        return processed_results