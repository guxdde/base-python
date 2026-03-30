import logging
from typing import Optional, Any

from app.core.pipeline import Pipeline
from app.pipeline.pdf_steps import (
    MineruParsingStep,
    ImageTableAnalyzeStep,
    MarkdownChunkingStep,
    MilvusStorageStep,
)
from app.models.chunk import ProcessStatusEnum, StockResearchReportRecord, IndustryResearchReportRecord
from app.core.database import dbm
from sqlalchemy import select

logger = logging.getLogger(__name__)


def create_pdf_pipeline() -> Pipeline:
    return Pipeline(
        name="pdf_processing",
        steps=[
            MineruParsingStep(),
            ImageTableAnalyzeStep(),
            MarkdownChunkingStep(),
            MilvusStorageStep(),
        ]
    )


class PDFProcessingPipeline:
    def __init__(self):
        self.pipeline = create_pdf_pipeline()

    async def execute(
        self,
        report_type: str,
        report_id: int,
        filename: str,
        trade_date: str,
        db_session: Optional[Any] = None
    ) -> dict:
        record = None

        if db_session:
            record = await self._get_record(db_session, report_type, report_id)
        else:
            async with dbm.session() as db:
                record = await self._get_record(db, report_type, report_id)

        if not record:
            return {
                "pipeline": self.pipeline.name,
                "completed": False,
                "message": "研报记录不存在"
            }

        if record.process_status == ProcessStatusEnum.chunked_to_db:
            return {
                "pipeline": self.pipeline.name,
                "completed": True,
                "message": "研报已处理完成",
                "current_state": record.process_status
            }

        context = {
            "report_type": report_type,
            "report_id": report_id,
            "filename": filename,
            "trade_date": trade_date,
        }

        if db_session:
            context["db"] = db_session
            result = await self.pipeline.execute(record, context)

            if record.process_status == ProcessStatusEnum.chunked_to_db:
                import datetime
                record.process_end = datetime.datetime.now()
                await db_session.commit()

            return result
        else:
            async with dbm.session() as db:
                context["db"] = db
                record = await self._get_record(db, report_type, report_id)
                result = await self.pipeline.execute(record, context)

                if record.process_status == ProcessStatusEnum.chunked_to_db:
                    import datetime
                    record.process_end = datetime.datetime.now()
                    await db.commit()

                return result

    async def _get_record(self, db, report_type: str, report_id: int):
        if report_type == "stock":
            query = select(StockResearchReportRecord).where(
                StockResearchReportRecord.report_id == report_id
            )
        else:
            query = select(IndustryResearchReportRecord).where(
                IndustryResearchReportRecord.report_id == report_id
            )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_record_status(self, report_type: str, report_id: int) -> Optional[dict]:
        async with dbm.session() as db:
            record = await self._get_record(db, report_type, report_id)
            if record:
                return {
                    "report_id": record.report_id,
                    "filename": record.filename,
                    "process_status": record.process_status,
                    "output_path": record.output_path,
                    "process_start": record.process_start.isoformat() if record.process_start else None,
                    "process_end": record.process_end.isoformat() if record.process_end else None,
                }
            return None
