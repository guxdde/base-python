from fastapi import APIRouter

from app.api.response import ResponseCode
from app.core.base_endpoint import BaseHTTPEndpoint
from app.services.retrieval import RetrievalService, RetrievalRequest

router = APIRouter()


class RetrievalEndpoint(BaseHTTPEndpoint):
    async def post(self, request):
        body = await request.json()
        
        try:
            req = RetrievalRequest(**body)
        except Exception as e:
            return self.error_response(
                code=ResponseCode.bad_request,
                message=f"请求参数错误: {str(e)}"
            )
        
        try:
            service = RetrievalService()
            result = await service.search(req)
            
            return self.success_response({
                "results": [r.model_dump() for r in result.results],
                "total": result.total,
                "query": result.query,
                "intent_data": result.intent_data,
                "processing_time": result.processing_time,
                "from_cache": result.from_cache
            })
        except Exception as e:
            return self.error_response(
                code=ResponseCode.server_error,
                message=f"检索失败: {str(e)}"
            )


class RetrievalHealthEndpoint(BaseHTTPEndpoint):
    async def get(self, request):
        from app.services.embedding_service import get_embedding_service
        from app.services.rerank_service import get_rerank_service
        from app.core.milvus import get_milvus
        
        health_status = {
            "milvus": False,
            "embedding": False,
            "rerank": False
        }
        
        try:
            milvus = get_milvus()
            if milvus._collection:
                health_status["milvus"] = True
        except:
            pass
        
        try:
            embedding = get_embedding_service()
            health_status["embedding"] = await embedding.health_check()
        except:
            pass
        
        try:
            rerank = get_rerank_service()
            health_status["rerank"] = await rerank.health_check()
        except:
            pass
        
        all_healthy = all(health_status.values())
        
        return self.success_response({
            "status": "healthy" if all_healthy else "degraded",
            "services": health_status
        })

router.add_route("/search", RetrievalEndpoint, methods=["POST"])
router.add_route("/health", RetrievalHealthEndpoint, methods=["GET"])