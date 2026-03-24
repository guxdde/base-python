import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain.schema import Document

from app.core.database import dbm
from app.models.chunk import ProcessStatusEnum, StockResearchReportRecord, IndustryResearchReportRecord
from sqlalchemy import select

_logger = logging.getLogger(__name__)


class MarkdownReportSplitter:
    """Markdown 研报结构化分块器"""

    def __init__(
        self,
        headers_to_split_on: list[tuple[str, str]] = None,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        concurrency: int = 5,
    ):
        if headers_to_split_on is None:
            headers_to_split_on = [
                ("#", "一级标题"),
                ("##", "二级标题"),
                ("###", "三级标题"),
            ]
        self.headers_to_split_on = headers_to_split_on
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.concurrency = concurrency

        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            return_each_line=False,
        )

        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[r"|\n", "\n\n", "\n", " "],
            keep_separator=False,
        )

    def split_file(self, file_path: str) -> list[Document]:
        """从文件路径分割 Markdown 文件"""
        if not os.path.exists(file_path):
            _logger.error(f"文件不存在: {file_path}")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                markdown_text = f.read()
            return self.split_text(markdown_text)
        except Exception as e:
            _logger.error(f"读取文件失败 {file_path}: {e}")
            return []

    def split_text(self, markdown_text: str) -> list[Document]:
        """分割 Markdown 文本"""
        if not markdown_text:
            return []

        try:
            header_chunks = self.header_splitter.split_text(markdown_text)

            result_chunks = []
            for chunk in header_chunks:
                if len(chunk.page_content) > self.chunk_size:
                    sub_chunks = self.recursive_splitter.split_text(chunk.page_content)
                    for sub_chunk in sub_chunks:
                        result_chunks.append(
                            Document(
                                page_content=sub_chunk,
                                metadata=chunk.metadata.copy()
                            )
                        )
                else:
                    result_chunks.append(chunk)

            return result_chunks
        except Exception as e:
            _logger.error(f"分割文本失败: {e}")
            return []

    def chunks_to_json(self, chunks: list[Document]) -> list[dict]:
        """将 Document 列表转换为 JSON 格式"""
        result = []
        for chunk in chunks:
            result.append({
                "content": chunk.page_content,
                "metadata": {
                    "source": chunk.metadata.get("source", ""),
                    "headers": chunk.metadata.get("headers", [])
                }
            })
        return result

    def save_chunks_json(self, chunks: list[Document], output_path: str) -> bool:
        """保存分块结果为 JSON 文件"""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            json_data = self.chunks_to_json(chunks)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            _logger.info(f"分块结果已保存: {output_path}")
            return True
        except Exception as e:
            _logger.error(f"保存 JSON 失败: {e}")
            return False


class PDFServiceChunkMixin:
    """PDFService 的分块功能 mixin"""

    def __init__(self):
        self._splitter: Optional[MarkdownReportSplitter] = None

    @property
    def splitter(self) -> MarkdownReportSplitter:
        if self._splitter is None:
            self._splitter = MarkdownReportSplitter(concurrency=5)
        return self._splitter

    async def chunk_markdown(
        self,
        report_type: str,
        report_id: int,
    ) -> dict:
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

    async def chunk_batch(
        self,
        report_type: str,
        report_ids: list[int],
    ) -> list[dict]:
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


async def main():
    """使用示例"""
    import json

    splitter = MarkdownReportSplitter()

    test_file = "research_report/output/industry/95861/传媒行业快评报告：11月游戏版号过审184款，西山居《星砂岛》布局生活模拟赛道/vlm/传媒行业快评报告：11月游戏版号过审184款，西山居《星砂岛》布局生活模拟赛道.md"

    if os.path.exists(test_file):
        docs = splitter.split_file(test_file)
        print(f"分块数量: {len(docs)}")
        print("\n前 3 个块的内容和元数据:\n")

        for i, doc in enumerate(docs[:3]):
            print(f"--- 块 {i + 1} ---")
            print(json.dumps({
                "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "metadata": doc.metadata
            }, ensure_ascii=False, indent=2))
            print()
    else:
        print(f"测试文件不存在: {test_file}")


if __name__ == "__main__":
    asyncio.run(main())