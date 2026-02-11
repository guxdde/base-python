import yaml
from pathlib import Path
from pydantic import BaseModel, field_validator
from typing import Dict, Any, Optional, List



class DatabaseConfig(BaseModel):
    """数据库配置"""

    database_type: str="mysql"
    host: str
    db: str
    port: int
    user: str
    password: str

    @property
    def url(self) -> str:
        """构建数据库连接URL"""
        if self.database_type == 'mysql':
            return f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"
        elif self.database_type == 'postgresql':
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"
        else:
            raise ValueError("Unsupported database type")

class RedisConfig(BaseModel):
    """Redis配置"""

    host: str
    port: int
    password: str

    @property
    def url(self) -> str:
        """构建Redis连接URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/0"
        else:
            return f"redis://{self.host}:{self.port}/0"


class RabbitMQConfig(BaseModel):
    """RabbitMQ配置"""

    host: str
    port: int
    username: str
    password: str
    virtual_host: str = "/"


class EmailConfig(BaseModel):
    """邮件配置"""

    server: str
    port: int
    username: str
    password: str
    default_sender: str


class SmsConfig(BaseModel):
    """短信配置"""

    access_key_id: str
    access_key_secret: str
    sign_name: str  # 这个字段会用作from_参数
    template_code: str
    region: str = "cn-hangzhou"  # 默认使用杭州区域



class AttachmentConfig(BaseModel):
    """附件配置"""

    access_type: str = 'local'  # 附件访问类型
    avatar_dir: str = 'avatar/'    # 头像保存目录
    nginx_url: str = '/files'

class WechatServiceAccountConfig(BaseModel):
    """微信服务号配置"""

    app_id: str
    app_secret: str
    token: str
    encoding_aes_key: str



class TenantConfig(BaseModel):
    """租户配置"""
    token_secret: str
    access_token_expire_time: int
    refresh_token_expire_time: int

class AliyunConfig(BaseModel):
    """阿里云配置"""
    url: str
    app_id: str
    app_secret: str
    ars_tts_app_key: str
    token_host: str
    ars_audio_format: str = "wav"
    tts_audio_format: str = "wav"
    tts_voice: str = "xiaoyun"
    tts_volume: int = 50

class Settings(BaseModel):
    """应用配置"""

    default_db: DatabaseConfig
    redis: RedisConfig
    rabbitmq: RabbitMQConfig
    email: EmailConfig
    sms: Optional[SmsConfig] = None
    attachment: AttachmentConfig
    wechat_service_account: Optional[WechatServiceAccountConfig]
    timescaledb: PostgresqlConfig
    tenant: TenantConfig
    aliyun: AliyunConfig

    # JWT配置（兼容性配置）
    jwt_secret_key: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 15  # 15天
    jwt_refresh_token_expire_days: int = 7

    # CORS跨域配置
    cors_origins: List[str] = ["*"]  # 允许的来源，默认允许所有
    cors_allow_credentials: bool = True  # 允许携带凭证
    cors_allow_methods: List[str] = ["*"]  # 允许的HTTP方法
    cors_allow_headers: List[str] = ["*"]  # 允许的请求头

    @classmethod
    def from_yaml(cls, yaml_path: str = "config.yaml") -> "Settings":
        """从YAML文件加载配置"""
        config_file = Path(yaml_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件 {yaml_path} 不存在")

        with open(config_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        # 解析嵌套配置
        parsed_config = {}

        # 数据库配置
        if "default_db" in config_data:
            parsed_config["default_db"] = DatabaseConfig(**config_data["default_db"])

        # Redis配置
        if "redis" in config_data:
            parsed_config["redis"] = RedisConfig(**config_data["redis"])

        # RabbitMQ配置
        if "rabbitmq" in config_data:
            parsed_config["rabbitmq"] = RabbitMQConfig(**config_data["rabbitmq"])

        # 邮件配置
        if "email" in config_data:
            parsed_config["email"] = EmailConfig(**config_data["email"])

        # 短信配置
        if "sms" in config_data:
            parsed_config["sms"] = SmsConfig(**config_data["sms"])

        # 附件配置
        if "attachment" in config_data:
            parsed_config["attachment"] = AttachmentConfig(**config_data["attachment"])

        if "wechat_service_account" in config_data:
            parsed_config["wechat_service_account"] = WechatServiceAccountConfig(
                **config_data["wechat_service_account"]
            )

        if "timescaledb" in config_data:
            parsed_config["timescaledb"] = DatabaseConfig(**config_data["timescaledb"])

        if "tenant" in config_data:
            parsed_config["tenant"] = TenantConfig(
                **config_data["tenant"]
            )

        if "aliyun" in config_data:
            parsed_config["aliyun"] = AliyunConfig(
                **config_data["aliyun"]
            )

        # 其他简单配置

        # CORS配置
        cors_config = config_data.get("cors", {})
        parsed_config["cors_origins"] = cors_config.get("origins", ["*"])
        parsed_config["cors_allow_credentials"] = cors_config.get(
            "allow_credentials", True
        )
        parsed_config["cors_allow_methods"] = cors_config.get("allow_methods", ["*"])
        parsed_config["cors_allow_headers"] = cors_config.get("allow_headers", ["*"])

        return cls(**parsed_config)


# 加载配置
settings = Settings.from_yaml()

