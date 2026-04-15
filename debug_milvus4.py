from pymilvus import connections, Collection

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

# 测试 BM25 搜索不过滤
print("=== BM25 搜索 (无过滤) ===")
try:
    results = c.search(
        data=["游戏行业"],
        anns_field="sparse_vector",
        param={"metric_type": "BM25", "params": {"bf": 1.0}},
        limit=10,
        output_fields=["report_type", "industry_name", "chunk_uid"]
    )
    if results and results[0]:
        print(f"Found {len(results[0])} BM25 results")
        for i, r in enumerate(results[0][:5]):
            print(f"  [{i}] type={r.entity.get('report_type')}, industry={r.entity.get('industry_name')}, uid={r.entity.get('chunk_uid')}, dist={r.distance}")
    else:
        print("No BM25 results!")
except Exception as e:
    print(f"BM25 search error: {e}")

# 测试 summary_sparse_vector BM25 搜索
print("\n=== BM25 搜索 summary_sparse_vector (无过滤) ===")
try:
    results = c.search(
        data=["游戏行业"],
        anns_field="summary_sparse_vector",
        param={"metric_type": "BM25", "params": {"bf": 1.0}},
        limit=10,
        output_fields=["report_type", "industry_name", "chunk_uid"]
    )
    if results and results[0]:
        print(f"Found {len(results[0])} BM25 results")
        for i, r in enumerate(results[0][:5]):
            print(f"  [{i}] type={r.entity.get('report_type')}, industry={r.entity.get('industry_name')}, uid={r.entity.get('chunk_uid')}, dist={r.distance}")
    else:
        print("No BM25 results!")
except Exception as e:
    print(f"BM25 search error: {e}")
