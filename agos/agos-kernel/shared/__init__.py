"""Shared types for AGOS Kernel."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import uuid4


class ResultStatus(Enum):
    """Result status."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    """Base result type.

    Generic over its payload (R-F-007): ``Result[Decision]`` is a valid annotation
    (used by ``decision.DecisionEngine``). Runtime behaviour is unchanged — ``data``
    still accepts any value and ``Result(status=...)`` works as before.
    """
    status: ResultStatus
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_success(self) -> bool:
        return self.status == ResultStatus.SUCCESS
    
    @property
    def is_failure(self) -> bool:
        return self.status == ResultStatus.FAILURE


@dataclass
class Metadata:
    """Metadata for any component."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    version: str = "0.1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)


class SkillInput:
    """Base class for skill inputs."""
    pass


class SkillOutput:
    """Base class for skill outputs."""
    pass
