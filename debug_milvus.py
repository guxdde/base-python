from pymilvus import connections, Collection

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

# 查询 industry 研报
r = c.query(expr='industry_name != ""', output_fields=['industry_name', 'report_type', 'chunk_uid'], limit=20)
print('Industry reports found:', len(r))
for x in r[:10]:
    print(f"  {x.get('chunk_uid')}: industry={x.get('industry_name')}, type={x.get('report_type')}")

# 统计
all_data = c.query(expr='industry_name == ""', output_fields=['industry_name'], limit=1)
print(f'\nStock reports (empty industry_name) sample exists: {len(all_data) > 0}')
