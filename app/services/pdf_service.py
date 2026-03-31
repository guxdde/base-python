import datetime
from sqlalchemy import select, and_
import logging
import os
from typing import Optional

from app.core.config import settings
from app.models.chunk import ProcessStatusEnum, StockResearchReportRecord, IndustryResearchReportRecord
from app.models.report import StockResearchReport, DownloadStatusEnum, IndustryResearchReport
from app.core.database import dbm
from app.services.markdown_splitter import MarkdownReportSplitter
from app.pipeline import PDFProcessingPipeline
from app.services import pdf_utils

_logger = logging.getLogger(__name__)


class PDFService:

    def __init__(self):
        self.report_dir = settings.research_report.report_dir
        self.output_dir = settings.research_report.output_dir
        self.mineru_server = settings.research_report.mineru_server
        self._splitter: Optional[MarkdownReportSplitter] = None
        self._pipeline: Optional[PDFProcessingPipeline] = None

    @property
    def splitter(self) -> MarkdownReportSplitter:
        if self._splitter is None:
            self._splitter = MarkdownReportSplitter(concurrency=5)
        return self._splitter

    @property
    def pipeline(self) -> PDFProcessingPipeline:
        if self._pipeline is None:
            self._pipeline = PDFProcessingPipeline()
        return self._pipeline

    async def process_pdf(self, report_type: str, report_id: int):
        """处理 PDF，使用流水线框架"""
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
                if not os.path.exists(file_path):
                    _logger.warning(f"PDF 文件不存在：{file_path}")
                    return None, f'PDF文件不存在：{report.title}'

                if report_type == "stock":
                    record_query = select(StockResearchReportRecord).where(StockResearchReportRecord.report_id == report_id)
                else:
                    record_query = select(IndustryResearchReportRecord).where(IndustryResearchReportRecord.report_id == report_id)
                record = await db.execute(record_query)
                record = record.scalars().first()

                if record and record.process_status == ProcessStatusEnum.chunked_to_db:
                    return record.output_path, '研报已处理'

                if record and record.process_status != ProcessStatusEnum.no:
                    _logger.info(f"继续处理: {report_type}:{report_id}, 当前状态: {record.process_status}")
                    trade_date_str = record.trade_date.strftime("%Y-%m-%d") if record.trade_date else None
                    result = await self.pipeline.execute(
                        report_type, report_id, record.filename, trade_date_str, db
                    )
                    if result.get("completed"):
                        return record.output_path, '处理成功'
                    else:
                        failed_step = next((r["step"] for r in result.get("results", []) if not r["success"]), None)
                        return None, f'处理失败: {failed_step}'

                if record and record.process_status == ProcessStatusEnum.no:
                    record.process_status = ProcessStatusEnum.no
                    record.process_start = datetime.datetime.now()
                    await db.commit()
                else:
                    if report_type == "stock":
                        record = StockResearchReportRecord(
                            report_id=report.id, filename=report.title, trade_date=report.trade_date,
                            file_path=file_path, process_start=datetime.datetime.now(),
                            ts_code=report.ts_code or report.symbol, symbol=report.symbol,
                            company_name=report.company_name, org_name=report.org_name,
                            org_code=report.org_code, info_code=report.info_code,
                            process_status=ProcessStatusEnum.no
                        )
                    else:
                        record = IndustryResearchReportRecord(
                            report_id=report.id, filename=report.title, trade_date=report.trade_date,
                            file_path=file_path, process_start=datetime.datetime.now(),
                            industry_name=report.industry_name, org_name=report.org_name,
                            org_code=report.org_code, info_code=report.info_code,
                            process_status=ProcessStatusEnum.no
                        )
                    db.add(record)
                    await db.commit()

                trade_date_str = report.trade_date.strftime("%Y-%m-%d")
                result = await self.pipeline.execute(
                    report_type, report.id, report.title, trade_date_str, db
                )
                if result.get("completed"):
                    return True, '处理成功'
                else:
                    failed_step = next((r["step"] for r in result.get("results", []) if not r["success"]), None)
                    return None, f'处理失败: {failed_step}'

    def get_file_path(self, report_type: str, filename: str, trade_date: str):
        """获取文件路径"""
        file_path = self.report_dir + report_type + "/" + trade_date + "/" + filename
        if file_path.endswith(".pdf"):
            return file_path
        return file_path + ".pdf"

    def generate_output_path(self, report_type: str, report_id: str):
        """获取输出路径"""
        output_path = self.output_dir + report_type + "/" + report_id
        return output_path

    async def chunk_batch(self, report_type: str, report_ids: list) -> list:
        """批量并行处理研报分块"""
        import asyncio
        semaphore = asyncio.Semaphore(self.splitter.concurrency)

        async def process_one(report_id: int) -> dict:
            async with semaphore:
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
                        return {"report_id": report_id, "success": False, "message": "记录不存在"}

                    if record.process_status != ProcessStatusEnum.integrated:
                        return {
                            "report_id": report_id,
                            "success": False,
                            "message": f"当前状态为 {record.process_status}，需要先完成 integrated 状态"
                        }

                    output_path = record.output_path
                    if not output_path or not os.path.exists(output_path):
                        return {"report_id": report_id, "success": False, "message": "输出路径不存在"}

                    md_filename = record.filename
                    md_file_path = os.path.join(output_path, md_filename, "vlm", f"{md_filename}.md")
                    if not os.path.exists(md_file_path):
                        md_file_path = os.path.join(output_path, md_filename, f"{md_filename}.md")

                    if not os.path.exists(md_file_path):
                        return {"report_id": report_id, "success": False, "message": f"Markdown 文件不存在"}

                    try:
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

                        chunks = self.splitter.split_file(md_file_path)
                        if not chunks:
                            return {"report_id": report_id, "success": False, "message": "分块结果为空"}

                        report_summary = await pdf_utils.generate_report_summary(
                            " ".join([chunk.page_content for chunk in chunks])
                        )
                        _logger.info(f"[PDFService] report_summary长度: {len(report_summary)}, report_id: {report_id}")

                        async def process_chunk_with_metadata(chunk, index):
                            async with semaphore:
                                chunk.metadata.update(base_metadata)
                                chunk.metadata["chunk_index"] = index
                                chunk.metadata["report_summary"] = report_summary

                                _logger.info(f"[PDFService] 开始生成chunk {index} 的摘要")
                                contextual_summary = await pdf_utils.generate_contextual_summary(
                                    chunk_content=chunk.page_content,
                                    report_summary=report_summary,
                                    header_path=chunk.metadata.get("header_path", ""),
                                    report_title=record.title if hasattr(record, 'title') else "",
                                    chunk_index=index
                                )
                                _logger.info(f"[PDFService] chunk {index} 摘要长度: {len(contextual_summary)}")
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
                        save_success = self.splitter.save_chunks_json(chunks, json_output_path)

                        if not save_success:
                            return {"report_id": report_id, "success": False, "message": "保存 JSON 失败"}

                        record.process_status = ProcessStatusEnum.chunked
                        await db.commit()

                        from app.services.vector_service import insert_chunks_to_milvus
                        vector_result = await insert_chunks_to_milvus(report_type, report_id)
                        if vector_result.get("success"):
                            record.process_status = ProcessStatusEnum.chunked_to_db
                            record.process_end = datetime.datetime.now()
                            await db.commit()

                        return {
                            "report_id": report_id,
                            "success": True,
                            "message": "分块成功",
                            "chunk_count": len(chunks),
                            "vector_inserted": vector_result.get("success", False)
                        }

                    except Exception as e:
                        _logger.error(f"分块处理失败: {e}")
                        return {"report_id": report_id, "success": False, "message": str(e)}

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
                processed_results.append(result)

        success_count = sum(1 for r in processed_results if r.get("success", False))
        _logger.info(f"批量分块完成: {success_count}/{len(report_ids)} 成功")

        return processed_results


