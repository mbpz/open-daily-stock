"""Bot package for P6-4: Bidirectional IM interaction."""
from .dispatcher import BotDispatcher, BotRunner, build_dispatcher, get_dispatcher

__all__ = ["BotDispatcher", "BotRunner", "build_dispatcher", "get_dispatcher"]
