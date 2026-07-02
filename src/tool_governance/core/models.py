from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from enum import Enum

Base = declarative_base()


class ToolStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class ToolPermission(str, Enum):
    PUBLIC = "public"
    DEFAULT = "default"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ToolRegistry(Base):
    __tablename__ = "tool_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500))
    schema_json = Column(JSON)
    permission_level = Column(String(50))
    status = Column(String(20), default=ToolStatus.PENDING)
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True))
    call_count = Column(Integer, default=0)
    last_called_at = Column(DateTime(timezone=True))
    approval_id = Column(String(200))
    approval_platform = Column(String(50))
    approval_count = Column(Integer, default=0)
    approval_required = Column(Integer, default=1)
    quiet_period_until = Column(DateTime(timezone=True))
    approvers = Column(JSON, default=list)


