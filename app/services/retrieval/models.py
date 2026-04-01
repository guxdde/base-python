from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class RetrievalRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    top_k: int = Field(6, description="返回结果数量")
    report_type: Optional[str] = Field(None, description="研报类型过滤: stock/industry")
    ts_code: Optional[str] = Field(None, description="股票代码过滤")
    industry_name: Optional[str] = Field(None, description="行业名称过滤")
    org_name: Optional[str] = Field(None, description="发布机构过滤")
    trade_date_from: Optional[str] = Field(None, description="起始日期 YYYY-MM-DD")
    trade_date_to: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    use_rerank: bool = Field(True, description="是否使用 rerank")
    use_cache: bool = Field(True, description="是否使用缓存")


class RetrievalResult(BaseModel):
    chunk_uid: str
    chunk_index: int
    content: str = Field(..., description="Chunk 原始内容")
    summary: str = Field(..., description="上下文增强摘要")
    score: float = Field(..., description="向量检索分数")
    final_score: Optional[float] = Field(None, description="时效性衰减后的分数")
    rerank_score: Optional[float] = Field(None, description="Rerank 分数")
    report_id: int
    report_type: str
    filename: str
    trade_date: str
    ts_code: Optional[str] = None
    company_name: Optional[str] = None
    industry_name: Optional[str] = None
    org_name: str
    header_path: str
    related_stocks: Optional[List[Dict[str, str]]] = Field(None, description="行业研报涉及的公司股票")


class RetrievalResponse(BaseModel):
    results: List[RetrievalResult]
    total: int
    query: str
    intent_data: dict = Field(default_factory=dict, description="意图识别结果")
    processing_time: float = Field(..., description="处理时间（秒）")
    from_cache: bool = Field(False, description="是否命中缓存")
