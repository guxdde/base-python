from pymilvus import connections, Collection
from pymilvus.exceptions import MilvusException

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

# 尝试直接更新 sparse_vector - 使用表达式计算
# 如果 BM25 function 可以重新计算

print("=== 尝试手动触发 BM25 计算 ===")

# 检查 Milvus 版本
import pymilvus
print(f"PyMilvus version: {pymilvus.__version__}")

# 尝试使用 search 获取 BM25 score (不用于检索，只触发计算?)
# 实际上 Milvus 的 function 输出是只读的，不能直接写入

# 方案1: 重新插入数据
print("\n=== 方案: 重新插入数据 ===")

# 获取一个 chunk 的数据
results = c.query(
    expr='chunk_uid == "industry:95861:1"',
    output_fields=['*']
)
if results:
    chunk = results[0]
    print(f"当前数据: {chunk.get('chunk_uid')}")
    print(f"  content: {chunk.get('content')[:50]}...")
    print(f"  summary: {chunk.get('summary')[:50]}...")
    print(f"  sparse_vector: {chunk.get('sparse_vector')}")

    # 尝试删除并重新插入
    print("\n尝试删除并重新插入一条测试数据...")

    try:
        # 删除
        c.delete(expr='chunk_uid == "industry:95861:1"')
        c.flush()
        print("删除成功")

        # 重新插入 (应该触发 BM25 计算)
        data = [{
            'chunk_uid': 'industry:95861:1',
            'report_type': 'industry',
            'report_id': 95861,
            'chunk_index': 0,
            'content': chunk.get('content'),
            'summary': chunk.get('summary'),
            'embedding': chunk.get('embedding'),
            'summary_embedding': chunk.get('summary_embedding'),
            # 不传入 sparse_vector，让 function 自动计算
        }]

        c.insert(data)
        c.flush()
        print("重新插入成功")

        # 查询验证
        results = c.query(
            expr='chunk_uid == "industry:95861:1"',
            output_fields=['sparse_vector', 'summary_sparse_vector', 'content', 'summary']
        )
        if results:
            r = results[0]
            print(f"重新插入后:")
            print(f"  sparse_vector: {r.get('sparse_vector')}")
            print(f"  summary_sparse_vector: {r.get('summary_sparse_vector')}")

    except MilvusException as e:
        print(f"错误: {e}")
