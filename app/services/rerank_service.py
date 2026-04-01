import logging
from typing import List, Optional, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# class RerankResult(BaseModel):
#     index: int = Field(..., description="原始文本的索引")
#     score: float = Field(..., description="相关性分数")
#     text: Optional[str] = Field(None, description="原始文本内容（可选）")
#
#
# class RerankResponse(BaseModel):
#     results: List[RerankResult] = Field(..., description="重排序结果列表，按分数降序排列")
#     model: str = Field(..., description="使用的模型名称")
#     total_texts: int = Field(..., description="输入文本总数")
#     processing_time: float = Field(..., description="处理时间（秒）")
#

class RerankService:
    def __init__(self):
        self.url = settings.rerank_service.url if settings.rerank_service else "http://localhost:8002"
        self.api_endpoint = settings.rerank_service.api_endpoint if settings.rerank_service else "/api/v1/rerank"
        self.health_endpoint = settings.rerank_service.health_endpoint if settings.rerank_service else "/health"
        self.model_name = settings.rerank_service.model_name if settings.rerank_service else "bge-reranker-v2-m3"
        self.max_doc_length = settings.rerank_service.max_doc_length if settings.rerank_service else 2048

    async def health_check(self) -> bool:
        """检查 rerank 服务健康状态"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.url}{self.health_endpoint}")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Rerank 服务健康检查失败: {e}")
            return False

    async def rerank(
        self,
        query: str,
        texts: List[str],
        top_k: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> Dict:
        """对文本进行重排序

        Args:
            query: 查询字符串
            texts: 待排序的文本列表
            top_k: 返回前 k 个结果，默认返回全部
            max_length: 文档最大长度，默认使用配置值

        Returns:
            RerankResponse: 重排序结果
        """
        if not texts:
            raise ValueError("texts 不能为空")

        payload = {
            "query": query,
            "texts": texts,
            "top_k": top_k if top_k is not None else len(texts),
            "max_length": max_length if max_length is not None else self.max_doc_length,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.url}{self.api_endpoint}",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

                return result

        except Exception as e:
            logger.error(f"Rerank 服务调用失败: {e}")
            raise

    async def rerank_with_scores(
        self,
        query: str,
        texts: List[str],
        top_k: Optional[int] = None,
    ) -> List[tuple[int, float, str]]:
        """简化返回：返回 (index, score, text) 元组列表

        Args:
            query: 查询字符串
            texts: 待排序的文本列表
            top_k: 返回前 k 个结果

        Returns:
            List[tuple]: [(index, score, text), ...] 按分数降序
        """
        response = await self.rerank(query, texts, top_k=top_k)
        return [(r.index, r.score, r.text or texts[r.index]) for r in response.results]


rerank_service = RerankService()


def get_rerank_service() -> RerankService:
    return rerank_service
