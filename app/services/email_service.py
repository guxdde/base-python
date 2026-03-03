import time
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from app.core.config import settings
from app.core.redis import get_redis
from app.core.constants import email_code_redis_key
from app.utils import generate_random_code
from app.core.logger import main_logger as logger


# 配置邮件连接
conf = ConnectionConfig(
    MAIL_USERNAME=settings.email.username,
    MAIL_PASSWORD=settings.email.password,
    MAIL_FROM=settings.email.default_sender,
    MAIL_FROM_NAME="AutoThink",  # 设置显示的发件人名称
    MAIL_PORT=settings.email.port,
    MAIL_SERVER=settings.email.server,
    MAIL_STARTTLS=settings.email.port == 587,
    MAIL_SSL_TLS=settings.email.port == 465,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path("templates"),
)


class EmailService:
    """邮件服务类"""
    
    def __init__(self):
        self.fastmail = FastMail(conf)
        self.expired_time = 60 * 30  # 验证码过期时间30分钟
        self.send_interval_time = 55  # 发送验证码间隔时间55秒
    
    async def send_verification_code(self, email: str) -> dict:
        """发送邮箱验证码"""
        redis = await get_redis()
        
        # 检查发送间隔
        key = email_code_redis_key.format(email=email)
        old_code = await redis.get(key)
        print(old_code)
        if old_code is not None:
            try:
                code, send_time = old_code.split('_')
                if time.time() - float(send_time) < self.send_interval_time:
                    return {
                        "success": False,
                        "error": "emain_send_code_interval_time_short",
                        "message": "发送验证码间隔时间太短"
                    }
            except ValueError:
                pass
        
        # 生成新的验证码
        code = generate_random_code()
        
        # 保存验证码到Redis
        await redis.set(key, f'{code}_{time.time()}', expire=self.expired_time)
        
        # 发送邮件
        try:
            # 准备邮件内容
            message = MessageSchema(
                subject="邮箱验证码",
                recipients=[email],
                template_body={"code": code},
                subtype=MessageType.html,
                # 也可以在每个消息中单独设置发件人
                # from_="AutoThink <{}>".format(settings.email.default_sender)
            )
            
            # 发送邮件
            await self.fastmail.send_message(message, template_name="email.html")
            
            return {"success": True, "message": "验证码发送成功"}
        except Exception as e:
            logger.error(f"邮件发送失败: {str(e)}", exc_info=True, extra={'question_openid': 'system'})
            return {"success": False, "error": "server_error", "message": f"邮件发送失败: {str(e)}"}


# 创建全局邮件服务实例
email_service = EmailService() 