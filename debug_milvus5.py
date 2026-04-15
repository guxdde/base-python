from pymilvus import connections, Collection, Function

connections.connect(host='192.168.1.119', port=19530)
c = Collection('research_report')
c.load()

print("=== Collection 信息 ===")
print(f"Name: {c.name}")
print(f"Schema: {c.schema}")

print("\n=== Functions ===")
try:
    # 尝试获取 functions
    print(c.describe())
except Exception as e:
    print(f"Error: {e}")

# 检查字段
print("\n=== Fields ===")
schema = c.schema
for field in schema.fields:
    print(f"  {field.name}: {field.dtype}")

# 尝试直接获取 functions
print("\n=== 获取 Functions ===")
try:
    from pymilvus.orm import types
    # 列出所有 functions
    print("Functions 列表需要通过其他方式获取")
except Exception as e:
    print(f"Error: {e}")
