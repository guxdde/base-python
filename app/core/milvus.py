import logging
from typing import Optional, List, Dict, Any
import json

from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility, Function, FunctionType

from app.core.config import settings

_logger = logging.getLogger(__name__)


class MilvusService:
    """Milvus 向量数据库服务"""

    def __init__(self):
        self.host = settings.milvus.host if settings.milvus else "localhost"
        self.port = settings.milvus.port if settings.milvus else 19530
        self.collection_name = settings.milvus.collection_name if settings.milvus else "research_report"
        self.timeout = settings.milvus.timeout if settings.milvus else 30
        self.batch_size = settings.milvus.collection_batch_size if settings.milvus else 10
        self.flush_interval = settings.milvus.flush_interval if settings.milvus else 100
        self._client = None
        self._collection: Optional[Collection] = None
        self.vector_dim = settings.embedding_service.dim if settings.embedding_service else 1024

    async def connect(self) -> None:
        """连接 Milvus"""
        try:
            connections.connect(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            self._client = True
            _logger.info(f"Milvus 连接成功: {self.host}:{self.port}")
        except Exception as e:
            _logger.error(f"Milvus 连接失败: {e}")
            raise

    async def close(self) -> None:
        """关闭 Milvus 连接"""
        try:
            connections.disconnect("default")
            self._client = None
            self._collection = None
            _logger.info("Milvus 连接已关闭")
        except Exception as e:
            _logger.error(f"关闭 Milvus 连接失败: {e}")

    def get_collection(self) -> Optional[Collection]:
        """获取 Collection 对象"""
        return self._collection

    async def create_collection_if_not_exists(self) -> Collection:
        """创建 Collection（如果不存在）"""
        collection_name = self.collection_name

        _logger.info(f"检查 Collection: {collection_name}")

        # 删除已存在的 Collection（以便使用新 schema 重建）
        if utility.has_collection(collection_name):
            self._collection = Collection(collection_name)
            _logger.info(f"Collection 已存在: {collection_name}, 尝试加载...")
            try:
                self._collection.load()
                _logger.info(f"Collection 加载成功: {collection_name}")
            except Exception as e:
                _logger.warning(f"Collection 加载失败: {e}")
            return self._collection
            # _logger.info(f"删除已存在的 Collection:
            # _logger.info(f"删除已存在的 Collection: {collection_name}")
            # utility.drop_collection(collection_name)

        _logger.info(f"创建新 Collection: {collection_name}")

        # 字段定义 - 使用唯一主键 (chunk_uid) 实现唯一性和覆盖更新
        # chunk_uid = f"{report_type}:{report_id}:{chunk_index}"
        fields = [
            # 唯一主键: report_type:report_id:chunk_index
            FieldSchema(name="chunk_uid", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            # 原始字段（保留用于查询）
            FieldSchema(name="report_type", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="report_id", dtype=DataType.INT32),
            FieldSchema(name="chunk_index", dtype=DataType.INT32),
            # content 字段需要 enable_analyzer=true 才能使用 BM25 函数
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096, enable_analyzer=True),
            FieldSchema(name="summary", dtype=DataType.VARCHAR, max_length=1024, enable_analyzer=True),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="trade_date", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="ts_code", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="company_name", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="industry_name", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="org_name", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="headers", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="related_stocks", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="report_summary", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="header_path", dtype=DataType.VARCHAR, max_length=1024),
            # 稠密向量 (embedding for content)
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),
            # 稀疏向量 (BM25 for content)
            FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
            # 摘要向量 (embedding for summary)
            FieldSchema(name="summary_embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),
            # 摘要稀疏向量 (BM25 for summary)
            FieldSchema(name="summary_sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="Research report chunks with dual BM25 (content + summary), unique primary key (chunk_uid)"
        )

        # Content BM25 函数配置
        bm25_function = Function(
            name="text_bm25_emb",
            input_field_names=["content"],
            output_field_names=["sparse_vector"],
            function_type=FunctionType.BM25,
        )
        schema.add_function(bm25_function)
        _logger.info("Content BM25 函数已添加到 schema")

        # Summary BM25 函数配置
        bm25_function_summary = Function(
            name="summary_bm25_emb",
            input_field_names=["summary"],
            output_field_names=["summary_sparse_vector"],
            function_type=FunctionType.BM25,
        )
        schema.add_function(bm25_function_summary)
        _logger.info("Summary BM25 函数已添加到 schema")

        collection = Collection(name=collection_name, schema=schema)
        _logger.info("Collection 创建成功")

        # 稠密向量索引 (IVF_FLAT)
        index_params_dense = {
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="embedding", index_params=index_params_dense)
        _logger.info("稠密向量索引创建成功 (IVF_FLAT, L2)")

        # 稀疏向量索引 (SPARSE_INVERTED_INDEX) - BM25 函数输出字段必须使用 BM25 度量
        index_params_sparse = {
            "index_type": "SPARSE_INVERTED_INDEX",
            "metric_type": "BM25"
        }
        collection.create_index(field_name="sparse_vector", index_params=index_params_sparse)
        _logger.info("稀疏向量索引创建成功 (SPARSE_INVERTED_INDEX, BM25)")

        # Summary 稠密向量索引 (IVF_FLAT)
        collection.create_index(field_name="summary_embedding", index_params=index_params_dense)
        _logger.info("Summary 稠密向量索引创建成功 (IVF_FLAT, L2)")

        # Summary 稀疏向量索引 (SPARSE_INVERTED_INDEX)
        collection.create_index(field_name="summary_sparse_vector", index_params=index_params_sparse)
        _logger.info("Summary 稀疏向量索引创建成功 (SPARSE_INVERTED_INDEX, BM25)")

        # 字符串字段索引 (TRIE) - 提升查询性能
        string_fields = ["company_name", "ts_code", "industry_name", "org_name"]
        for field in string_fields:
            index_params_str = {"index_type": "TRIE"}
            try:
                collection.create_index(field_name=field, index_params=index_params_str)
                _logger.info(f"字符串索引创建成功: {field} (TRIE)")
            except Exception as e:
                _logger.warning(f"字符串索引创建失败 {field}: {e}")

        # 确保所有索引创建完成后再加载
        _logger.info("等待索引创建完成...")
        import time
        time.sleep(1)

        collection.load()
        _logger.info("Collection 加载成功")

        self._collection = collection
        _logger.info(f"Collection 初始化完成: {collection_name}")
        return self._collection

    def _get_sparse_dim(self) -> int:
        """获取稀疏向量维度 (BM25 返回固定维度)"""
        return 32768

    async def insert_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """批量插入 chunks 到 Milvus

        Args:
            chunks: 分块数据列表，每个元素包含 content, metadata, embedding

        Returns:
            是否插入成功
        """
        _logger.info(f"开始插入数据, chunks 数量: {len(chunks)}")
        _logger.info(f"Milvus client 状态: {self._client}")
        _logger.info(f"Milvus collection 状态: {self._collection}")

        if not self._collection:
            _logger.info("Collection 为 None，尝试创建...")
            await self.create_collection_if_not_exists()

        _logger.info(f"最终 Collection 状态: {self._collection}")

        try:
            # 确保 Collection 已加载
            try:
                self._collection.load()
                _logger.info("Collection 加载成功")
            except Exception as e:
                _logger.warning(f"Collection 加载警告: {e}")

            data = []
            for i, chunk in enumerate(chunks):
                metadata = chunk.get("metadata", {})

                def safe_str(value, max_len=512):
                    if value is None:
                        return ""
                    return str(value)[:max_len]

                report_type_val = safe_str(metadata.get("report_type", ""), 16)
                report_id_val = metadata.get("report_id", 0) or 0
                chunk_index_val = metadata.get("chunk_index", 0)
                chunk_uid = f"{report_type_val}:{report_id_val}:{chunk_index_val}"

                data.append({
                    # 唯一主键: report_type:report_id:chunk_index
                    "chunk_uid": chunk_uid,
                    # 原始字段
                    "report_type": report_type_val,
                    "report_id": report_id_val,
                    "chunk_index": chunk_index_val,
                    # content 字段需要 enable_analyzer=true 才能使用 BM25 函数
                    "content": safe_str(chunk.get("content", ""), 4096),
                    "summary": safe_str(metadata.get("summary", ""), 1024),
                    "source": safe_str(metadata.get("source", ""), 512),
                    "filename": safe_str(metadata.get("filename", ""), 512),
                    "trade_date": safe_str(metadata.get("trade_date", ""), 16),
                    "ts_code": safe_str(metadata.get("ts_code", ""), 16),
                    "company_name": safe_str(metadata.get("company_name", ""), 64),
                    "industry_name": safe_str(metadata.get("industry_name", ""), 32),
                    "org_name": safe_str(metadata.get("org_name", ""), 128),
                    "headers": json.dumps(metadata.get("headers", []) or [], ensure_ascii=False)[:1024],
                    "related_stocks": json.dumps(metadata.get("related_stocks", []) or [], ensure_ascii=False)[:2048],
                    "report_summary": safe_str(metadata.get("report_summary", ""), 2048),
                    "header_path": safe_str(metadata.get("header_path", ""), 1024),
                    "embedding": chunk.get("embedding", []) or [],
                    "summary_embedding": chunk.get("summary_embedding", []) or [],
                    # sparse_vector 和 summary_sparse_vector 会由 BM25 函数自动生成
                })

            _logger.info(f"准备插入数据, data 数量: {len(data)}")

            self._collection.insert(data)
            self._collection.flush()
            _logger.info(f"成功插入 {len(chunks)} 条数据到 Milvus")
            return True

        except Exception as e:
            _logger.error(f"插入 Milvus 失败: {e}")
            import traceback
            _logger.error(f"详细堆栈: {traceback.format_exc()}")
            return False

    def delete_chunks_by_report_id(self, report_id: int, report_type: str = None) -> bool:
        """删除指定研报的所有 chunks

        Args:
            report_id: 研报 ID
            report_type: 研报类型，"stock" 或 "industry"

        Returns:
            是否删除成功
        """
        if not self._collection:
            _logger.warning("Collection 未初始化，跳过删除")
            return False

        try:
            delete_expr = f'report_id == {report_id} and report_type == "{report_type}"'
            _logger.info(f"删除研报 {report_type}:{report_id} 的所有 chunks, 表达式: {delete_expr}")
            self._collection.delete(delete_expr)
            self._collection.flush()
            _logger.info(f"成功删除研报 {report_type}:{report_id} 的所有 chunks")
            return True
        except Exception as e:
            _logger.error(f"删除 chunks 失败: {e}")
            return False

    def delete_chunks_by_report_and_type(self, report_id: int, report_type: str) -> bool:
        """删除指定研报的所有 chunks（按类型）

        Args:
            report_id: 研报 ID
            report_type: 研报类型，"stock" 或 "industry"

        Returns:
            是否删除成功
        """
        return self.delete_chunks_by_report_id(report_id, report_type)

    def query_chunks_by_report_id(self, report_id: int, report_type: str = None) -> List[Dict[str, Any]]:
        """查询指定研报的所有 chunks

        Args:
            report_id: 研报 ID
            report_type: 研报类型，"stock" 或 "industry"

        Returns:
            chunks 列表
        """
        if not self._collection:
            _logger.warning("Collection 未初始化")
            return []

        try:
            query_expr = f'report_id == {report_id} and report_type == "{report_type}"'
            results = self._collection.query(
                expr=query_expr,
                output_fields=["*"]
            )
            _logger.info(f"查询到研报 {report_type}:{report_id} 的 {len(results)} 个 chunks")
            return results
        except Exception as e:
            _logger.error(f"查询 chunks 失败: {e}")
            return []

    def get_chunk_count(self, report_id: int = None, report_type: str = None) -> int:
        """获取 chunks 数量

        Args:
            report_id: 研报 ID，可选
            report_type: 研报类型，可选

        Returns:
            chunks 数量
        """
        if not self._collection:
            return 0

        try:
            if report_id is not None:
                query_expr = f'report_id == {report_id} and report_type == "{report_type}"'
                results = self._collection.query(expr=query_expr, output_fields=["count(*)"])
                return results[0].get("count(*)", 0) if results else 0
            else:
                stats = self._collection.query(expr="", output_fields=["count(*)"])
                return stats[0].get("count(*)", 0) if stats else 0
        except Exception as e:
            _logger.error(f"获取 chunk 数量失败: {e}")
            return 0


milvus_service = MilvusService()


def get_milvus() -> MilvusService:
    """获取 Milvus 服务实例"""
    return milvus_service