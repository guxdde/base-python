
from sqlalchemy import Column, Integer, String, Date, Text
from enum import Enum
from app.core.database import Base
from app.models.abstract import BigIntBaseModel, IntBaseModel

class IndustryResearchReportContent(Base, IntBaseModel):
    __tablename__ = "industry_research_report_content"

    report_id = Column(Integer, nullable=False, index=True, comment="研报ID")
    filename = Column(String(256), nullable=False, comment="文件名")
    file_path = Column(String(500), nullable=False, comment="文件路径")
    trade_date = Column(Date, nullable=False, index=True, comment="发布时间")
    industry_name = Column(String(32), nullable=True, index=True, comment="行业名称")
    org_name = Column(String(128), nullable=True, comment="发布组织")
    org_code = Column(String(32), nullable=True, comment="组织代码")
    info_code = Column(String(32), nullable=True, comment="研报获取关键字段")
    content = Column(Text, nullable=True, comment="内容")

class StockResearchReportContent(Base, IntBaseModel):
    __tablename__ = "stock_research_report_content"

    report_id = Column(Integer, nullable=False, index=True, comment="研报ID")
    filename = Column(String(256), nullable=False, comment="文件名")
    file_path = Column(String(500), nullable=False, comment="文件路径")
    trade_date = Column(Date, nullable=False, index=True, comment="发布时间")
    ts_code = Column(String(16), nullable=False, index=True, comment="股票代码，统一字段")
    symbol = Column(String(16), nullable=True, comment="股票代码，不带后缀")
    company_name = Column(String(32), nullable=True, comment="股票名称")
    org_name = Column(String(128), nullable=True, comment="发布组织")
    org_code = Column(String(32), nullable=True, comment="组织代码")
    info_code = Column(String(32), nullable=True, comment="研报获取关键字段")
    content = Column(Text, nullable=True, comment="内容")


class IndustryResearchReportChunk(Base, BigIntBaseModel):
    __tablename__ = "industry_research_report_chunk"

    report_id = Column(Integer, nullable=True, comment="研报ID")
    filename = Column(String(256), nullable=True, comment="文件名")
    file_path = Column(String(500), nullable=True, comment="文件路径")
    trade_date = Column(Date, nullable=True, comment="发布时间")
    industry_name = Column(String(32), nullable=True, comment="行业名称")
    org_name = Column(String(128), nullable=True, comment="发布组织")
    org_code = Column(String(32), nullable=True, comment="组织代码")
    info_code = Column(String(32), nullable=True, comment="研报获取关键字段")


class StockResearchReportChunk(Base, BigIntBaseModel):
    __tablename__ = "stock_research_report_chunk"

    report_id = Column(Integer, nullable=True, comment="研报ID")
    filename = Column(String(256), nullable=True, comment="文件名")
    file_path = Column(String(500), nullable=True, comment="文件路径")
    trade_date = Column(Date, nullable=True, comment="发布时间")
    ts_code = Column(String(16), nullable=True, comment="股票代码，统一字段")
    symbol = Column(String(16), nullable=True, comment="股票代码，不带后缀")
    company_name = Column(String(32), nullable=True, comment="股票名称")
    org_name = Column(String(128), nullable=True, comment="发布组织")
    org_code = Column(String(32), nullable=True, comment="组织代码")
    info_code = Column(String(32), nullable=True, comment="研报获取关键字段")
