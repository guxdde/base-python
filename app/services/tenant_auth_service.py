import json
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from jose import jwt
import uuid
import logging

from app.core.redis import get_redis_sync
from app.core.service_cache import BaseServiceCache
from app.models import Tenant, TenantAuthToken
from app.models.tenant import TenantStatusEnum
from app.api.utils import md5_signature
from app.core.custom_auth import ALGORITHM
from app.core.config import settings

_logger = logging.getLogger(__name__)


class TenantAuthService:
    """租户认证服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = get_redis_sync()

    async def get_today_refresh_token_data(self, tenant: Tenant) -> Dict[str, Any]:
        """获取当日已存在的refresh token"""
        now = datetime.now()
        data = {}
        key = f"tenant:refresh:token:{now.strftime('%Y%m%d')}:{tenant.appid}"
        refresh_token_record = await self.redis.get(key)
        if refresh_token_record:
            refresh_token_record = json.loads(refresh_token_record)
            refresh_jti = refresh_token_record.get('refresh_jti')
            refresh_expire = refresh_token_record.get('expire_time')
            refresh_expire = datetime.strptime(refresh_expire, "%Y-%m-%d %H:%M:%S")
            refresh_expires_in = int((refresh_expire - now).total_seconds())
            data.update({
                'refresh_jti': refresh_jti,
                'refresh_expire': refresh_expire,
                'refresh_expires_in': refresh_expires_in,
            })
        else:
            token_filter_expire_time = now + timedelta(
                seconds=(settings.tenant.refresh_token_expire_time - 24 * 60 * 60))
            token_query = (select(TenantAuthToken).where(and_(TenantAuthToken.tenant_id == tenant.id,
                                                              TenantAuthToken.appid == tenant.appid,
                                                              TenantAuthToken.expire_time > token_filter_expire_time))
                           .order_by(TenantAuthToken.expire_time.desc()))
            refresh_token_record = await self.db.execute(token_query)
            refresh_token_record = refresh_token_record.scalars().first()
            if refresh_token_record:
                refresh_jti = refresh_token_record.refresh_jti
                refresh_expire = refresh_token_record.expire_time
                refresh_expires_in = int((refresh_expire - now).total_seconds())
                await self.redis.set(key, json.dumps({'refresh_jti': refresh_jti,
                                                      'expire_time': refresh_expire.strftime("%Y-%m-%d %H:%M:%S")}),
                                     expire=24 * 60 * 60)
                data.update({
                    'refresh_jti': refresh_jti,
                    'refresh_expire': refresh_expire,
                    'refresh_expires_in': refresh_expires_in,
                })
        return data

    async def get_tenant_auth_token(self, appid: str, signature: str) -> Dict[str, Any]:
        """获取租户认证token"""
        if not appid or not signature:
            return {'success': False, 'message': 'appid和signature不能为空'}
        tenant_query = select(Tenant).where(and_(Tenant.appid == appid, Tenant.is_active == True))
        tenant = await self.db.execute(tenant_query)
        tenant = tenant.scalars().first()
        if not tenant:
            return {'success': False, 'message': 'appid不存在'}
        if tenant.status == TenantStatusEnum.stopped:
            return {'success': False, 'message': '租户已停用'}
        if not md5_signature(appid, tenant.app_secret, signature):
            return {'success': False, 'message': '签名错误'}
        # 生成token
        now = datetime.now()
        access_expire = (now + timedelta(seconds=settings.tenant.access_token_expire_time))
        access_token = jwt.encode({'tenant_id': tenant.id, 'appid': tenant.appid, 'type': 'access',
                                   'exp': access_expire}, settings.tenant.token_secret, algorithm=ALGORITHM)
        # 每天减少refresh_token重复生成
        refresh_token_data = await self.get_today_refresh_token_data(tenant)
        if refresh_token_data:
            refresh_jti = refresh_token_data.get('refresh_jti')
            refresh_expire = refresh_token_data.get('refresh_expire')
            refresh_expires_in = int((refresh_expire - now).total_seconds())
        else:
            refresh_jti = str(uuid.uuid4())
            refresh_expire = now + timedelta(seconds=settings.tenant.refresh_token_expire_time)
            token_record = TenantAuthToken(tenant_id=tenant.id, appid=tenant.appid, refresh_jti=refresh_jti,
                                           expire_time=refresh_expire)
            self.db.add(token_record)
            await self.db.commit()
            refresh_expires_in = settings.tenant.refresh_token_expire_time
        # 生成refresh_token
        refresh_token = jwt.encode({"refresh_jti": refresh_jti, "type": "refresh", "exp": refresh_expire},
                                   settings.tenant.token_secret, algorithm=ALGORITHM)
        await self.set_refresh_token_to_redis(refresh_jti, {
            'tenant_id': tenant.id,
            'appid': tenant.appid,
            'refresh_token': refresh_token,
            'refresh_expire': refresh_expire.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return {'success': True, 'message': '成功',
                'data': {'access_token': access_token,
                         'expires_in': settings.tenant.access_token_expire_time,
                         'refresh_token': refresh_token,
                         'refresh_expires_in': refresh_expires_in, }}

    async def set_refresh_token_to_redis(self, refresh_jti: str, refresh_token_data: Dict[str, Any], expire: int=None):
        """将refresh_token保存到redis"""
        try:
            if expire is None:
                expire = settings.tenant.refresh_token_expire_time
            await self.redis.set(f"tenant:refresh:token:{refresh_jti}", json.dumps(refresh_token_data), expire=expire)
        except Exception as e:
            _logger.error('将refresh_token保存到redis失败：%s'%str(e), exc_info=True)
        return True

    async def get_refresh_token_from_redis(self, refresh_jti: str) -> Dict[str, Any]:
        """从redis中获取refresh_token"""
        refresh_token_data = {}
        try:
            refresh_token_data = await self.redis.get(f"tenant:refresh:token:{refresh_jti}")
            if refresh_token_data:
                refresh_token_data = json.loads(refresh_token_data)
            else:
                refresh_token_data = {}
        except Exception as e:
            _logger.error('将refresh_token保存到redis失败：%s' % str(e), exc_info=True)
        return refresh_token_data

    async def refresh_tenant_auth_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新租户认证token"""
        if not refresh_token:
            return {'success': False, 'message': 'refresh_token不能为空'}
        payload = jwt.decode(refresh_token, settings.tenant.token_secret, algorithms=[ALGORITHM])
        if payload.get('type') != 'refresh':
            return {'success': False, 'message': '非法的refresh_token'}
        refresh_jti = payload.get('refresh_jti')
        refresh_token_data = await self.get_refresh_token_from_redis(refresh_jti)
        now = datetime.now()
        if not refresh_token_data:
            query = select(TenantAuthToken).where(and_(TenantAuthToken.refresh_jti == refresh_jti))
            refresh_token_record = await self.db.execute(query)
            refresh_token_record = refresh_token_record.scalars().first()
            if not refresh_token_record:
                return {'success': False, 'message': 'refresh_token已过期'}
            # 查询到记录则重载到redis
            refresh_token_data = {
                'tenant_id': refresh_token_record.tenant_id,
                'appid': refresh_token_record.appid,
                'refresh_token': refresh_token,
                'refresh_expire': refresh_token_record.expire_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            refresh_expires_in = int((refresh_token_record.expire_time - now).total_seconds())

            await self.set_refresh_token_to_redis(refresh_jti, refresh_token_data, refresh_expires_in)
        else:
            refresh_expires_in = int((
                        datetime.strptime(refresh_token_data.get('refresh_expire'), "%Y-%m-%d %H:%M:%S") - now).total_seconds())
        appid = refresh_token_data.get('appid')
        tenant_id = refresh_token_data.get('tenant_id')
        access_expire = (now + timedelta(seconds=settings.tenant.access_token_expire_time)).strftime("%Y-%m-%d %H:%M:%S")
        access_token = jwt.encode({'tenant_id': tenant_id, 'appid': appid, 'type': 'access',
                                   'exp': access_expire}, settings.tenant.token_secret, algorithm=ALGORITHM)
        return {'success': True, 'message': '成功',
                'data': {'access_token': access_token,
                         'expires_in': settings.tenant.access_token_expire_time,
                         'refresh_token': refresh_token,
                         'refresh_expires_in': refresh_expires_in, }}

