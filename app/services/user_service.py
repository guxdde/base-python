from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import datetime
import uuid
import urllib.parse
import hmac
import base64


from app.core.config import settings
from app.core.redis import get_redis_sync


class UserService:
    """用户服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = get_redis_sync()