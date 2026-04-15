from pymilvus import connections, Collection
from app.services.embedding_service import get_embedding_service
import asyncio

async def test_search():
    connections.connect(host='192.168.1.119', port=19530)
    c = Collection('research_report')
    c.load()
    
    # 测试意图识别
    from app.services.retrieval.intent_router import analyze_query_intent
    intent = await analyze_query_intent("游戏行业近况如何")
    print(f"Intent: {intent}")
    
    # 获取查询向量
    embedding = get_embedding_service()
    search_keywords = intent.get("search_keywords", "游戏行业近况如何")
    query_embeddings = await embedding.get_embeddings([search_keywords])
    query_vector = query_embeddings[0]
    
    # 直接搜索，不加过滤
    print("\n=== 直接向量搜索 (无过滤) ===")
    results = c.search(
        data=[query_vector],
        anns_field="summary_embedding",
        param={"metric_type": "L2", "params": {"nprobe": 10}},
        limit=10,
        output_fields=["industry_name", "report_type", "chunk_uid", "content"]
    )
    if results and results[0]:
        for i, r in enumerate(results[0]):
            print(f"  [{i}] type={r.entity.get('report_type')}, industry={r.entity.get('industry_name')}, uid={r.entity.get('chunk_uid')}")
    
    # 搜索 industry 类型
    print("\n=== 向量搜索 (只找 industry) ===")
    results = c.search(
        data=[query_vector],
        anns_field="summary_embedding",
        param={"metric_type": "L2", "params": {"nprobe": 10}},
        limit=10,
        expr='report_type == "industry"',
        output_fields=["industry_name", "report_type", "chunk_uid"]
    )
    if results and results[0]:
        print(f"Found {len(results[0])} industry results")
        for i, r in enumerate(results[0][:5]):
            print(f"  [{i}] industry={r.entity.get('industry_name')}, uid={r.entity.get('chunk_uid')}, dist={r.distance}")
    else:
        print("No industry results found!")
    
    # 测试 BM25 搜索
    print("\n=== BM25 搜索 (industry) ===")
    try:
        results = c.search(
            data=[search_keywords],
            anns_field="sparse_vector",
            param={"metric_type": "BM25", "params": {"bf": 1.0}},
            limit=10,
            expr='report_type == "industry"',
            output_fields=["industry_name", "report_type", "chunk_uid"]
        )
        if results and results[0]:
            print(f"Found {len(results[0])} BM25 industry results")
            for i, r in enumerate(results[0][:5]):
                print(f"  [{i}] industry={r.entity.get('industry_name')}, uid={r.entity.get('chunk_uid')}, dist={r.distance}")
        else:
            print("No BM25 industry results!")
    except Exception as e:
        print(f"BM25 search error: {e}")

asyncio.run(test_search())
