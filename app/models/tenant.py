from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Enum as SQLEnum, ForeignKey
from sqlalchemy.sql import func
from enum import Enum

from app.core.database import Base


class TenantStatusEnum(str, Enum):
    """租户状态枚举"""
    active = "active" # 生效
    stopped = "stopped" # 停用

class Tenant(Base):
    """租户模型"""
    __tablename__ = "tenant"

    id = Column(Integer, primary_key=True)
    create_time = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    company_name = Column(String(40), nullable=True, comment="公司名称")
    description = Column(Text, nullable=False, comment="描述")
    appid = Column(String(40), nullable=False, unique=True, comment="应用id")
    app_secret = Column(String(40), nullable=False, comment="应用密钥")
    status = Column(SQLEnum(TenantStatusEnum), nullable=False, default=TenantStatusEnum.active, comment="状态")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")

class TenantAuthToken(Base):
    """租户认证token模型"""
    __tablename__ = "tenant_auth_token"

    id = Column(Integer, primary_key=True)
    create_time = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False, index=True, comment="租户ID")
    appid = Column(String(40), nullable=True, index=True, comment="应用id")
    refresh_jti = Column(String(40), nullable=False, index=True, comment="刷新令牌")
    expire_time = Column(DateTime(timezone=True), nullable=False, comment="过期时间")


