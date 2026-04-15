from pymilvus import connections, Collection

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

# 检查 sparse_vector 字段是否有数据
print("=== 检查 sparse_vector 字段 ===")
results = c.query(
    expr='report_type == "industry"',
    output_fields=['sparse_vector', 'chunk_uid'],
    limit=5
)
print(f"Found {len(results)} results")
for r in results:
    sv = r.get('sparse_vector')
    print(f"  {r.get('chunk_uid')}: sparse_vector exists={sv is not None}, type={type(sv)}, value={str(sv)[:50] if sv else 'None'}")

# 检查 summary_sparse_vector
print("\n=== 检查 summary_sparse_vector 字段 ===")
results = c.query(
    expr='report_type == "industry"',
    output_fields=['summary_sparse_vector', 'chunk_uid'],
    limit=5
)
for r in results:
    sv = r.get('summary_sparse_vector')
    print(f"  {r.get('chunk_uid')}: summary_sparse_vector exists={sv is not None}, type={type(sv)}, value={str(sv)[:50] if sv else 'None'}")
