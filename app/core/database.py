from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker

from .config import settings
from .config import DatabaseConfig


class Base(AsyncAttrs, DeclarativeBase):
    """数据库模型基类"""
    pass

class ExternalBase(AsyncAttrs, DeclarativeBase):
    """外部数据库模型基类"""
    pass

class TimescaledbBase(AsyncAttrs, DeclarativeBase):
    """时序数据库模型基类"""
    pass

class DatabaseManager:
    def __init__(self):
        self._configs: Dict[str, DatabaseConfig] = {}
        self._engines: Dict[str, AsyncEngine] = {}
        self._factories: Dict[str, sessionmaker] = {}
        self._initialized = False

    async def register(self, cfg: "DatabaseConfig") -> None:
        # 仅在需要时创建引擎与工厂
        if cfg.db in self._engines:
            return
        eng = create_async_engine(cfg.url,
                                  pool_recycle=cfg.pool_recycle,
                                  pool_size=cfg.pool_size,
                                  max_overflow=cfg.max_overflow,
                                  pool_timeout=cfg.pool_timeout,
                                  future=True,
                                  pool_pre_ping=True,
                                  echo=False)
        self._configs[cfg.db] = cfg
        self._engines[cfg.db] = eng
        self._factories[cfg.db] = sessionmaker(eng, class_=AsyncSession, expire_on_commit=cfg.expire_on_commit)
        self._initialized = True

    async def init_databases(self) -> None:
        # 如果已初始化，则直接返回；否则由外部调用逐个注册后初始化
        if self._initialized:
            return
        # 这里可以按需自动启动已注册的 cfg（如果有默认配置来源）
        # 例：await self.register(DBConfig(...))
        self._initialized = True

    async def shutdown(self) -> None:
        # 统一清理资源
        for eng in self._engines.values():
            await eng.dispose()
        self._engines.clear()
        self._factories.clear()
        self._initialized = False

    async def get_session(self, name: str = "default") -> AsyncSession:
        if not self._initialized:
            await self.init_databases()
        factory = self._factories.get(name)
        if factory is None:
            factory = self._factories.get("default")
        # 这里直接返回一个 AsyncSession 对象，调用方再决定上下文管理
        return factory()

    @asynccontextmanager
    async def session(self, name: str = "default"):
        """
        使用示例:
        async with dbm.session("default") as session:
            ...
        """
        sess = await self.get_session(name)
        async with sess as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


dbm = DatabaseManager()

async def init_databases():
    """初始化数据库"""
    await dbm.register(settings.default_db)
    await dbm.init_databases()

async def close_databases():
    """关闭数据库"""
    await dbm.shutdown()



