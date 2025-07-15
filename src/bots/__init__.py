"""
机器人模块 - 支持多平台机器人集成
"""

from .base_bot import BaseBot
from .telegram_bot import TelegramBot
from .synology_chat_bot import SynologyChatBot

__all__ = [
    'BaseBot', 'TelegramBot', 'SynologyChatBot'
] 