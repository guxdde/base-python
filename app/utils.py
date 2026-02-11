import hmac
import random
import re
import string
import uuid
from os import urandom
from sqlalchemy import select
import math
import httpx
import json

from app.core.database import get_db_session
from app.core.redis import get_redis
from app.core.constants import sms_code_redis_key
from typing import Dict, Any, List
import hashlib
import time
import datetime
from ast import literal_eval
from collections import namedtuple



def get_uuid():
    uuid_string = str(uuid.uuid1()).replace("-", "")
    return uuid_string


def get_hmac(key=None, s=None, method="SHA1"):
    key = str(uuid.uuid1()).replace("-", "") if key is None else key
    s = urandom(64) if s is None else s

    return hmac.new(key.encode("utf-8"), s, method).hexdigest()


def generate_license_key(length=12):
    # 生成一个长度为 length 的由大写字母和数字组成的随机字符串
    key = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    # 将字符串按照每 4 个字符一组用连字符分隔开
    formatted_key = "-".join([key[i: i + 4] for i in range(0, length, 4)])
    return formatted_key


def has_none(*args, **kwargs):
    if args:
        return None in args
    if kwargs:
        return None in kwargs.values()


def generate_salt(length=8):
    # 生成一个长度为 length 的由大写字母和数字组成的随机字符串
    salt = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return salt


def is_valid_phone(phone_number) -> bool:
    """
    判断是否为合法的中国大陆手机号
    :param phone_number: 待校验的手机号
    :return: 如果是合法的手机号则返回True，否则返回False
    """
    # 先将输入的手机号转换成字符串类型，以兼容用户在前端输入时传入数字类型的情况
    if not phone_number:
        return False
    phone_number = str(phone_number).strip()

    # 首先判断是否为11位数字
    if not re.match(r"^1\d{10}$", phone_number):
        return False

    # 判断前3位号码段是否为合法的手机号码段
    prefix = phone_number[:3]
    if prefix not in [
        "130",
        "131",
        "132",
        "133",
        "134",
        "135",
        "136",
        "137",
        "138",
        "139",
        "141",
        "142",
        "143",
        "145",
        "146",
        "147",
        "148",
        "149",
        "150",
        "151",
        "152",
        "153",
        "155",
        "156",
        "157",
        "158",
        "159",
        "160",
        "161",
        "162",
        "163",
        "165",
        "166",
        "167",
        "168",
        "169",
        "170",
        "171",
        "172",
        "173",
        "174",
        "175",
        "176",
        "177",
        "178",
        "179",
        "180",
        "181",
        "182",
        "183",
        "184",
        "185",
        "186",
        "187",
        "188",
        "189",
        "191",
        "192",
        "193",
        "195",
        "196",
        "197",
        "198",
        "199",
    ]:
        return False

    # 如果以上两个校验都通过，则返回True
    return True


# 为了向后兼容，保留原函数名
is_valid_phone_number = is_valid_phone


def is_valid_email(email: str) -> bool:
    """
    校验邮箱是否合法
    """
    if not email:
        return False
    # 邮箱格式正则表达式
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    # 使用正则表达式匹配邮箱
    if not re.match(pattern, email):
        return False
    return True




def generate_random_code(length=6):
    """生成随机验证码
        length参数表示验证码的位数，默认为6位
    """

    return ''.join([str(random.choice(range(10))) for i in range(length)])


def num_tokens_from_string(string: str, encoding_name: str = 'cl100k_base') -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


# async def verify_sms_code(phone: str, code: str) -> Dict[str, Any]:
#     """
#     验证手机验证码
#
#     Args:
#         phone: 手机号
#         code: 验证码
#
#     Returns:
#         Dict[str, Any]: 包含验证结果的字典
#             - success: 验证是否成功
#             - error: 错误代码（如果验证失败）
#             - message: 错误消息（如果验证失败）
#     """
#     # 验证手机号格式
#     if not is_valid_phone(phone):
#         return {
#             "success": False,
#             "error": "phone_verify_fail",
#             "message": "手机号格式不正确"
#         }
#
#     # 从Redis获取验证码
#     redis = await get_redis()
#     key = sms_code_redis_key.format(phone=phone)
#     stored_code = await redis.get(key)
#
#     # 验证码不存在或已过期
#     if not stored_code:
#         return {
#             "success": False,
#             "error": "phone_verify_fail",
#             "message": "验证码已过期"
#         }
#     stored_code = stored_code.split('_')[0] if '_' in stored_code else stored_code
#
#     # 验证码不匹配
#     if stored_code != code:
#         return {
#             "success": False,
#             "error": "phone_verify_fail",
#             "message": "验证码错误"
#         }
#
#     # 验证成功，删除验证码
#     await redis.delete(key)
#
#     return {
#         "success": True
#     }


