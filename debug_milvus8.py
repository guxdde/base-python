from pymilvus import connections, Collection
from pymilvus.exceptions import MilvusException

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

print("=== 重新插入完整数据测试 ===")

# 获取完整数据
results = c.query(
    expr='chunk_uid == "industry:95861:0"',
    output_fields=['*']
)

if not results:
    print("未找到数据")
    exit()

chunk = results[0]
print(f"原始数据 keys: {chunk.keys()}")

# 准备完整数据重新插入
data = [{
    'chunk_uid': chunk.get('chunk_uid'),
    'report_type': chunk.get('report_type'),
    'report_id': chunk.get('report_id'),
    'chunk_index': chunk.get('chunk_index'),
    'content': chunk.get('content'),
    'summary': chunk.get('summary'),
    'source': chunk.get('source') or '',
    'filename': chunk.get('filename') or '',
    'trade_date': chunk.get('trade_date') or '',
    'ts_code': chunk.get('ts_code') or '',
    'company_name': chunk.get('company_name') or '',
    'industry_name': chunk.get('industry_name') or '',
    'org_name': chunk.get('org_name') or '',
    'headers': chunk.get('headers') or '[]',
    'related_stocks': chunk.get('related_stocks') or '[]',
    'header_path': chunk.get('header_path') or '',
    'embedding': chunk.get('embedding'),
    'summary_embedding': chunk.get('summary_embedding'),
    # 不传 sparse_vector 和 summary_sparse_vector，让 function 自动计算
}]

try:
    # 删除旧数据
    c.delete(expr='chunk_uid == "industry:95861:0"')
    c.flush()
    print("删除成功")
    
    # 插入新数据
    c.insert(data)
    c.flush()
    print("插入成功")
    
    # 查询验证
    results = c.query(
        expr='chunk_uid == "industry:95861:0"',
        output_fields=['sparse_vector', 'summary_sparse_vector', 'content', 'summary']
    )
    
    if results:
        r = results[0]
        sv = r.get('sparse_vector')
        ssv = r.get('summary_sparse_vector')
        print(f"\n重新插入后:")
        print(f"  sparse_vector: {sv is not None}, type={type(sv)}")
        print(f"  summary_sparse_vector: {ssv is not None}, type={type(ssv)}")
        
        if sv:
            print(f"    值: {str(sv)[:100]}")
        if ssv:
            print(f"    值: {str(ssv)[:100]}")
        
        # 验证 BM25 搜索
        print("\n=== 验证 BM25 搜索 ===")
        search_results = c.search(
            data=["游戏"],
            anns_field="sparse_vector",
            param={"metric_type": "BM25"},
            limit=5
        )
        if search_results and search_results[0]:
            print(f"BM25 搜索成功! 找到 {len(search_results[0])} 条结果")
            for i, sr in enumerate(search_results[0][:3]):
                print(f"  [{i}] {sr.entity.get('chunk_uid')}, dist={sr.distance}")
        else:
            print("BM25 搜索无结果")
            
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
