from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Index, Enum as SQLEnum
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.abstract import IntBaseModel


class UserStatusEnum(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"


class User(Base, IntBaseModel):
    """用户模型
    
    基于 BigIntBaseModel，包含:
    - bigint自增主键
    - 创建时间、更新时间
    - 逻辑删除字段
    
    业务字段:
    - username: 用户名(唯一)
    - email: 邮箱(唯一,可空)
    - phone: 手机号(唯一,可空)
    - nickname: 昵称
    - avatar_id: 头像ID
    - status: 用户状态
    - last_login_at: 最后登录时间
    - password_hash: 密码哈希
    """

    __tablename__ = "user"

    __table_args__ = (
        Index("idx_user_username", "username", unique=True),
        Index("idx_user_email", "email", unique=True),
        Index("idx_user_phone", "phone", unique=True),
        Index("idx_user_status", "status"),
    )

    username = Column(
        String(50),
        nullable=False,
        unique=True,
        comment="用户名"
    )
    email = Column(
        String(255),
        nullable=True,
        unique=True,
        comment="邮箱"
    )
    phone = Column(
        String(20),
        nullable=True,
        unique=True,
        comment="手机号"
    )
    nickname = Column(
        String(50),
        nullable=True,
        comment="昵称"
    )
    avatar_id = Column(
        BigInteger,
        nullable=True,
        comment="头像ID"
    )
    status = Column(
        SQLEnum(UserStatusEnum),
        nullable=False,
        default=UserStatusEnum.ACTIVE,
        comment="用户状态"
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间"
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="密码哈希"
    )
    salt = Column(
        String(100),
        nullable=False,
        comment="密码盐"
    )