def generate_invite_code(user_id: int) -> str:
    """生成用户邀请码"""
    # 使用用户ID和时间戳生成唯一的邀请码
    timestamp = str(int(time.time()))
    raw_string = f"{user_id}_{timestamp}"
    hash_object = hashlib.md5(raw_string.encode())
    hash_hex = hash_object.hexdigest()
    
    # 取前8位作为邀请码
    invite_code = hash_hex[:8].upper()
    return invite_code

_INVERTDICT = {
    1e-1: 1e+1, 1e-2: 1e+2, 1e-3: 1e+3, 1e-4: 1e+4, 1e-5: 1e+5,
    1e-6: 1e+6, 1e-7: 1e+7, 1e-8: 1e+8, 1e-9: 1e+9, 1e-10: 1e+10,
    2e-1: 5e+0, 2e-2: 5e+1, 2e-3: 5e+2, 2e-4: 5e+3, 2e-5: 5e+4,
    2e-6: 5e+5, 2e-7: 5e+6, 2e-8: 5e+7, 2e-9: 5e+8, 2e-10: 5e+9,
    5e-1: 2e+0, 5e-2: 2e+1, 5e-3: 2e+2, 5e-4: 2e+3, 5e-5: 2e+4,
    5e-6: 2e+5, 5e-7: 2e+6, 5e-8: 2e+7, 5e-9: 2e+8, 5e-10: 2e+9,
}

def float_invert(value):
    """Inverts a floating point number with increased accuracy.

    :param float value: value to invert.
    :param bool store: whether store the result in memory for future calls.
    :return: rounded float.
    """
    result = _INVERTDICT.get(value)
    if result is None:
        coefficient, exponent = f'{value:.15e}'.split('e')
        # invert exponent by changing sign, and coefficient by dividing by its square
        result = float(f'{coefficient}e{-int(exponent)}') / float(coefficient)**2
    return result

def _float_check_precision(precision_digits=None, precision_rounding=None):
    if precision_rounding is not None and precision_digits is None:
        assert precision_rounding > 0,\
            f"precision_rounding must be positive, got {precision_rounding}"
    elif precision_digits is not None and precision_rounding is None:
        # TODO: `int`s will also get the `is_integer` method starting from python 3.12
        assert float(precision_digits).is_integer() and precision_digits >= 0,\
            f"precision_digits must be a non-negative integer, got {precision_digits}"
        precision_rounding = 10 ** -precision_digits
    else:
        msg = "exactly one of precision_digits and precision_rounding must be specified"
        raise AssertionError(msg)
    return precision_rounding

