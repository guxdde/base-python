Generic single-database configuration.
### 历史migration缺失，以当前时间点数据库状态作为初始化。


#### 数据库执行,查询最后版本号，然后清空表
```sql
select * from alembic_version;

TRUNCATE TABLE alembic_version;
```
    
    测试环境为8567b8630287

#### 代码路径下操作
 - 代码路径下执行

```shell
alembic revision -m "Base Migration" --head head
```

对生成的versions/下的文件名和内容修改版本号为8567b8630287
 - 代码路径下执行
```shell
alembic upgrade head --sql

# 查看生成的ddl语句是否只有对alembic_version表的操作，确认后执行
alembic upgrade head
alembic revision --autogenerate -m "init_db"
```
 - 将新生成的versions/下的文件中的upgrade方法和downgrade方法中的代码注释掉，添加pass

 - 代码路径下执行
```shell
alembic stamp head 
alembic upgrade head --sql
# 查看生成的ddl语句是否只有对alembic_version表的操作，确认后执行
alembic upgrade head
```

完成当前数据库状态初始化

后续迁移操作
```shell
alembic revision --autogenerate -m "migration description"
alembic upgrade head --sql
# 确认DDL语句，确认无误后执行
alembic upgrade head
```