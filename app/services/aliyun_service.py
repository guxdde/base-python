from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import datetime
import uuid
import urllib.parse
import hmac
import base64


from app.core.config import settings
from app.core.redis import get_redis_sync


class AliyunService:
    """阿里云服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = get_redis_sync()
        self.url = settings.aliyun.url
        self.app_id = settings.aliyun.app_id
        self.app_secret = settings.aliyun.app_secret
        self.ars_tts_app_key = settings.aliyun.ars_tts_app_key
        self.token_host = settings.aliyun.token_host
        self.ars_format = settings.aliyun.ars_audio_format
        self.tts_format = settings.aliyun.tts_audio_format
        self.tts_voice = settings.aliyun.tts_voice
        self.tts_volume = settings.aliyun.tts_volume

    def percent_encode(self, s: str) -> str:
        """按阿里云规则做一次 URL 编码（RFC3986 子集）"""
        if not isinstance(s, (str, bytes)):
            s = str(s)
        encoded = urllib.parse.quote_plus(s.encode('utf-8'))
        # 把 + 换成 %20，* 换成 %2A，%7E 换回 ~
        encoded = encoded.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
        return encoded

    def gen_signature(self, params):
        """生成签名"""
        keys = sorted(params.keys())
        pairs = []
        for k in keys:
            pairs.append(f'{self.percent_encode(k)}={self.percent_encode(params[k])}')
        # 2. 规范化 query
        canonical_query = '&'.join(pairs)
        # 3. 构造待签名字符串
        string_to_sign = f'GET&{self.percent_encode("/")}&{self.percent_encode(canonical_query)}'
        key = (self.app_secret + '&').encode('utf-8')
        raw = string_to_sign.encode('utf-8')
        signature = base64.b64encode(hmac.new(key, raw, digestmod='sha1').digest()).decode('utf-8')
        return self.percent_encode(signature), canonical_query

    async def get_token(self):
        """获取token"""
        key = f'aliyun:token:{self.app_id}'
        cache_token = await self.redis.get(key)
        if cache_token:
            return cache_token, '成功'
        params = {
                'AccessKeyId': self.app_id,
                'Action': 'CreateToken',
                'Version': '2019-02-28',
                'Format': 'JSON',
                'RegionId': 'cn-shanghai',
                'Timestamp': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'SignatureMethod': 'HMAC-SHA1',
                'SignatureVersion': '1.0',
                'SignatureNonce': str(uuid.uuid4()),
            }
        signature, canonical_query = self.gen_signature(params)
        token_url = f'{self.token_host}/?Signature={signature}&{canonical_query}'
        async with httpx.AsyncClient() as client:
            r = await client.get(token_url)
        if r.status_code != 200:
            return None, '阿里云获取token失败'
        response = r.json()
        token_info = response.get('Token')
        if token_info:
            token = token_info.get('Id')
            expire_time = token_info.get('ExpireTime')
            expire = int((datetime.datetime.fromtimestamp(expire_time) - datetime.datetime.now()).total_seconds())
            if token:
                await self.redis.set(key, token, expire=expire)
                return token, '成功'
        return None, '阿里云获取token失败'