def float_round(value, precision_digits=None, precision_rounding=None, rounding_method='HALF-UP'):
    """Return ``value`` rounded to ``precision_digits`` decimal digits,
       minimizing IEEE-754 floating point representation errors, and applying
       the tie-breaking rule selected with ``rounding_method``, by default
       HALF-UP (away from zero).
       Precision must be given by ``precision_digits`` or ``precision_rounding``,
       not both!

       :param float value: the value to round
       :param int precision_digits: number of fractional digits to round to.
       :param float precision_rounding: decimal number representing the minimum
           non-zero value at the desired precision (for example, 0.01 for a
           2-digit precision).
       :param rounding_method: the rounding method used:
           - 'HALF-UP' will round to the closest number with ties going away from zero.
           - 'HALF-DOWN' will round to the closest number with ties going towards zero.
           - 'HALF_EVEN' will round to the closest number with ties going to the closest
              even number.
           - 'UP' will always round away from 0.
           - 'DOWN' will always round towards 0.
       :return: rounded float
    """
    rounding_factor = _float_check_precision(precision_digits=precision_digits,
                                             precision_rounding=precision_rounding)
    if rounding_factor == 0 or value == 0:
        return 0.0

    # NORMALIZE - ROUND - DENORMALIZE
    # In order to easily support rounding to arbitrary 'steps' (e.g. coin values),
    # we normalize the value before rounding it as an integer, and de-normalize
    # after rounding: e.g. float_round(1.3, precision_rounding=.5) == 1.5
    def normalize(val):
        return val / rounding_factor

    def denormalize(val):
        return val * rounding_factor

    # inverting small rounding factors reduces rounding errors
    if rounding_factor < 1:
        rounding_factor = float_invert(rounding_factor)
        normalize, denormalize = denormalize, normalize

    normalized_value = normalize(value)

    # Due to IEEE-754 float/double representation limits, the approximation of the
    # real value may be slightly below the tie limit, resulting in an error of
    # 1 unit in the last place (ulp) after rounding.
    # For example 2.675 == 2.6749999999999998.
    # To correct this, we add a very small epsilon value, scaled to the
    # the order of magnitude of the value, to tip the tie-break in the right
    # direction.
    # Credit: discussion with OpenERP community members on bug 882036
    epsilon_magnitude = math.log2(abs(normalized_value))
    # `2**(epsilon_magnitude - 52)` would be the minimal size, but we increase it to be
    # more tolerant of inaccuracies accumulated after multiple floating point operations
    epsilon = 2**(epsilon_magnitude - 50)

    match rounding_method:
        case 'HALF-UP':  # 0.5 rounds away from 0
            result = round(normalized_value + math.copysign(epsilon, normalized_value))
        case 'HALF-EVEN':  # 0.5 rounds towards closest even number
            integral = math.floor(normalized_value)
            remainder = abs(normalized_value - integral)
            is_half = abs(0.5 - remainder) < epsilon
            # if is_half & integral is odd, add odd bit to make it even
            result = integral + (integral & 1) if is_half else round(normalized_value)
        case 'HALF-DOWN':  # 0.5 rounds towards 0
            result = round(normalized_value - math.copysign(epsilon, normalized_value))
        case 'UP':  # round to number furthest from zero
            result = math.trunc(normalized_value + math.copysign(1 - epsilon, normalized_value))
        case 'DOWN':  # round to number closest to zero
            result = math.trunc(normalized_value + math.copysign(epsilon, normalized_value))
        case _:
            msg = f"unknown rounding method: {rounding_method}"
            raise ValueError(msg)

    return denormalize(result)

def float_is_zero(value, precision_digits=None, precision_rounding=None):
    """Returns true if ``value`` is small enough to be treated as
       zero at the given precision (smaller than the corresponding *epsilon*).
       The precision (``10**-precision_digits`` or ``precision_rounding``)
       is used as the zero *epsilon*: values less than that are considered
       to be zero.
       Precision must be given by ``precision_digits`` or ``precision_rounding``,
       not both!

       Warning: ``float_is_zero(value1-value2)`` is not equivalent to
       ``float_compare(value1,value2) == 0``, as the former will round after
       computing the difference, while the latter will round before, giving
       different results for e.g. 0.006 and 0.002 at 2 digits precision.

       :param int precision_digits: number of fractional digits to round to.
       :param float precision_rounding: decimal number representing the minimum
           non-zero value at the desired precision (for example, 0.01 for a
           2-digit precision).
       :param float value: value to compare with the precision's zero
       :return: True if ``value`` is considered zero
    """
    epsilon = _float_check_precision(precision_digits=precision_digits,
                                     precision_rounding=precision_rounding)
    return value == 0.0 or abs(float_round(value, precision_rounding=epsilon)) < epsilon


# async def get_user_rights(user_id: int) -> dict:
#     """
#     获取用户权益项
#     """
#     if user_id:
#         today = datetime.date.today().strftime("%Y%m%d")
#         redis_cli = await get_redis()
#         right_key = "user:right:control:{date}:{user}".format(date=today, user=user_id)
#         rights = await redis_cli.hgetall(right_key)
#         if rights:
#             return {key: literal_eval(value) for key, value in rights.items()}
#         else:
#             from app.services.user_right_service import UserRightService
#             from app.models.user import User
#             async with get_db_session() as db:
#                 user = await db.get(User, user_id)
#                 service = UserRightService(db, user)
#                 rights = await service.init_user_active_right()
#                 return {key: literal_eval(value) for key, value in rights.items()}
#     return {}


