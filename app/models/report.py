
from sqlalchemy import Column, Integer, String, Date, Index
from enum import Enum
from app.core.database import ExternalBase


class DownloadStatusEnum(str, Enum):
    """下载状态枚举"""
    yes = "Y"
    no = "N"


class IndustryResearchReport(ExternalBase):
    __tablename__ = "industry_research_report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    industry_name = Column(String(32), nullable=True, comment="行业名称")
    trade_date = Column(Date, nullable=True, comment="发布时间")
    title = Column(String(512), nullable=True, comment="研报标题")
    org_name = Column("orgName", String(128), nullable=True, comment="发布组织")
    org_code = Column("orgCode", String(32), nullable=True, comment="组织代码")
    info_code = Column("infoCode", String(32), nullable=True, comment="研报获取关键字段")
    download = Column( String(16), nullable=True, comment="是否下载 (Y 代表下载，N 代表未下载)")

    __table_args__ = (
        Index(
            "industry_naem__title",
            "industry_name",
            "title",
            "trade_date",
            unique=True,
            mysql_using="BTREE"
        ),
        Index(
            "trade_date_industry_name",
            "trade_date",
            "industry_name",
            mysql_using="BTREE"
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
            "comment": "行业研报表"
        }
    )

    def __repr__(self):
        return f"<IndustryResearchReport(id={self.id}, title='{self.title}', industry='{self.industry_name}')>"


class StockResearchReport(ExternalBase):
    __tablename__ = "stock_research_report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(16), nullable=True, comment="股票代码，统一字段")
    symbol = Column(String(16), nullable=True, comment="股票代码，不带后缀")
    trade_date = Column(Date, nullable=True, comment="发布时间")
    company_name = Column(String(32), nullable=True, comment="股票名称")
    title = Column(String(512), nullable=True, comment="研报标题")
    org_name = Column("orgName", String(128), nullable=True, comment="发布组织")
    org_code = Column("orgCode", String(32), nullable=True, comment="组织代码")
    info_code = Column("infoCode", String(32), nullable=True, comment="研报获取关键字段")
    industry_name = Column(String(32), nullable=True, comment="行业名称（股票归属）")
    download = Column(String(16), nullable=True, comment="是否下载（Y 代表下载，N 代表未下载）")

    __table_args__ = (
        Index(
            "ts_code_title",
            "ts_code",
            "title",
            "trade_date",
            unique=True,
            mysql_using="BTREE"
        ),
        Index(
            "ts_code_trade_date",
            "ts_code",
            "trade_date",
            mysql_using="BTREE"
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci"
        }
    )

    def __repr__(self):
        return f"<StockResearchReport(id={self.id}, ts_code='{self.ts_code}', title='{self.title}', company='{self.company_name}')>"