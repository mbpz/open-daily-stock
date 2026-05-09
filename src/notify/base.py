"""通知渠道基类"""
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class ChannelPriority(Enum):
    """渠道优先级"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class ChannelResult:
    """渠道发送结果"""
    success: bool
    channel: str
    message: Optional[str] = None
    error: Optional[str] = None


class BaseChannel(ABC):
    """通知渠道抽象基类"""

    def __init__(self, config: dict):
        self.config = config
        self.name = self.__class__.__name__

    @abstractmethod
    def send(self, content: str, **kwargs) -> ChannelResult:
        pass

    def is_configured(self) -> bool:
        return True

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.MEDIUM