# # 创建多个数据库引擎和会话工厂
# default_engine = None
# news_engine = None
# market_engine = None
# ai_interpretation_engine = None  # 新增AI解读数据库引擎
# realtime_market_engine = None  # 新增AI解读数据库引擎
# hot_spot_engine = None
# timescaledb_engine = None
# stock_news_engine = None
#
# # 会话工厂
# default_session_factory = None
# news_session_factory = None
# market_session_factory = None
# ai_interpretation_session_factory = None  # 新增AI解读数据库会话工厂
# realtime_market_session_factory = None  # 新增AI解读数据库会话工厂
# hot_spot_session_factory = None
# timescaledb_session_factory = None
# stock_news_session_factory = None
#
# async def init_databases():
#     """初始化多个数据库连接"""
#     global default_engine, news_engine, market_engine, ai_interpretation_engine, realtime_market_engine, \
#         hot_spot_engine, timescaledb_engine, stock_news_engine
#     global default_session_factory, news_session_factory, market_session_factory, ai_interpretation_session_factory, \
#         realtime_market_session_factory, hot_spot_session_factory, timescaledb_session_factory, \
#         stock_news_session_factory
#
#     # 默认数据库
#     default_url = f"mysql+aiomysql://{settings.default_db.user}:{settings.default_db.password}@{settings.default_db.host}:{settings.default_db.port}/{settings.default_db.db}"
#     default_engine = create_async_engine(
#         default_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,        # 基础连接池：200个
#         max_overflow=40,     # 溢出连接：800个，总共1000个连接
#         pool_timeout=30,      # 获取连接超时时间
#         future=True
#     )
#     default_session_factory = async_sessionmaker(
#         default_engine,
#         class_=AsyncSession,
#         expire_on_commit=False
#     )
#
#     # 新闻数据库
#     news_url = f"mysql+aiomysql://{settings.news_db.user}:{settings.news_db.password}@{settings.news_db.host}:{settings.news_db.port}/{settings.news_db.db}"
#     news_engine = create_async_engine(
#         news_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,        # 基础连接池：100个
#         max_overflow=40,     # 溢出连接：400个，总共500个连接
#         pool_timeout=30,
#         future=True
#     )
#     news_session_factory = async_sessionmaker(
#         news_engine,
#         class_=AsyncSession,
#         expire_on_commit=True
#     )
#
#     # AI解读数据库
#     ai_interpretation_url = f"mysql+aiomysql://{settings.ai_interpretation_db.user}:{settings.ai_interpretation_db.password}@{settings.ai_interpretation_db.host}:{settings.ai_interpretation_db.port}/{settings.ai_interpretation_db.db}"
#     ai_interpretation_engine = create_async_engine(
#         ai_interpretation_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,        # 基础连接池：50个
#         max_overflow=40,     # 溢出连接：200个，总共250个连接
#         pool_timeout=30,
#         future=True
#     )
#     ai_interpretation_session_factory = async_sessionmaker(
#         ai_interpretation_engine,
#         class_=AsyncSession,
#         expire_on_commit=False
#     )
#
#     # 市场数据库
#     market_url = f"mysql+aiomysql://{settings.market.user}:{settings.market.password}@{settings.market.host}:{settings.market.port}/{settings.market.db}"
#     market_engine = create_async_engine(
#         market_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,        # 基础连接池：100个
#         max_overflow=40,     # 溢出连接：400个，总共500个连接
#         pool_timeout=30,
#         future=True
#     )
#     market_session_factory = async_sessionmaker(
#         market_engine,
#         class_=AsyncSession,
#         expire_on_commit=False
#     )
#
#     # 实时市场数据库
#     realtime_market_url = f"mysql+aiomysql://{settings.realtime_market.user}:{settings.realtime_market.password}@{settings.realtime_market.host}:{settings.realtime_market.port}/{settings.realtime_market.db}"
#     realtime_market_engine = create_async_engine(
#         realtime_market_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,        # 基础连接池：100个
#         max_overflow=40,     # 溢出连接：400个，总共500个连接
#         pool_timeout=30,
#         future=True
#     )
#     realtime_market_session_factory = async_sessionmaker(
#         realtime_market_engine,
#         class_=AsyncSession,
#         expire_on_commit=False
#     )
#
#     # 热点预测数据库
#     hot_spot_url = f"mysql+aiomysql://{settings.hot_spot.user}:{settings.hot_spot.password}@{settings.hot_spot.host}:{settings.hot_spot.port}/{settings.hot_spot.db}"
#     hot_spot_engine = create_async_engine(
#         hot_spot_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,        # 基础连接池：100个
#         max_overflow=40,     # 溢出连接：400个，总共500个连接
#         pool_timeout=30,
#         future=True
#     )
#     hot_spot_session_factory = async_sessionmaker(
#         hot_spot_engine,
#         class_=AsyncSession,
#         expire_on_commit=False
#     )
#
#     timescaledb_url = settings.timescaledb.url
#     timescaledb_engine = create_async_engine(
#         timescaledb_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,        # 基础连接池：100个
#         max_overflow=40,     # 溢出连接：400个，总共500个连接
#         pool_timeout=30,
#         future=True
#     )
#     timescaledb_session_factory = async_sessionmaker(
#         timescaledb_engine,
#         class_=AsyncSession,
#         expire_on_commit=False
#     )
#
#     stock_news_url = settings.stock_news.url
#     stock_news_engine = create_async_engine(
#         stock_news_url,
#         echo=False,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=20,  # 基础连接池：100个
#         max_overflow=40,  # 溢出连接：400个，总共500个连接
#         pool_timeout=30,
#         future=True
#     )
#     stock_news_session_factory = async_sessionmaker(
#         stock_news_engine,
#         class_=AsyncSession,
#         expire_on_commit=False
#     )
#
# async def get_db():
#     """获取默认数据库会话 - 依赖注入方式"""
#     if default_session_factory is None:
#         await init_databases()
#
#     async with default_session_factory() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()
#
#
# async def get_news_db():
#     """获取新闻数据库会话 - 依赖注入方式"""
#     if news_session_factory is None:
#         await init_databases()
#
#     async with news_session_factory() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()
#
#
# async def get_ai_interpretation_db():
#     """获取AI解读数据库会话 - 依赖注入方式"""
#     if ai_interpretation_session_factory is None:
#         await init_databases()
#
#     async with ai_interpretation_session_factory() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()
#
#
# async def get_market_db():
#     """获取市场数据库会话 - 依赖注入方式"""
#     if market_session_factory is None:
#         await init_databases()
#
#     async with market_session_factory() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()
#
# async def get_realtime_market_db():
#     """获取实时市场数据库会话 - 依赖注入方式"""
#     if realtime_market_session_factory is None:
#         await init_databases()
#
#     async with realtime_market_session_factory() as session:
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()
#
#
# # chains独立使用的数据库会话管理器 - 优化版本
# @asynccontextmanager
# async def get_db_session(db_type: str = "default"):
#     """为chains提供的独立数据库会话管理器 - 优化异步版本
#
#     Args:
#         db_type: 数据库类型，可选值: "default", "news", "market", "ai_interpretation"
#
#     Usage:
#         async with get_db_session() as db:
#             # 使用数据库会话
#             result = await db.execute(select(User).where(User.id == 1))
#             user = result.scalar_one_or_none()
#     """
#     if default_session_factory is None:
#         await init_databases()
#
#     # 根据类型选择对应的会话工厂
#     if db_type == "news":
#         session_factory = news_session_factory
#     elif db_type == "market":
#         session_factory = market_session_factory
#     elif db_type == "ai_interpretation":
#         session_factory = ai_interpretation_session_factory
#     elif db_type == "realtime_market":
#         session_factory = realtime_market_session_factory
#     elif db_type == "hot_spot_prediction":
#         session_factory = hot_spot_session_factory
#     elif db_type == "timescaledb":
#         session_factory = timescaledb_session_factory
#     elif db_type == "stock_news":
#         session_factory = stock_news_session_factory
#     else:
#         session_factory = default_session_factory
#
#     async with session_factory() as session:
#         try:
#             yield session
#             await session.commit()  # 自动提交成功的事务
#         except Exception:
#             await session.rollback()  # 发生异常时回滚
#             raise
#         finally:
#             await session.close()
#
#
#
#
# async def init_db() -> None:
#     """初始化数据库表 (仅对默认数据库)"""
#     if default_engine is None:
#         await init_databases()
#
#     async with default_engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#
#
# async def close_db() -> None:
#     """关闭所有数据库连接"""
#     global default_engine, news_engine, market_engine, ai_interpretation_engine, realtime_market_engine, \
#         hot_spot_engine, timescaledb_engine, stock_news_engine
#     global default_session_factory, news_session_factory, market_session_factory, ai_interpretation_session_factory, \
#         realtime_market_session_factory, hot_spot_session_factory, timescaledb_session_factory, \
#         stock_news_session_factory
#
#     if default_engine:
#         await default_engine.dispose()
#         default_engine = None
#         default_session_factory = None
#
#     if news_engine:
#         await news_engine.dispose()
#         news_engine = None
#         news_session_factory = None
#
#     if market_engine:
#         await market_engine.dispose()
#         market_engine = None
#         market_session_factory = None
#
#     if ai_interpretation_engine:
#         await ai_interpretation_engine.dispose()
#         ai_interpretation_engine = None
#         ai_interpretation_session_factory = None
#
#     if realtime_market_engine:
#         await realtime_market_engine.dispose()
#         realtime_market_engine = None
#         realtime_market_session_factory = None
#
#     if hot_spot_engine:
#         await hot_spot_engine.dispose()
#         hot_spot_engine = None
#         hot_spot_session_factory = None
#
#     if timescaledb_engine:
#         await timescaledb_engine.dispose()
#         timescaledb_engine = None
#         timescaledb_session_factory = None
#
#     if stock_news_engine:
#         await stock_news_engine.dispose()
#         stock_news_engine = None
#         stock_news_session_factory = None
#
# # 获取直接的数据库会话 - 用于特殊场景
# async def get_raw_session(db_type: str = "default") -> AsyncSession:
#     """获取原始数据库会话对象 - 需要手动管理
#
#     注意：使用后需要手动关闭会话
#     """
#     if default_session_factory is None:
#         await init_databases()
#
#     if db_type == "news":
#         session_factory = news_session_factory
#     elif db_type == "market":
#         session_factory = market_session_factory
#     elif db_type == "ai_interpretation":
#         session_factory = ai_interpretation_session_factory
#     elif db_type == "realtime_market":
#         session_factory = realtime_market_session_factory
#     else:
#         session_factory = default_session_factory
#
#     return session_factory()
#
#
# # 数据库健康检查
# async def check_db_health() -> dict:
#     """检查所有数据库连接健康状况"""
#     health_status = {
#         'default': False,
#         'news': False,
#         'market': False,
#         'ai_interpretation': False
#     }
#
#     try:
#         # 检查默认数据库
#         async with get_db_session("default") as db:
#             await db.execute("SELECT 1")
#             health_status['default'] = True
#     except Exception as e:
#         print(f"Default database health check failed: {e}")
#
#     try:
#         # 检查新闻数据库
#         async with get_db_session("news") as db:
#             await db.execute("SELECT 1")
#             health_status['news'] = True
#     except Exception as e:
#         print(f"News database health check failed: {e}")
#
#     try:
#         # 检查市场数据库
#         async with get_db_session("market") as db:
#             await db.execute("SELECT 1")
#             health_status['market'] = True
#     except Exception as e:
#         print(f"Market database health check failed: {e}")
#
#     try:
#         # 检查AI解读数据库
#         async with get_db_session("ai_interpretation") as db:
#             await db.execute("SELECT 1")
#             health_status['ai_interpretation'] = True
#     except Exception as e:
#         print(f"AI interpretation database health check failed: {e}")
#
#     try:
#         # 检查实时市场数据库
#         async with get_db_session("realtime_market") as db:
#             await db.execute("SELECT 1")
#             health_status['realtime_market'] = True
#     except Exception as e:
#         print(f"Realtime market database health check failed: {e}")
#
#     return health_status