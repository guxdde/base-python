from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, BigInteger, DateTime, Boolean, String, func
from sqlalchemy.sql import expression


class TimestampMixin:
    """时间戳Mixin - 包含创建时间和更新时间"""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )


class IntPrimaryKeyMixin:
    """int自增主键Mixin"""

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")


class BigIntPrimaryKeyMixin:
    """bigint自增主键Mixin"""

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")


class SoftDeleteMixin:
    """逻辑删除Mixin"""

    is_deleted = Column(
        Boolean,
        server_default=expression.false(),
        nullable=False,
        default=False,
        index=True,
        comment="是否删除"
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="删除时间"
    )
    deleted_by = Column(
        BigInteger,
        nullable=True,
        comment="删除人ID"
    )


class UserTrackMixin:
    """用户追踪Mixin - 包含创建人、更新人、所属人"""

    creator_id = Column(
        BigInteger,
        nullable=True,
        index=True,
        comment="创建人ID"
    )
    updater_id = Column(
        BigInteger,
        nullable=True,
        index=True,
        comment="更新人ID"
    )
    owner_id = Column(
        BigInteger,
        nullable=True,
        index=True,
        comment="所属人ID(用于数据归属)"
    )


class IntBaseModel(IntPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """int主键基础模型
    
    包含:
    - int自增主键
    - 创建时间、更新时间
    - 逻辑删除字段
    """
    __abstract__ = True


class BigIntBaseModel(BigIntPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """bigint主键基础模型
    
    包含:
    - bigint自增主键
    - 创建时间、更新时间
    - 逻辑删除字段
    """
    __abstract__ = True


class IntTrackableModel(IntBaseModel, UserTrackMixin):
    """int主键可追踪模型
    
    包含:
    - int自增主键
    - 创建时间、更新时间
    - 逻辑删除字段
    - 用户追踪字段(创建人、更新人、所属人)
    """
    __abstract__ = True


class BigIntTrackableModel(BigIntBaseModel, UserTrackMixin):
    """bigint主键可追踪模型
    
    包含:
    - bigint自增主键
    - 创建时间、更新时间
    - 逻辑删除字段
    - 用户追踪字段(创建人、更新人、所属人)
    """
    __abstract__ = True
