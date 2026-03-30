import logging
import os
import re
from typing import Any, Optional

from app.core.pipeline import PipelineStep, StepResult
from app.models.chunk import ProcessStatusEnum
from app.services import pdf_utils
from app.services.markdown_splitter import MarkdownReportSplitter
from app.services.vector_service import insert_chunks_to_milvus
from app.core.config import settings

logger = logging.getLogger(__name__)


class MineruParsingStep(PipelineStep):
    name = "mineru_parsing"
    target_state = ProcessStatusEnum.pdf_analyzed
    optional = False

    async def can_execute(self, record: Any, context: dict) -> bool:
        return record.process_status == ProcessStatusEnum.no

    async def execute(self, record: Any, context: dict) -> StepResult:
        try:
            report_type = context["report_type"]
            report_id = context["report_id"]
            filename = context["filename"]
            trade_date = context["trade_date"]

            report_dir = settings.research_report.report_dir
            output_dir = settings.research_report.output_dir
            mineru_server = settings.research_report.mineru_server

            file_path = report_dir + report_type + "/" + trade_date + "/" + filename
            if not file_path.endswith(".pdf"):
                file_path += ".pdf"
            output_dir = output_dir + report_type + "/" + str(report_id)

            if not os.path.exists(file_path):
                return StepResult(success=False, message=f"PDF 文件不存在: {file_path}")

            from mineru.cli.common import aio_do_parse, read_fn
            pdf_bytes = read_fn(file_path)

            await aio_do_parse(
                output_dir=output_dir,
                pdf_file_names=[filename],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=["ch"],
                backend="vlm-http-client",
                server_url=mineru_server,
                formula_enable=True,
                table_enable=True,
                f_dump_md=True,
                f_dump_content_list=True,
                f_draw_layout_bbox=False,
                f_draw_span_bbox=False
            )

            record.output_path = output_dir
            logger.info(f"Mineru 解析完成: {filename} -> {output_dir}")

            return StepResult(
                success=True,
                message="PDF 解析完成",
                data={"output_dir": output_dir, "filename": filename}
            )

        except Exception as e:
            logger.exception(f"Mineru 解析失败")
            return StepResult(success=False, message=f"PDF 解析失败: {str(e)}")


class ImageTableAnalyzeStep(PipelineStep):
    name = "image_table_analyze"
    target_state = ProcessStatusEnum.integrated
    optional = True

    async def can_execute(self, record: Any, context: dict) -> bool:
        return record.process_status == ProcessStatusEnum.pdf_analyzed

    async def execute(self, record: Any, context: dict) -> StepResult:
        try:
            report_type = context["report_type"]
            report_id = context["report_id"]
            filename = context["filename"]

            output_dir = record.output_path
            if not output_dir:
                output_dir = settings.research_report.output_dir + report_type + "/" + str(report_id)

            vlm_dir = f"{output_dir}/{filename}/vlm"

            if not os.path.exists(vlm_dir):
                logger.info(f"VLM 目录不存在，跳过图片分析: {vlm_dir}")
                return StepResult(
                    success=True,
                    message="VLM 目录不存在，视为已处理",
                    data={"status": "skipped"}
                )

            md_file_path = os.path.join(vlm_dir, f"{filename}.md")
            if not os.path.exists(md_file_path):
                md_file_path = os.path.join(output_dir, f"{filename}.md")

            if not os.path.exists(md_file_path):
                return StepResult(success=False, message=f"Markdown 文件不存在: {md_file_path}")

            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            content = pdf_utils.clean_markdown_content(content)

            html_pattern = r'<html><body><table>.*?</table></body></html>'
            html_matches = list(re.finditer(html_pattern, content, re.DOTALL))

            img_pattern = r'!\[([^\]]*)\]\(([^)]*\.jpg)\)'
            img_matches = list(re.finditer(img_pattern, content))

            if not html_matches and not img_matches:
                logger.info(f"Mineru 已处理完成，无需额外分析: {md_file_path}")
                return StepResult(
                    success=True,
                    message="Mineru 已处理完成，无需额外分析",
                    data={"status": "mineru_processed"}
                )

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

                possible_paths = [
                    os.path.join(md_dir, img_path),
                    os.path.join(md_dir, img_path.lstrip('.' + os.path.sep))
                ]
                if os.path.isabs(img_path):
                    possible_paths.append(img_path)

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
                logger.info(f"所有内容已被 Mineru 处理，无需额外分析: {md_file_path}")
                return StepResult(
                    success=True,
                    message="所有内容已被 Mineru 处理",
                    data={"status": "mineru_processed"}
                )

            import asyncio
            semaphore = asyncio.Semaphore(5)

            async def process_item(task):
                async with semaphore:
                    if task['type'] == 'html_table' or task['type'] == 'html_table_only':
                        return task, await pdf_utils.analyze_html_table(task['html_content'])
                    elif task['type'] == 'image':
                        return task, await pdf_utils.analyze_image(task['img_path'])

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

            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"图片表格分析完成: {md_file_path}")

            return StepResult(
                success=True,
                message="图片表格分析完成",
                data={"tasks_processed": len(tasks)}
            )

        except Exception as e:
            logger.exception(f"图片表格分析失败")
            return StepResult(success=False, message=f"图片表格分析失败: {str(e)}")


