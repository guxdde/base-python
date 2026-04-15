from pymilvus import connections, Collection

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

# 尝试使用 Milvus 的 function 重新计算 BM25
print("=== 尝试使用 BM25 function ===")

# 方法1: 检查是否可以通过 search 来触发 function
# 实际上 BM25 function 应该在 insert 时自动计算

# 检查现有数据的 content 和 summary 是否有值
print("\n=== 检查现有数据 ===")
results = c.query(
    expr='report_type == "industry"',
    output_fields=['chunk_uid', 'content', 'summary'],
    limit=3
)

for r in results:
    content = r.get('content', '')
    summary = r.get('summary', '')
    print(f"\n{r.get('chunk_uid')}:")
    print(f"  content length: {len(content) if content else 0}")
    print(f"  content preview: {content[:100] if content else 'None'}...")
    print(f"  summary length: {len(summary) if summary else 0}")
    print(f"  summary preview: {summary[:100] if summary else 'None'}...")
