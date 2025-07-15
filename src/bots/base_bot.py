"""
基础机器人类
定义所有机器人的通用接口和行为
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
from loguru import logger

from ..core.message_processor import MessageProcessor


class BotEvent:
    """机器人事件类"""
    
    def __init__(
        self,
        event_type: str,
        user_id: str,
        message: str = "",
        platform: str = "",
        raw_data: Optional[Dict[str, Any]] = None
    ):
        self.event_type = event_type  # message, command, callback等
        self.user_id = user_id
        self.message = message
        self.platform = platform
        self.raw_data = raw_data or {}
        self.timestamp = datetime.now(timezone.utc)


class BaseBot(ABC):
    """
    基础机器人类
    所有机器人都应该继承这个基类
    """
    
    def __init__(self, name: str, platform: str):
        """
        初始化机器人
        
        Args:
            name: 机器人名称
            platform: 平台名称
        """
        self.name = name
        self.platform = platform
        self.is_running = False
        self.message_processor = MessageProcessor()
        
        # 事件处理器
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # 运行状态
        self.start_time = None
        self.message_count = 0
        self.error_count = 0
        
        logger.info(f"{self.platform} 机器人 '{self.name}' 初始化完成")
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化机器人连接
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """启动机器人"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止机器人"""
        pass
    
    @abstractmethod
    async def send_message(self, user_id: str, message: str, **kwargs) -> bool:
        """
        发送消息
        
        Args:
            user_id: 用户ID
            message: 消息内容
            **kwargs: 平台特定参数
            
        Returns:
            bool: 发送是否成功
        """
        pass
    
    @abstractmethod
    async def send_rich_message(
        self, 
        user_id: str, 
        content: Dict[str, Any], 
        **kwargs
    ) -> bool:
        """
        发送富媒体消息（图片、按钮等）
        
        Args:
            user_id: 用户ID
            content: 富媒体内容
            **kwargs: 平台特定参数
            
        Returns:
            bool: 发送是否成功
        """
        pass
    
    async def process_message(self, user_id: str, message: str) -> str:
        """
        处理用户消息
        
        Args:
            user_id: 用户ID
            message: 用户消息
            
        Returns:
            str: 处理结果
        """
        try:
            self.message_count += 1
            
            # 使用消息处理器处理消息
            response = await self.message_processor.process_message(
                message=message,
                user_id=user_id,
                platform=self.platform
            )
            
            return response
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"消息处理失败: {e}")
            return "抱歉，处理您的消息时出现了问题。"
    
    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        添加事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def emit_event(self, event: BotEvent) -> None:
        """
        触发事件
        
        Args:
            event: 事件对象
        """
        try:
            handlers = self.event_handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"事件处理器执行失败: {e}")
        except Exception as e:
            logger.error(f"事件触发失败: {e}")
    
    async def handle_message_event(self, user_id: str, message: str, raw_data: Optional[Dict] = None) -> None:
        """
        处理消息事件
        
        Args:
            user_id: 用户ID
            message: 消息内容
            raw_data: 原始数据
        """
        try:
            # 创建事件
            event = BotEvent(
                event_type="message",
                user_id=user_id,
                message=message,
                platform=self.platform,
                raw_data=raw_data
            )
            
            # 触发事件
            await self.emit_event(event)
            
            # 处理消息
            response = await self.process_message(user_id, message)
            
            # 发送回复
            if response:
                await self.send_message(user_id, response)
                
        except Exception as e:
            logger.error(f"消息事件处理失败: {e}")
            try:
                await self.send_message(user_id, "抱歉，处理您的消息时出现了问题。")
            except:
                pass
    
    async def handle_command(self, user_id: str, command: str, args: List[str] = None) -> None:
        """
        处理命令
        
        Args:
            user_id: 用户ID
            command: 命令名称
            args: 命令参数
        """
        try:
            args = args or []
            
            # 内置命令
            if command == "help":
                await self._handle_help_command(user_id)
            elif command == "status":
                await self._handle_status_command(user_id)
            elif command == "stats":
                await self._handle_stats_command(user_id)
            elif command == "clear":
                await self._handle_clear_command(user_id)
            else:
                # 创建命令事件
                event = BotEvent(
                    event_type="command",
                    user_id=user_id,
                    message=f"/{command} {' '.join(args)}",
                    platform=self.platform,
                    raw_data={"command": command, "args": args}
                )
                await self.emit_event(event)
                
        except Exception as e:
            logger.error(f"命令处理失败: {e}")
            await self.send_message(user_id, "命令执行失败。")
    
    async def _handle_help_command(self, user_id: str) -> None:
        """处理帮助命令"""
        help_text = f"""
🤖 {self.name} 使用指南

📝 基础功能：
• 记账：直接说 "花了50元买咖啡" 或 "收入1000元工资"
• 订阅：说 "订阅Netflix每月30元" 
• 待办：说 "提醒我明天开会" 或 "添加任务完成报告"

🔍 查询功能：
• "本月花了多少钱"
• "我的订阅有哪些"
• "今天有什么任务"

⚙️ 命令：
/help - 显示帮助
/status - 查看状态
/stats - 查看统计
/clear - 清除对话历史

💬 支持自然语言对话，直接告诉我你要做什么！
        """
        await self.send_message(user_id, help_text.strip())
    
    async def _handle_status_command(self, user_id: str) -> None:
        """处理状态命令"""
        uptime = ""
        if self.start_time:
            delta = datetime.now(timezone.utc) - self.start_time
            hours = delta.total_seconds() // 3600
            minutes = (delta.total_seconds() % 3600) // 60
            uptime = f"{int(hours)}小时{int(minutes)}分钟"
        
        status_text = f"""
🤖 机器人状态

📊 基本信息：
• 名称：{self.name}
• 平台：{self.platform}
• 状态：{'运行中' if self.is_running else '停止'}
• 运行时间：{uptime}

📈 统计信息：
• 处理消息数：{self.message_count}
• 错误次数：{self.error_count}
• 成功率：{((self.message_count - self.error_count) / max(self.message_count, 1) * 100):.1f}%
        """
        await self.send_message(user_id, status_text.strip())
    
    async def _handle_stats_command(self, user_id: str) -> None:
        """处理统计命令"""
        try:
            # 获取用户统计信息
            stats = await self.message_processor.get_user_stats(user_id)
            
            stats_text = "📊 您的使用统计：\n\n"
            
            # 记账统计
            if "accounting" in stats:
                acc_stats = stats["accounting"]
                stats_text += f"💰 记账（{acc_stats.get('period', '本月')}）：\n"
                stats_text += f"• 收入：{acc_stats.get('total_income', 0)}元\n"
                stats_text += f"• 支出：{acc_stats.get('total_expense', 0)}元\n"
                stats_text += f"• 净额：{acc_stats.get('net_amount', 0)}元\n\n"
            
            # 订阅统计
            if "subscription" in stats:
                sub_stats = stats["subscription"]
                stats_text += f"📱 订阅统计：\n"
                stats_text += f"• 订阅数量：{sub_stats.get('subscription_count', 0)}个\n"
                stats_text += f"• 月度成本：{sub_stats.get('total_monthly_cost', 0)}元\n"
                stats_text += f"• 年度成本：{sub_stats.get('annual_cost', 0)}元\n\n"
            
            # 待办统计
            if "todo" in stats:
                todo_stats = stats["todo"]
                stats_text += f"✅ 待办事项：\n"
                stats_text += f"• 今日任务：{todo_stats.get('today_count', 0)}项\n"
                stats_text += f"• 逾期任务：{todo_stats.get('overdue_count', 0)}项\n"
            
            if len(stats_text) == len("📊 您的使用统计：\n\n"):
                stats_text += "暂无统计数据，开始使用功能后会显示统计信息。"
            
            await self.send_message(user_id, stats_text.strip())
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            await self.send_message(user_id, "获取统计信息失败，请稍后再试。")
    
    async def _handle_clear_command(self, user_id: str) -> None:
        """处理清除命令"""
        try:
            self.message_processor.clear_conversation_context(user_id)
            await self.send_message(user_id, "✅ 对话历史已清除。")
        except Exception as e:
            logger.error(f"清除对话历史失败: {e}")
            await self.send_message(user_id, "清除失败，请稍后再试。")
    
    async def send_task_suggestions(self, user_id: str) -> None:
        """发送任务建议"""
        try:
            suggestions = await self.message_processor.get_task_suggestions(user_id)
            
            if suggestions:
                message = "📋 今日提醒：\n\n"
                for i, suggestion in enumerate(suggestions, 1):
                    message += f"{i}. {suggestion}\n"
                
                await self.send_message(user_id, message.strip())
            
        except Exception as e:
            logger.error(f"发送任务建议失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取机器人统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        uptime = 0
        if self.start_time:
            delta = datetime.now(timezone.utc) - self.start_time
            uptime = delta.total_seconds()
        
        return {
            "name": self.name,
            "platform": self.platform,
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "success_rate": (self.message_count - self.error_count) / max(self.message_count, 1) * 100
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            Dict[str, Any]: 健康状态
        """
        try:
            # 基本状态检查
            status = {
                "name": self.name,
                "platform": self.platform,
                "is_running": self.is_running,
                "healthy": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # 检查消息处理器
            if not self.message_processor:
                status["healthy"] = False
                status["error"] = "消息处理器未初始化"
                return status
            
            # 检查AI连接
            try:
                ai_health = await self.message_processor.gemini_client.test_connection()
                status["ai_healthy"] = ai_health
                if not ai_health:
                    status["healthy"] = False
            except Exception as e:
                status["ai_healthy"] = False
                status["ai_error"] = str(e)
                status["healthy"] = False
            
            # 检查Notion连接
            try:
                notion_health = await self.message_processor.task_dispatcher.task_history  # 简单检查
                status["storage_healthy"] = True
            except Exception as e:
                status["storage_healthy"] = False
                status["storage_error"] = str(e)
                status["healthy"] = False
            
            return status
            
        except Exception as e:
            return {
                "name": self.name,
                "platform": self.platform,
                "is_running": False,
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            } 