class MarkdownChunkingStep(PipelineStep):
    name = "markdown_chunking"
    target_state = ProcessStatusEnum.chunked
    optional = False

    async def can_execute(self, record: Any, context: dict) -> bool:
        return record.process_status == ProcessStatusEnum.integrated

    async def execute(self, record: Any, context: dict) -> StepResult:
        try:
            report_type = context["report_type"]
            report_id = context["report_id"]
            filename = context["filename"]

            output_path = record.output_path
            if not output_path:
                output_path = settings.research_report.output_dir + report_type + "/" + str(report_id)

            md_file_path = os.path.join(output_path, filename, "vlm", f"{filename}.md")
            if not os.path.exists(md_file_path):
                md_file_path = os.path.join(output_path, filename, f"{filename}.md")

            if not os.path.exists(md_file_path):
                return StepResult(success=False, message=f"Markdown 文件不存在: {md_file_path}")

            with open(md_file_path, 'r', encoding='utf-8') as f:
                full_markdown_content = f.read()

            base_metadata = {
                "report_type": report_type,
                "report_id": report_id,
                "filename": record.filename,
                "trade_date": record.trade_date.strftime("%Y-%m-%d") if record.trade_date else None,
                "ts_code": getattr(record, 'ts_code', None),
                "company_name": getattr(record, 'company_name', None),
                "industry_name": getattr(record, 'industry_name', None),
                "org_name": record.org_name,
            }

            splitter = MarkdownReportSplitter(concurrency=5)
            chunks = splitter.split_file(md_file_path)
            if not chunks:
                return StepResult(success=False, message="分块结果为空")

            report_title = chunks[0].metadata.get("report_title", "") if chunks else ""

            logger.info(f"生成整篇报告摘要...")
            report_summary = await pdf_utils.generate_report_summary(full_markdown_content)
            logger.info(f"报告摘要生成完成: {report_summary[:100]}...")

            import asyncio
            semaphore = asyncio.Semaphore(10)

            async def process_chunk_with_metadata(chunk, index):
                async with semaphore:
                    chunk.metadata.update(base_metadata)
                    chunk.metadata["chunk_index"] = index
                    chunk.metadata["report_summary"] = report_summary

                    contextual_summary = await pdf_utils.generate_contextual_summary(
                        chunk_content=chunk.page_content,
                        report_summary=report_summary,
                        header_path=chunk.metadata.get("header_path", ""),
                        report_title=report_title or chunk.metadata.get("report_title", ""),
                        chunk_index=index
                    )
                    chunk.metadata["summary"] = contextual_summary

                    if report_type == "industry":
                        related_stocks = await pdf_utils.extract_related_stocks(chunk.page_content)
                        chunk.metadata["related_stocks"] = related_stocks
                    else:
                        chunk.metadata["related_stocks"] = []

                    return chunk

            chunks = await asyncio.gather(*[
                process_chunk_with_metadata(chunk, i)
                for i, chunk in enumerate(chunks)
            ])

            json_output_path = os.path.join(output_path, "chunks.json")
            save_success = splitter.save_chunks_json(chunks, json_output_path)

            if not save_success:
                return StepResult(success=False, message="保存 JSON 失败")

            logger.info(f"Markdown 分块完成: {len(chunks)} 个 chunk (上下文增强摘要)")

            return StepResult(
                success=True,
                message=f"分块成功，共 {len(chunks)} 个 chunk (上下文增强摘要)",
                data={
                    "chunk_count": len(chunks),
                    "output_path": json_output_path,
                    "report_summary": report_summary
                }
            )

        except Exception as e:
            logger.exception(f"Markdown 分块失败")
            return StepResult(success=False, message=f"分块失败: {str(e)}")


class MilvusStorageStep(PipelineStep):
    name = "milvus_storage"
    target_state = ProcessStatusEnum.chunked_to_db
    optional = False

    async def can_execute(self, record: Any, context: dict) -> bool:
        return record.process_status == ProcessStatusEnum.chunked

    async def execute(self, record: Any, context: dict) -> StepResult:
        try:
            report_type = context["report_type"]
            report_id = context["report_id"]

            result = await insert_chunks_to_milvus(report_type, report_id)

            if result.get("success"):
                logger.info(f"Milvus 向量入库成功: {report_type}:{report_id}")
                return StepResult(
                    success=True,
                    message="向量入库成功",
                    data={"inserted_count": result.get("inserted_count", 0)}
                )
            else:
                return StepResult(
                    success=False,
                    message=f"向量入库失败: {result.get('message', '未知错误')}"
                )

        except Exception as e:
            logger.exception(f"Milvus 向量入库失败")
            return StepResult(success=False, message=f"向量入库失败: {str(e)}")
