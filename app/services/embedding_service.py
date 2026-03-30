import logging
from typing import List, Optional

import httpx

from app.core.config import settings

_logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 服务"""

    def __init__(self):
        self.url = settings.embedding_service.url if settings.embedding_service else "http://localhost:8001"
        self.api_endpoint = settings.embedding_service.api_endpoint if settings.embedding_service else "/api/v1/embeddings"
        self.health_endpoint = settings.embedding_service.health_endpoint if settings.embedding_service else "/health"
        self.model_name = settings.embedding_service.model_name if settings.embedding_service else "BAAI/bge-large-zh-v1.5"
        self.dim = settings.embedding_service.dim if settings.embedding_service else 1024
        self.batch_size = settings.embedding_service.batch_size if settings.embedding_service else 8

    async def health_check(self) -> bool:
        """检查 Embedding 服务健康状态"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.url}{self.health_endpoint}")
                return response.status_code == 200
        except Exception as e:
            _logger.warning(f"Embedding 服务健康检查失败: {e}")
            return False

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """获取文本的 embedding 向量

        Args:
            texts: 文本列表

        Returns:
            embedding 向量列表
        """
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = await self._get_embeddings_batch(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取 embedding"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.url}{self.api_endpoint}",
                    json={
                        "texts": texts,
                        "model": self.model_name
                    }
                )
                response.raise_for_status()
                result = response.json()

                _logger.info(f"Embedding 服务返回: {result.get('model')}, texts: {result.get('total_texts')}")

                embeddings = result.get('embeddings', [])
                if embeddings and isinstance(embeddings, list):
                    # 提取每个 item 中的 "embedding" 字段
                    return [item.get("embedding", []) for item in embeddings]

                _logger.warning(f"Embedding 返回格式异常: {result}")
                return [[0.0] * self.dim for _ in texts]
        except Exception as e:
            _logger.error(f"调用 Embedding 服务失败: {e}")
            return [[0.0] * self.dim for _ in texts]


embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """获取 Embedding 服务实例"""
    return embedding_service