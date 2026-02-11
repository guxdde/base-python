from sqlalchemy.ext.asyncio import AsyncSession
import datetime
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
from typing import List

from app.core.redis import get_redis_sync


class MarketBaseService:

    def __init__(self, db: AsyncSession, *args, **kwargs):
        self.db = db
        self.redis = get_redis_sync()
        super().__init__(*args, **kwargs)

    async def get_expire_time(self, date: str, days: int):
        """获取过期时间"""
        expired_date = await self.get_stock_trade_date(date, days)
        date = datetime.datetime.strptime(date.replace('-', ''), '%Y%m%d')
        if expired_date:
            expired_date = datetime.datetime.strptime('{}235959'.format(expired_date.replace('-', '')), '%Y%m%d%H%M%S')
        else:
            return days * 24 * 60 * 60
        return int((expired_date - date).total_seconds())

    async def get_stock_trade_date(self, trade_date: str, range_days: int = None):
        """获取股票交易日，今天不是则获取上一个"""
        if isinstance(trade_date, str):
            trade_date = datetime.datetime.strptime(trade_date.replace('-', ''), '%Y%m%d')
        trade_date_str = trade_date.strftime('%Y%m%d')
        result = await self.redis.zrevrangebyscore('stock:market:trade:date', '-inf', int(trade_date_str), 0, 1)
        if not result or not result[0]:
            return None
        trade_date_str = result[0]
        if range_days is None:
            return trade_date_str
        trade_date_index = await self.redis.zrank('stock:market:trade:date', trade_date_str)
        if trade_date_index is None or trade_date_index < 0:
            return None
        target_index = trade_date_index + range_days
        trade_days = await self.redis.zrange('stock:market:trade:date', target_index, target_index)
        if trade_days and trade_days[0]:
            return trade_days[0]
        return None

    async def get_query_trade_date(self, trade_date: str=None, last=0):
        """获取查询日期交易日和实际间隔天数，不传日期为今天往前最近交易日，传日期为日期的上一个交易日"""
        today = datetime.datetime.now()
        if trade_date:
            trade_date = trade_date.replace('-', '')
            pre_trade_date = await self.get_stock_trade_date(trade_date, -1)
            if pre_trade_date:
                last = (today - datetime.datetime.strptime(pre_trade_date, '%Y%m%d')).days + last
                trade_date = pre_trade_date
            else:
                trade_date = datetime.datetime.strptime(trade_date, '%Y%m%d') - datetime.timedelta(days=1)
                last = (today - trade_date).days + last
                trade_date = trade_date.strftime('%Y%m%d')
        else:
            trade_date = await self.get_stock_trade_date(today.strftime('%Y%m%d'))
            last = last
        return trade_date, last

    async def get_prev_trade_days(self, trade_date: str=None, count: int = 1):
        """获取前几个交易日"""
        if isinstance(trade_date, str):
            trade_date_str = trade_date.replace('-', '')
        else:
            trade_date_str = trade_date.strftime('%Y%m%d')
        result = await self.redis.zrevrangebyscore('stock:market:trade:date', '-inf', int(trade_date_str), 0, 1)
        if not result or not result[0]:
            return []
        trade_date_str = result[0]
        trade_date_index = await self.redis.zrank('stock:market:trade:date', trade_date_str)
        if trade_date_index is None or trade_date_index < 0:
            return []
        target_index = trade_date_index - 1 - count
        trade_days = await self.redis.zrange('stock:market:trade:date', target_index, trade_date_index-1)
        if not trade_days:
            return []
        return trade_days

    async def get_next_trade_days(self, trade_date: str = None, count: int = 1) -> List[str]:
        """
        获取后几个交易日

        Args:
            trade_date (str, optional): 基准交易日，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            count (int): 获取的交易日数量，默认为1

        Returns:
            List[str]: 后续的交易日列表，格式为 'YYYYMMDD'
        """
        if isinstance(trade_date, str):
            trade_date_str = trade_date.replace('-', '')
        else:
            trade_date_str = datetime.datetime.now().strftime('%Y%m%d')

        # 获取基准交易日
        result = await self.redis.zrevrangebyscore('stock:market:trade:date', '-inf', int(trade_date_str), 0, 1)
        if not result or not result[0]:
            return []

        trade_date_str = result[0]

        # 获取基准交易日在列表中的索引
        trade_date_index = await self.redis.zrank('stock:market:trade:date', trade_date_str)
        if trade_date_index is None:
            return []

        # 计算目标索引范围（基准日期之后的count个交易日）
        target_start_index = trade_date_index + 1
        target_end_index = trade_date_index + count

        # 获取后续的交易日
        trade_days = await self.redis.zrange('stock:market:trade:date', target_start_index, target_end_index)

        return trade_days if trade_days else []

    async def get_trade_dates_between(self, start_date: str, end_date: str) -> List[str]:
        """
        获取日期区间内的交易日列表

        Args:
            start_date (str): 开始日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            end_date (str): 结束日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'

        Returns:
            List[str]: 日期区间内的交易日列表，格式为 'YYYYMMDD'
        """
        # 格式化日期
        if '-' in start_date:
            start_date = start_date.replace('-', '')
        if '-' in end_date:
            end_date = end_date.replace('-', '')

        # 从Redis中获取区间内的交易日
        trade_dates = await self.redis.zrangebyscore(
            'stock:market:trade:date',
            int(start_date),
            int(end_date)
        )

        return trade_dates

    def check_day_k_query_date_limit(self, trade_date: str):
        """检查日K数据查询日期限制"""
        date_limit_year = 3
        today = datetime.date.today()
        limit_date = today - relativedelta(years=date_limit_year)
        return limit_date.strftime('%Y-%m-%d') <= trade_date

    async def check_minute_k_query_date_limit(self, trade_date: str):
        """检查分时数据查询日期限制"""
        date_limit_day = 7
        today = datetime.date.today()
        today_str = await self.get_stock_trade_date(today.strftime('%Y%m%d'))
        if today_str:
            limit_date = await self.get_stock_trade_date(today_str, -date_limit_day)
            if limit_date:
                return limit_date <= trade_date.replace('-', '')
        limit_date = today - relativedelta(days=date_limit_day + 2)
        return limit_date.strftime('%Y-%m-%d') <= trade_date

    def caculate_vwap_line(self, data: list, vol_key: str = 'vol',  amount_key: str = 'amount', vol_ratio: float = 1, amount_ratio: float = 1):
        """计算股票均价线"""
        if not data:
            return []
        df = pd.DataFrame(data)
        # 累计量、累计额
        df[f'{vol_key}_cum'] = df[vol_key].cumsum()
        df[f'{amount_key}_cum'] = df[amount_key].cumsum()

        # 均价线（VWAP）
        df['vwap_line'] = ((df[f'{amount_key}_cum'] * amount_ratio) / (df[f'{vol_key}_cum'] * vol_ratio)).round(2)
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict(orient='records')

    def caculate_ma_multi(self, data: list, close_key: str = 'close'):
        """计算股票均线"""
        df = pd.DataFrame(data)
        # 计算均线，要求“满窗口”才出值
        df['ma5'] = df[close_key].rolling(window=5, min_periods=5).mean().round(2)
        df['ma10'] = df[close_key].rolling(window=10, min_periods=10).mean().round(2)
        df['ma20'] = df[close_key].rolling(window=20, min_periods=20).mean().round(2)
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict(orient='records')