import logging
import time
import hashlib
import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.config import settings
from app.core.milvus import get_milvus
from app.services.embedding_service import get_embedding_service
from app.services.rerank_service import get_rerank_service
from app.services.retrieval.intent_router import analyze_query_intent
from app.services.retrieval.time_decay import apply_time_decay
from app.services.retrieval.models import (
    RetrievalRequest, 
    RetrievalResult, 
    RetrievalResponse
)

logger = logging.getLogger(__name__)

SEARCH_MULTIPLIER = 3
CACHE_TTL = 86400
DEFAULT_LAMBDA_MONTHLY = 0.01

WEIGHT_STOCK_EXACT_MATCH = 1.3
WEIGHT_INDUSTRY_RELATED_STOCK = 1.2


class RetrievalService:
    def __init__(self):
        self.milvus = get_milvus()
        self.embedding = get_embedding_service()
        self.rerank = get_rerank_service()
        self._redis = None
        
        self._init_config()
    
    def _init_config(self):
        retrieval_config = settings.retrieval if settings.retrieval else None
        
        if retrieval_config:
            self.weights = retrieval_config.weights
            self.threshold_enabled = retrieval_config.threshold.enabled
            self.vector_threshold = retrieval_config.threshold.vector
            self.bm25_threshold = retrieval_config.threshold.bm25
            self.fusion_threshold = retrieval_config.threshold.fusion
            self.cross_validation_enabled = retrieval_config.threshold.cross_validation
            self.min_vector_ratio = retrieval_config.threshold.min_vector_ratio
            self.min_bm25_ratio = retrieval_config.threshold.min_bm25_ratio
            self.boost_when_both_high = retrieval_config.threshold.boost_when_both_high
            self.log_enabled = retrieval_config.threshold.log_enabled
            self.log_filtered = retrieval_config.threshold.log_filtered
            self.log_level = retrieval_config.threshold.log_level
            self.min_results = retrieval_config.threshold.min_results
        else:
            self.weights = {"summary_embedding": 0.4, "content_bm25": 0.3, "summary_bm25": 0.3}
            self.threshold_enabled = True
            self.vector_threshold = type("obj", (object,), {"method": "relative", "ratio": 0.3})()
            self.bm25_threshold = type("obj", (object,), {"method": "relative", "ratio": 0.3})()
            self.fusion_threshold = type("obj", (object,), {"method": "relative", "ratio": 0.2})()
            self.cross_validation_enabled = True
            self.min_vector_ratio = 0.1
            self.min_bm25_ratio = 0.05
            self.boost_when_both_high = 1.2
            self.log_enabled = True
            self.log_filtered = True
            self.log_level = "info"
            self.min_results = 3
        
        self.WEIGHT_SUMMARY_EMBEDDING = self.weights.get("summary_embedding", 0.4)
        self.WEIGHT_CONTENT_BM25 = self.weights.get("content_bm25", 0.3)
        self.WEIGHT_SUMMARY_BM25 = self.weights.get("summary_bm25", 0.3)
    
    @property
    def redis(self):
        if self._redis is None:
            from app.core.redis import get_redis_sync
            self._redis = get_redis_sync()
        return self._redis
    
    def _generate_cache_key(self, request: RetrievalRequest, intent_data: Dict) -> str:
        cache_str = f"{request.query}:{request.top_k}:{request.report_type or 'all'}"
        cache_str += f":{request.ts_code or ''}:{request.industry_name or ''}"
        cache_str += f":{request.trade_date_from or ''}:{request.trade_date_to or ''}"
        cache_str += f":{intent_data.get('search_keywords', '')}"
        
        hash_key = hashlib.md5(cache_str.encode()).hexdigest()
        return f"retrieval:{hash_key}"
    
    async def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        try:
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    logger.info(f"命中缓存: {cache_key}")
                    if isinstance(cached, bytes):
                        cached = cached.decode('utf-8')
                    return json.loads(cached)
        except Exception as e:
            logger.warning(f"缓存读取失败: {e}")
        return None
    
    async def _save_to_cache(self, cache_key: str, data: Dict, ttl: int = CACHE_TTL):
        try:
            if self.redis:
                await self.redis.setex(cache_key, ttl, json.dumps(data, ensure_ascii=False))
                logger.info(f"缓存已保存: {cache_key}")
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")
    
    def _build_stock_filter_expr(self, request: RetrievalRequest, intent_data: Dict) -> str:
        conditions = []
        conditions.append('report_type == "stock"')
        
        if request.ts_code or (intent_data.get("company_code") and intent_data["company_code"] != "NONE"):
            ts_code = request.ts_code or intent_data.get("company_code", "")
            conditions.append(f'ts_code == "{ts_code}"')
        
        if request.org_name:
            conditions.append(f'org_name == "{request.org_name}"')
        
        if request.trade_date_from:
            conditions.append(f'trade_date >= "{request.trade_date_from}"')
        
        if request.trade_date_to:
            conditions.append(f'trade_date <= "{request.trade_date_to}"')
        
        expr = " and ".join(conditions)
        logger.info(f"Stock 过滤表达式: {expr}")
        return expr
    
    def _build_industry_filter_expr(self, request: RetrievalRequest, intent_data: Dict) -> str:
        conditions = []
        conditions.append('report_type == "industry"')
        
        industry_name = None
        if request.industry_name or (intent_data.get("industry_name") and intent_data["industry_name"] != "NONE"):
            industry_name = request.industry_name or intent_data.get("industry_name", "")
            conditions.append(f'industry_name == "{industry_name}"')
            logger.info(f"识别到行业过滤: {industry_name}")
        
        if request.org_name:
            conditions.append(f'org_name == "{request.org_name}"')
        
        company_code = request.ts_code or intent_data.get("company_code", "")
        if company_code and company_code != "NONE":
            conditions.append(f'related_stocks LIKE "%{company_code}%"')
        
        if request.trade_date_from:
            conditions.append(f'trade_date >= "{request.trade_date_from}"')
        
        if request.trade_date_to:
            conditions.append(f'trade_date <= "{request.trade_date_to}"')
        
        expr = " and ".join(conditions)
        logger.info(f"Industry 过滤表达式: {expr}")
        return expr
    
    def _build_single_type_filter(self, request: RetrievalRequest, intent_data: Dict, report_type: str) -> str:
        if report_type == "stock":
            return self._build_stock_filter_expr(request, intent_data)
        else:
            return self._build_industry_filter_expr(request, intent_data)
    
    async def _search_field(
        self, 
        query_vector: List[float], 
        field: str, 
        top_k: int, 
        filter_expr: str
    ) -> List[Dict[str, Any]]:
        try:
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10}
            }
            
            logger.info(f"执行向量检索: field={field}, top_k={top_k}, filter={filter_expr[:100]}...")
            
            results = self.milvus._collection.search(
                data=[query_vector],
                anns_field=field,
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["*"]
            )
            
            if results and results[0]:
                result_count = len(results[0])
                logger.info(f"向量检索到 {result_count} 条结果 (field={field})")
                return [self._format_search_result(r, field) for r in results[0]]
            logger.info(f"向量检索结果为空 (field={field})")
            return []
            
        except Exception as e:
            logger.error(f"向量检索失败 (field={field}): {e}")
            return []
    
    async def _search_bm25(
        self,
        query_text: str,
        field: str,
        top_k: int,
        filter_expr: str
    ) -> List[Dict[str, Any]]:
        try:
            search_params = {"metric_type": "BM25", "params": {"bf": 1.0}}
            
            logger.info(f"执行 BM25 检索: field={field}, top_k={top_k}, query={query_text[:50]}...")
            
            results = self.milvus._collection.search(
                data=[query_text],
                anns_field=field,
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["*"]
            )
            
            if results and results[0]:
                result_count = len(results[0])
                logger.info(f"BM25 检索到 {result_count} 条结果 (field={field})")
                return [self._format_search_result(r, field) for r in results[0]]
            logger.info(f"BM25 检索结果为空 (field={field})")
            return []
            
        except Exception as e:
            logger.error(f"BM25 检索失败 (field={field}): {e}")
            return []
    
    def _format_search_result(self, result, field: str) -> Dict[str, Any]:
        related_stocks_str = result.entity.get("related_stocks", "[]")
        try:
            related_stocks = json.loads(related_stocks_str) if related_stocks_str else []
        except:
            related_stocks = []
        
        return {
            "chunk_uid": result.entity.get("chunk_uid"),
            "chunk_index": result.entity.get("chunk_index"),
            "content": result.entity.get("content"),
            "summary": result.entity.get("summary"),
            "score": result.distance,
            "score_type": "bm25" if field.startswith("sparse") else "vector",
            "report_id": result.entity.get("report_id"),
            "report_type": result.entity.get("report_type"),
            "filename": result.entity.get("filename"),
            "trade_date": result.entity.get("trade_date"),
            "ts_code": result.entity.get("ts_code"),
            "company_name": result.entity.get("company_name"),
            "industry_name": result.entity.get("industry_name"),
            "org_name": result.entity.get("org_name"),
            "header_path": result.entity.get("header_path"),
            "related_stocks": related_stocks,
        }
    
    def _normalize_scores(self, results: List[Dict]) -> Dict[str, float]:
        if not results:
            return {}
        scores = [abs(r["score"]) for r in results]
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return {r["chunk_uid"]: 1.0 for r in results}
        return {
            r["chunk_uid"]: (abs(r["score"]) - min_s) / (max_s - min_s + 1e-8)
            for r in results
        }
    
    def _calculate_threshold(
        self,
        results: List[Dict],
        threshold_type: str
    ) -> float:
        if not results:
            return 0
        
        scores = [abs(r.get("score", 0)) for r in results]
        max_s = max(scores) if scores else 0
        
        if threshold_type == "vector":
            config = self.vector_threshold
        elif threshold_type == "bm25":
            config = self.bm25_threshold
        else:
            config = self.fusion_threshold
        
        method = config.method if hasattr(config, 'method') else "relative"
        ratio = config.ratio if hasattr(config, 'ratio') else 0.3
        
        if method == "relative" and max_s > 0:
            return max_s * ratio
        elif method == "fixed":
            return ratio
        else:
            percentile = getattr(config, 'percentile', 30)
            sorted_scores = sorted(scores)
            return sorted_scores[len(sorted_scores) * percentile // 100]
    
    def _filter_by_threshold(
        self,
        results: List[Dict],
        threshold_type: str
    ) -> List[Dict]:
        if not results:
            return []
        
        if not self.threshold_enabled:
            return results
        
        threshold = self._calculate_threshold(results, threshold_type)
        
        filtered = [r for r in results if abs(r.get("score", 0)) >= threshold]
        
        if self.log_filtered and self.log_enabled:
            logger.info(f"阈值过滤 [{threshold_type}]: {len(results)} → {len(filtered)} (阈值={threshold:.4f})")
            
            if self.log_level == "debug":
                filtered_ids = set(r["chunk_uid"] for r in filtered)
                for r in results:
                    if r["chunk_uid"] not in filtered_ids:
                        logger.debug(f"  过滤: {r.get('chunk_uid')} (score={r.get('score'):.4f})")
        
        if len(filtered) < self.min_results:
            filtered = results[:self.min_results]
            logger.info(f"保底结果数: {len(filtered)}")
        
        return filtered
    
    def _calculate_relevance_boost(self, result: Dict, intent_data: Dict) -> float:
        boost = 1.0
        company_code = intent_data.get("company_code", "")
        industry_name = intent_data.get("industry_name", "")
        
        if result.get("report_type") == "stock":
            if company_code and company_code != "NONE":
                if result.get("ts_code") == company_code:
                    boost *= WEIGHT_STOCK_EXACT_MATCH
                    logger.info(f"Stock 精确匹配 ts_code: {company_code}")
        
        elif result.get("report_type") == "industry":
            if industry_name and industry_name != "NONE":
                result_industry = result.get("industry_name", "")
                if result_industry == industry_name:
                    boost *= 1.1
                    logger.info(f"Industry 精确匹配 industry_name: {industry_name}")
            
            if company_code and company_code != "NONE":
                related = result.get("related_stocks", [])
                for stock in related:
                    if stock.get("code") == company_code:
                        boost *= WEIGHT_INDUSTRY_RELATED_STOCK
                        logger.info(f"Industry 命中相关股票: {company_code}")
                        break
        
        return boost
    
    def _fusion_results(
        self, 
        summary_results: List[Dict],
        content_bm25_results: List[Dict],
        summary_bm25_results: List[Dict],
        intent_data: Dict,
    ) -> List[Dict[str, Any]]:
        logger.info(f"三路融合: summary_emb={len(summary_results)}, content_bm25={len(content_bm25_results)}, summary_bm25={len(summary_bm25_results)}")
        
        summ_norm = self._normalize_scores(summary_results)
        content_bm25_norm = self._normalize_scores(content_bm25_results)
        summary_bm25_norm = self._normalize_scores(summary_bm25_results)
        
        all_results = {}
        for r in summary_results:
            all_results[r["chunk_uid"]] = {**r, "source": "summary_embedding"}
        for r in content_bm25_results:
            if r["chunk_uid"] in all_results:
                all_results[r["chunk_uid"]]["source"] = "content_bm25"
            else:
                all_results[r["chunk_uid"]] = {**r, "source": "content_bm25"}
        for r in summary_bm25_results:
            if r["chunk_uid"] in all_results:
                all_results[r["chunk_uid"]]["source"] = "summary_bm25"
            else:
                all_results[r["chunk_uid"]] = {**r, "source": "summary_bm25"}
        
        for uid, result in all_results.items():
            score = 0
            if uid in summ_norm:
                score += self.WEIGHT_SUMMARY_EMBEDDING * summ_norm[uid]
            if uid in content_bm25_norm:
                score += self.WEIGHT_CONTENT_BM25 * content_bm25_norm[uid]
            if uid in summary_bm25_norm:
                score += self.WEIGHT_SUMMARY_BM25 * summary_bm25_norm[uid]
            
            boost = self._calculate_relevance_boost(result, intent_data)
            result["score"] = score * boost
        
        fused = sorted(all_results.values(), key=lambda x: x.get("score", 0), reverse=True)
        
        logger.info(f"融合后结果: {len(fused)} 条")
        return fused
    
    def _apply_cross_validation(self, results: List[Dict]) -> List[Dict]:
        if not results or not self.cross_validation_enabled:
            return results
        
        vector_scores = [abs(r.get("score", 0)) for r in results]
        max_vector = max(vector_scores) if vector_scores else 0
        
        for r in results:
            vector_norm = abs(r.get("score", 0)) / max_vector if max_vector > 0 else 0
            
            if vector_norm > 0.5:
                r["score"] = r.get("score", 0) * self.boost_when_both_high
                r["cross_validated"] = True
                logger.info(f"交叉验证通过: {r.get('chunk_uid')} (boost={self.boost_when_both_high})")
        
        return sorted(results, key=lambda x: x.get("score", 0), reverse=True)
    
    async def _search_single_type(
        self,
        query_vector: List[float],
        query_text: str,
        top_k: int,
        request: RetrievalRequest,
        intent_data: Dict,
        report_type: str
    ) -> List[Dict[str, Any]]:
        filter_expr = self._build_single_type_filter(request, intent_data, report_type)
        
        summ_emb_task = self._search_field(query_vector, "summary_embedding", top_k, filter_expr)
        content_bm25_task = self._search_bm25(query_text, "sparse_vector", top_k, filter_expr)
        summary_bm25_task = self._search_bm25(query_text, "summary_sparse_vector", top_k, filter_expr)
        
        summary_results, content_bm25_results, summary_bm25_results = await asyncio.gather(
            summ_emb_task, content_bm25_task, summary_bm25_task
        )
        
        logger.info(f"三路检索完成: report_type={report_type}, summ_emb={len(summary_results)}, content_bm25={len(content_bm25_results)}, summary_bm25={len(summary_bm25_results)}")
        
        summary_results = self._filter_by_threshold(summary_results, "vector")
        content_bm25_results = self._filter_by_threshold(content_bm25_results, "bm25")
        summary_bm25_results = self._filter_by_threshold(summary_bm25_results, "bm25")
        
        fused = self._fusion_results(
            summary_results, content_bm25_results, summary_bm25_results,
            intent_data
        )
        
        fused = self._filter_by_threshold(fused, "fusion")
        
        if self.cross_validation_enabled:
            fused = self._apply_cross_validation(fused)
        
        return fused
    
    async def _search_both_types(
        self,
        query_vector: List[float],
        query_text: str,
        top_k: int,
        request: RetrievalRequest,
        intent_data: Dict
    ) -> List[Dict[str, Any]]:
        retrieval_top_k = max(top_k * SEARCH_MULTIPLIER, top_k + 10)
        
        logger.info(f"双类型三路检索: top_k={retrieval_top_k}, intent={intent_data}")
        
        stock_task = self._search_single_type(
            query_vector, query_text, retrieval_top_k, request, intent_data, "stock"
        )
        industry_task = self._search_single_type(
            query_vector, query_text, retrieval_top_k, request, intent_data, "industry"
        )
        
        stock_results, industry_results = await asyncio.gather(
            stock_task, industry_task
        )
        
        logger.info(f"Stock 检索结果: {len(stock_results)} 条")
        logger.info(f"Industry 检索结果: {len(industry_results)} 条")
        
        for i, r in enumerate(stock_results[:3]):
            logger.info(f"Stock[{i}]: report_type={r.get('report_type')}, industry_name={r.get('industry_name')}, ts_code={r.get('ts_code')}")
        
        for i, r in enumerate(industry_results[:3]):
            logger.info(f"Industry[{i}]: report_type={r.get('report_type')}, industry_name={r.get('industry_name')}, related_stocks={r.get('related_stocks')}")
        
        all_results = stock_results + industry_results
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        logger.info(f"合并后结果: {len(all_results)} 条, 前5条类型分布:")
        for i, r in enumerate(all_results[:5]):
            logger.info(f"  [{i}] score={r.get('score'):.4f}, type={r.get('report_type')}, industry={r.get('industry_name')}")
        
        return all_results
    
    async def search(self, request: RetrievalRequest) -> RetrievalResponse:
        start_time = time.time()
        intent_data = {}
        
        try:
            intent_data = await analyze_query_intent(request.query)
            logger.info(f"========== 检索开始 ==========")
            logger.info(f"用户问题: {request.query}")
            logger.info(f"意图识别结果: {intent_data}")
            logger.info(f"请求参数: top_k={request.top_k}, report_type={request.report_type}, use_rerank={request.use_rerank}")
            
            search_keywords = intent_data.get("search_keywords", request.query)
            if search_keywords == "NONE":
                search_keywords = request.query
            
            query_text = search_keywords
            
            cache_key = self._generate_cache_key(request, intent_data)
            
            if request.use_cache:
                cached_result = await self._get_from_cache(cache_key)
                if cached_result:
                    cached_result["from_cache"] = True
                    cached_result["processing_time"] = time.time() - start_time
                    logger.info(f"命中缓存，返回结果")
                    return RetrievalResponse(**cached_result)
            
            query_embeddings = await self.embedding.get_embeddings([search_keywords])
            query_vector = query_embeddings[0]
            
            retrieval_top_k = max(request.top_k * SEARCH_MULTIPLIER, request.top_k + 10)
            
            if request.report_type:
                fused_results = await self._search_single_type(
                    query_vector, query_text, retrieval_top_k, request, intent_data, request.report_type
                )
            else:
                fused_results = await self._search_both_types(
                    query_vector, query_text, retrieval_top_k, request, intent_data
                )
            
            logger.info(f"融合后结果数: {len(fused_results)}")
            
            decay_results = apply_time_decay(
                fused_results,
                current_timestamp=int(datetime.now().timestamp()),
                lambda_monthly=DEFAULT_LAMBDA_MONTHLY
            )
            
            logger.info(f"时效性衰减后结果数: {len(decay_results)}")
            
            if request.use_rerank and len(decay_results) > 0:
                logger.info(f"开始 Rerank，输入 {len(decay_results)} 条")
                decay_results = await self._rerank_results(
                    request.query, decay_results, request.top_k
                )
            else:
                logger.info(f"跳过 Rerank (use_rerank={request.use_rerank}, results={len(decay_results)})")
            
            final_results = decay_results[:request.top_k]
            
            logger.info(f"最终返回 {len(final_results)} 条结果")
            for i, r in enumerate(final_results):
                logger.info(f"  [{i}] type={r.get('report_type')}, score={r.get('score'):.4f}, rerank={r.get('rerank_score')}, filename={r.get('filename')[:30] if r.get('filename') else ''}")
            
            result_dicts = []
            for r in final_results:
                result_dicts.append({
                    "chunk_uid": r.get("chunk_uid"),
                    "chunk_index": r.get("chunk_index"),
                    "content": r.get("content", ""),
                    "summary": r.get("summary", ""),
                    "score": r.get("score"),
                    "final_score": r.get("final_score"),
                    "rerank_score": r.get("rerank_score"),
                    "report_id": r.get("report_id"),
                    "report_type": r.get("report_type"),
                    "filename": r.get("filename"),
                    "trade_date": r.get("trade_date"),
                    "ts_code": r.get("ts_code"),
                    "company_name": r.get("company_name"),
                    "industry_name": r.get("industry_name"),
                    "org_name": r.get("org_name"),
                    "header_path": r.get("header_path"),
                    "related_stocks": r.get("related_stocks"),
                })
            
            response_data = {
                "results": result_dicts,
                "total": len(result_dicts),
                "query": request.query,
                "intent_data": intent_data,
                "processing_time": time.time() - start_time,
                "from_cache": False
            }
            
            if request.use_cache:
                await self._save_to_cache(cache_key, response_data)
            
            logger.info(f"========== 检索完成 ==========\n")
            return RetrievalResponse(**response_data)
            
        except Exception as e:
            logger.error(f"检索失败: {e}", exc_info=True)
            return RetrievalResponse(
                results=[],
                total=0,
                query=request.query,
                intent_data=intent_data,
                processing_time=time.time() - start_time,
                from_cache=False
            )
    
    async def _rerank_results(
        self, 
        query: str, 
        results: List[Dict], 
        top_k: int
    ) -> List[Dict]:
        try:
            texts = [r.get("content", "") or r.get("summary", "") for r in results[:top_k * 3]]
            
            logger.info(f"Rerank 请求: query={query[:50]}, texts_count={len(texts)}")
            
            rerank_response = await self.rerank.rerank(
                query=query,
                texts=texts,
                top_k=len(texts)
            )
            
            logger.info(f"Rerank 响应 raw: {rerank_response}")
            
            if isinstance(rerank_response, dict) and "results" in rerank_response:
                rerank_map = {r.get("index", i): r.get("score", 0) for i, r in enumerate(rerank_response.get("results", []))}
            else:
                logger.warning(f"Rerank 响应格式异常")
                return results
            
            logger.info(f"Rerank 分数映射: {rerank_map}")
            
            for i, result in enumerate(results):
                if i in rerank_map:
                    result["rerank_score"] = rerank_map[i]
                    result["score"] = rerank_map[i]
            
            results = sorted(results, key=lambda x: x.get("rerank_score", 0) or 0, reverse=True)
            
            logger.info(f"Rerank 完成: {len(results)} 条")
            return results
            
        except Exception as e:
            logger.error(f"Rerank 失败: {e}", exc_info=True)
            return results


retrieval_service = RetrievalService()


def get_retrieval_service() -> RetrievalService:
    return retrieval_service
