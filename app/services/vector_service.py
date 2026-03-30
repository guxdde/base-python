import json
import logging
import os
from typing import Dict, Any, List

from app.core.config import settings
from app.core.database import dbm
from app.core.milvus import get_milvus, milvus_service
from app.models.chunk import ProcessStatusEnum, StockResearchReportRecord, IndustryResearchReportRecord
from sqlalchemy import select
from app.services.embedding_service import get_embedding_service

_logger = logging.getLogger(__name__)


async def insert_chunks_to_milvus(report_type: str, report_id: int) -> Dict[str, Any]:
    """将研报分块数据插入 Milvus 向量数据库

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

        if record.process_status != ProcessStatusEnum.chunked:
            return {"success": False, "message": f"当前状态为 {record.process_status}，需要先完成 chunked 状态"}

        output_path = record.output_path
        if not output_path or not os.path.exists(output_path):
            return {"success": False, "message": "输出路径不存在"}

        chunks_json_path = os.path.join(output_path, "chunks.json")
        if not os.path.exists(chunks_json_path):
            return {"success": False, "message": "chunks.json 文件不存在"}

        try:
            with open(chunks_json_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)

            if not chunks:
                return {"success": False, "message": "分块数据为空"}

            contents = [chunk.get("content", "") for chunk in chunks]
            embedding_service = get_embedding_service()
            embeddings = await embedding_service.get_embeddings(contents)

            for i, chunk in enumerate(chunks):
                chunk["embedding"] = embeddings[i] if i < len(embeddings) else []

            insert_success = await milvus_service.insert_chunks(chunks)

            if not insert_success:
                return {"success": False, "message": "向量数据插入失败"}

            record.process_status = ProcessStatusEnum.chunked_to_db
            await db.commit()

            _logger.info(f"研报 {report_type}:{report_id} 向量入库成功，共 {len(chunks)} 条")

            return {
                "success": True,
                "message": "向量入库成功",
                "chunk_count": len(chunks),
            }

        except Exception as e:
            _logger.error(f"向量入库失败: {e}")
            return {"success": False, "message": f"向量入库失败: {str(e)}"}


async def insert_batch_to_milvus(report_type: str, report_ids: List[int]) -> List[Dict[str, Any]]:
    """批量将研报分块数据插入 Milvus

    Args:
        report_type: 研报类型，"stock" 或 "industry"
        report_ids: 研报 ID 列表

    Returns:
        处理结果列表
    """
    results = []
    for report_id in report_ids:
        result = await insert_chunks_to_milvus(report_type, report_id)
        result["report_id"] = report_id
        results.append(result)

    success_count = sum(1 for r in results if r.get("success", False))
    _logger.info(f"批量向量入库完成: {success_count}/{len(report_ids)} 成功")

    return results