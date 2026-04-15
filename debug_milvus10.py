from pymilvus import connections, Collection

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

print("=== 验证 BM25 搜索 (重新插入后) ===")

# 测试 sparse_vector (content BM25)
print("\n[1] sparse_vector (content BM25):")
try:
    results = c.search(
        data=["万联证券"],
        anns_field="sparse_vector",
        param={"metric_type": "BM25"},
        limit=5
    )
    print(f'results:{results}')
    if results and results[0]:
        print(f"  找到 {len(results[0])} 条结果")
        for r in results[0][:3]:
            print(f"    {r.entity.get('chunk_uid')}, dist={r.distance:.4f}")
    else:
        print("  无结果")
except Exception as e:
    print(f"  错误: {e}")

# 测试 summary_sparse_vector
print("\n[2] summary_sparse_vector (summary BM25):")
try:
    results = c.search(
        data=["万联证券"],
        anns_field="summary_sparse_vector",
        param={"metric_type": "BM25"},
        limit=5
    )
    if results and results[0]:
        print(f"  找到 {len(results[0])} 条结果")
        for r in results[0][:3]:
            print(f"    {r.entity.get('chunk_uid')}, dist={r.distance:.4f}")
    else:
        print("  无结果")
except Exception as e:
    print(f"  错误: {e}")

# 验证向量检索仍然工作
print("\n[3] summary_embedding (向量):")
try:
    from app.services.embedding_service import get_embedding_service
    import asyncio
    
    async def test():
        emb = get_embedding_service()
        vecs = await emb.get_embeddings(["万联证券"])
        return vecs[0]
    
    query_vec = asyncio.run(test())
    
    results = c.search(
        data=[query_vec],
        anns_field="summary_embedding",
        param={"metric_type": "L2"},
        limit=5
    )
    if results and results[0]:
        print(f"  找到 {len(results[0])} 条结果")
        for r in results[0][:3]:
            print(f"    {r.entity.get('chunk_uid')}, dist={r.distance:.4f}")
    else:
        print("  无结果")
except Exception as e:
    print(f"  错误: {e}")