# async def set_user_rights(user_id: int, rights: dict):
#     """
#     设置用户权益项
#     """
#     if user_id:
#         today = datetime.date.today().strftime("%Y%m%d")
#         redis_cli = await get_redis()
#         right_key = "user:right:control:{date}:{user}".format(date=today, user=user_id)
#         data = {key: str(value) for key, value in rights.items()}
#         await redis_cli.hmset(right_key, data)
#         if await redis_cli.ttl(right_key) < 0:
#             today = datetime.datetime.now()
#             expire = int((datetime.datetime.strptime('{} 23:59:59'.format(today.strftime('%Y-%m-%d')),
#                                                      '%Y-%m-%d %H:%M:%S') - today).total_seconds() + 5)
#             await redis_cli.expire(right_key, expire)
#     return True

# async def user_rights_incrby(user_id: int, field: str, amount: int):
#     """用户权益次数更新"""
#     if user_id:
#         today = datetime.date.today().strftime("%Y%m%d")
#         redis_cli = await get_redis()
#         right_key = "user:right:control:{date}:{user}".format(date=today, user=user_id)
#         return await redis_cli.hincrby(right_key, field, amount)
#     return None
#
#
# async def get_user_rights_readonly(user_id: int):
#     """
#     只读获取用户权益项
#     """
#     data = await get_user_rights(user_id)
#     if data is not None:
#         Rights = namedtuple("Rights", data.keys())
#         rights = Rights(*data.values())
#         return rights
#     return None

# async def clear_user_rights(user_ids: List[int]):
#     """清除用户权益缓存"""
#     if user_ids:
#         today = datetime.date.today().strftime("%Y%m%d")
#         redis_cli = await get_redis()
#         right_key = "user:right:control:{date}:*".format(date=today)
#         keys = await redis_cli.keys(right_key)
#         pipe = redis_cli.pipeline()
#         for key in keys:
#             user_id = int(key.split(':')[-1])
#             if user_id in user_ids:
#                 await pipe.delete(key)
#         await pipe.execute()
#         return True
#     return False
#

# async def register_user_gift_rights(user_id: int):
#     """注册用户赠送权益"""
#     from app.models import UserRightRecord
#     from app.models.rights import UserRightStatusEnum, RightTermEnum, RightEdition, RightType
#
#     async with get_db_session() as db:
#         today = datetime.date.today()
#         end_date = today + datetime.timedelta(days=30)
#         result = await db.execute(
#             select(RightEdition.id).where(
#                 RightEdition.code == 'PROFESSIONAL'
#             )
#         )
#         edition_id = result.scalar_one_or_none()
#         type_result = await db.execute(
#             select(RightType.id).where(
#                 RightType.active == True
#             )
#         )
#         for type_id in type_result:
#             record = UserRightRecord(
#                 user_id=user_id,
#                 product_code='COMBO#PROFESSIONAL#MONTH',
#                 order_no=f'REGISTER#GIFT#{user_id}',
#                 status=UserRightStatusEnum.ACTIVE,
#                 edition_id=edition_id,
#                 type_id=type_id[0],
#                 term=RightTermEnum.MONTH,
#                 start_date=today,
#                 end_date=end_date,
#             )
#             db.add(record)
#         await db.commit()
#     return True

# class ModelClient:
#     """模型接口客户端"""
#
#     def __init__(self, host, timeout=30):
#         self.host = host
#         self.timeout = timeout
#         self._cli = None
#
#     def _get_client(self):
#         """延迟初始化客户端或重新创建"""
#         if self._cli is None or self._cli.is_closed:
#             self._cli = httpx.AsyncClient(base_url=self.host, timeout=self.timeout)
#         return self._cli
#
#     async def stream_chat(self, method: str, url: str, payload: dict):
#         client = self._get_client()
#         async with client.stream(method, url, json=payload) as r:
#             async for line in r.aiter_lines():
#                 line = line.strip()
#                 if line.startswith("data:"):
#                     data = line[5:].strip()
#                     if data == "[DONE]":
#                         yield "[DONE]"
#                         return
#                     yield json.loads(data)
#
#     async def post(self, url: str, params: dict):
#         client = self._get_client()
#         try:
#             response = await client.post(url, json=params)
#             if response.is_success:
#                 try:
#                     return True, response.json()
#                 except json.JSONDecodeError:
#                     return True, response.text
#             else:
#                 return False, {
#                     "status_code": response.status_code,
#                     "error": f"HTTP {response.status_code}",
#                     "message": response.text
#                 }
#         except httpx.TimeoutException:
#             return False, {"error": "timeout", "message": "Request timeout"}
#         except httpx.RequestError as e:
#             return False, {"error": "request_error", "message": str(e)}
#         except Exception as e:
#             return False, {"error": "unexpected_error", "message": str(e)}