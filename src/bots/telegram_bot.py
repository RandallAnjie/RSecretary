"""
Telegram机器人实现
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from loguru import logger

from .base_bot import BaseBot, BotEvent
from ..config.settings import settings


class TelegramBot(BaseBot):
    """Telegram机器人实现"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化Telegram机器人
        
        Args:
            token: Telegram机器人令牌
        """
        super().__init__("RSecretary", "Telegram")
        
        self.token = token or settings.bots.telegram.token
        if not self.token:
            raise ValueError("Telegram机器人令牌未配置")
        
        self.application = None
        self.webhook_url = None
        
        logger.info("Telegram机器人初始化完成")
    
    async def initialize(self) -> bool:
        """
        初始化Telegram机器人连接
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建应用程序
            self.application = ApplicationBuilder().token(self.token).build()
            
            # 注册处理器
            self._setup_handlers()
            
            # 测试连接
            bot_info = await self.application.bot.get_me()
            logger.info(f"Telegram机器人连接成功: @{bot_info.username}")
            
            return True
            
        except Exception as e:
            logger.error(f"Telegram机器人初始化失败: {e}")
            return False
    
    def _setup_handlers(self) -> None:
        """设置消息和命令处理器"""
        # 命令处理器
        self.application.add_handler(CommandHandler("start", self._handle_start_command))
        self.application.add_handler(CommandHandler("help", self._handle_help_command_tg))
        self.application.add_handler(CommandHandler("status", self._handle_status_command_tg))
        self.application.add_handler(CommandHandler("stats", self._handle_stats_command_tg))
        self.application.add_handler(CommandHandler("clear", self._handle_clear_command_tg))
        self.application.add_handler(CommandHandler("menu", self._handle_menu_command))
        
        # 消息处理器
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        
        # 错误处理器
        self.application.add_error_handler(self._handle_error)
    
    async def start(self) -> None:
        """启动Telegram机器人"""
        try:
            if not self.application:
                raise RuntimeError("机器人未初始化")
            
            self.is_running = True
            self.start_time = datetime.now(timezone.utc)
            
            # 启动轮询
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Telegram机器人启动成功")
            
        except Exception as e:
            logger.error(f"Telegram机器人启动失败: {e}")
            self.is_running = False
            raise
    
    async def stop(self) -> None:
        """停止Telegram机器人"""
        try:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            self.is_running = False
            logger.info("Telegram机器人已停止")
            
        except Exception as e:
            logger.error(f"Telegram机器人停止失败: {e}")
    
    async def send_message(self, user_id: str, message: str, **kwargs) -> bool:
        """
        发送消息
        
        Args:
            user_id: 用户ID
            message: 消息内容
            **kwargs: Telegram特定参数
            
        Returns:
            bool: 发送是否成功
        """
        try:
            if not self.application:
                return False
            
            # 清理和转义Markdown字符
            cleaned_message = self._clean_markdown(message)
            
            # 拆分长消息
            max_length = 4096
            if len(cleaned_message) > max_length:
                for i in range(0, len(cleaned_message), max_length):
                    chunk = cleaned_message[i:i + max_length]
                    await self._send_message_chunk(user_id, chunk, **kwargs)
            else:
                await self._send_message_chunk(user_id, cleaned_message, **kwargs)
            
            return True
            
        except Exception as e:
            logger.error(f"发送Telegram消息失败: {e}")
            return False
    
    def _clean_markdown(self, text: str) -> str:
        """
        清理和修复Markdown格式
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return text
        
        # 转义特殊字符
        special_chars = ['_', '*', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        cleaned_text = text
        
        # 简单清理：移除可能有问题的Markdown字符
        # 这里采用保守策略，如果检测到可能的格式问题就移除Markdown
        if self._has_markdown_issues(text):
            for char in special_chars:
                cleaned_text = cleaned_text.replace(char, f'\\{char}')
            return cleaned_text
        
        return cleaned_text
    
    def _has_markdown_issues(self, text: str) -> bool:
        """
        检测文本是否有Markdown格式问题
        
        Args:
            text: 待检测文本
            
        Returns:
            bool: 是否有格式问题
        """
        # 检查未配对的Markdown字符
        markdown_chars = ['*', '_', '`', '[', ']']
        for char in markdown_chars:
            count = text.count(char)
            if char in ['[', ']']:
                # 方括号需要成对出现
                if text.count('[') != text.count(']'):
                    return True
            elif count % 2 != 0:
                # 其他字符需要成对出现
                return True
        
        return False
    
    async def _send_message_chunk(self, user_id: str, text: str, **kwargs) -> None:
        """
        发送消息块，带有重试机制
        
        Args:
            user_id: 用户ID
            text: 消息文本
            **kwargs: 其他参数
        """
        try:
            # 首先尝试Markdown模式
            await self.application.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='Markdown',
                **kwargs
            )
        except Exception as e:
            if "can't parse entities" in str(e).lower():
                logger.warning("Markdown解析失败，尝试HTML模式")
                try:
                    # Markdown失败时尝试HTML模式
                    html_text = text.replace('*', '<b>').replace('*', '</b>')
                    html_text = html_text.replace('_', '<i>').replace('_', '</i>')
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=html_text,
                        parse_mode='HTML',
                        **kwargs
                    )
                except Exception:
                    logger.warning("HTML解析也失败，使用纯文本模式")
                    # 最后尝试纯文本模式
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=text,
                        **kwargs
                    )
            else:
                raise
    
    async def send_rich_message(
        self, 
        user_id: str, 
        content: Dict[str, Any], 
        **kwargs
    ) -> bool:
        """
        发送富媒体消息
        
        Args:
            user_id: 用户ID
            content: 富媒体内容
            **kwargs: Telegram特定参数
            
        Returns:
            bool: 发送是否成功
        """
        try:
            if not self.application:
                return False
            
            message_text = content.get("text", "")
            
            # 处理按钮
            reply_markup = None
            if "buttons" in content:
                keyboard = []
                for row in content["buttons"]:
                    button_row = []
                    for button in row:
                        button_row.append(InlineKeyboardButton(
                            text=button["text"],
                            callback_data=button.get("callback_data", ""),
                            url=button.get("url")
                        ))
                    keyboard.append(button_row)
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 发送消息
            await self.application.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                **kwargs
            )
            
            return True
            
        except Exception as e:
            logger.error(f"发送Telegram富媒体消息失败: {e}")
            return False
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文本消息"""
        try:
            user_id = str(update.effective_user.id)
            message = update.message.text
            
            # 处理消息事件
            await self.handle_message_event(user_id, message, {"update": update})
            
        except Exception as e:
            logger.error(f"处理Telegram消息失败: {e}")
    
    async def _handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.first_name or "朋友"
        
        welcome_text = f"""
🎉 欢迎使用 {self.name}！

你好 {user_name}！我是你的智能生活助理，可以帮助你：

📝 **记账管理**
直接告诉我你的收入和支出，我会自动记录

💰 **订阅管理** 
管理你的各种订阅服务，提醒续费

✅ **待办事项**
创建和管理你的任务清单

🔍 **智能查询**
随时查看你的财务状况和任务安排

💬 **自然对话**
用自然语言和我交流，无需复杂命令

发送 /help 查看详细使用说明
发送 /menu 查看快速菜单
        """
        
        await self.send_message(user_id, welcome_text.strip())
        
        # 发送任务建议
        await self.send_task_suggestions(user_id)
    
    async def _handle_help_command_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        user_id = str(update.effective_user.id)
        await self.handle_command(user_id, "help")
    
    async def _handle_status_command_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /status 命令"""
        user_id = str(update.effective_user.id)
        await self.handle_command(user_id, "status")
    
    async def _handle_stats_command_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /stats 命令"""
        user_id = str(update.effective_user.id)
        await self.handle_command(user_id, "stats")
    
    async def _handle_clear_command_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /clear 命令"""
        user_id = str(update.effective_user.id)
        await self.handle_command(user_id, "clear")
    
    async def _handle_menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /menu 命令"""
        user_id = str(update.effective_user.id)
        
        keyboard = [
            [
                InlineKeyboardButton("💰 查看本月账单", callback_data="query_monthly_accounting"),
                InlineKeyboardButton("📱 查看订阅", callback_data="query_subscriptions")
            ],
            [
                InlineKeyboardButton("✅ 今日待办", callback_data="query_today_todos"),
                InlineKeyboardButton("📊 使用统计", callback_data="show_stats")
            ],
            [
                InlineKeyboardButton("❓ 帮助", callback_data="show_help"),
                InlineKeyboardButton("🔄 清除历史", callback_data="clear_context")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.application.bot.send_message(
            chat_id=user_id,
            text="🎛️ **快速菜单**\n\n选择你需要的功能：",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _handle_error(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理错误"""
        self.error_count += 1
        logger.error(f"Telegram机器人错误: {context.error}")
        
        if update and update.effective_user:
            user_id = str(update.effective_user.id)
            await self.send_message(user_id, "抱歉，处理您的请求时出现了错误，请稍后再试。")
    
    async def set_webhook(self, webhook_url: str, port: int = 8443) -> bool:
        """
        设置Webhook模式
        
        Args:
            webhook_url: Webhook URL
            port: 端口号
            
        Returns:
            bool: 设置是否成功
        """
        try:
            if not self.application:
                return False
            
            await self.application.bot.set_webhook(url=webhook_url)
            self.webhook_url = webhook_url
            
            logger.info(f"Telegram Webhook设置成功: {webhook_url}")
            return True
            
        except Exception as e:
            logger.error(f"设置Telegram Webhook失败: {e}")
            return False
    
    async def start_webhook(self, listen: str = "0.0.0.0", port: int = 8443) -> None:
        """
        启动Webhook服务器
        
        Args:
            listen: 监听地址
            port: 监听端口
        """
        try:
            if not self.application:
                raise RuntimeError("机器人未初始化")
            
            self.is_running = True
            self.start_time = datetime.now(timezone.utc)
            
            # 启动Webhook
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_webhook(
                listen=listen,
                port=port,
                webhook_url=self.webhook_url
            )
            
            logger.info(f"Telegram Webhook服务器启动成功: {listen}:{port}")
            
        except Exception as e:
            logger.error(f"Telegram Webhook服务器启动失败: {e}")
            self.is_running = False
            raise
    
    async def send_notification(self, user_id: str, notification_type: str, data: Dict[str, Any]) -> bool:
        """
        发送通知消息
        
        Args:
            user_id: 用户ID
            notification_type: 通知类型
            data: 通知数据
            
        Returns:
            bool: 发送是否成功
        """
        try:
            if notification_type == "subscription_renewal":
                # 订阅续费提醒
                subscription_name = data.get("name", "未知订阅")
                price = data.get("price", 0)
                renewal_date = data.get("renewal_date", "")
                
                message = f"""
🔔 **订阅续费提醒**

📱 订阅服务：{subscription_name}
💰 费用：{price}元
📅 续费日期：{renewal_date}

请及时准备续费或考虑是否需要取消该订阅。
                """
                
                keyboard = [[
                    InlineKeyboardButton("✅ 已处理", callback_data=f"mark_handled_{data.get('id', '')}"),
                    InlineKeyboardButton("❌ 取消订阅", callback_data=f"cancel_subscription_{data.get('id', '')}")
                ]]
                
                await self.send_rich_message(user_id, {
                    "text": message.strip(),
                    "buttons": keyboard
                })
                
            elif notification_type == "todo_reminder":
                # 待办事项提醒
                title = data.get("title", "未知任务")
                due_date = data.get("due_date", "")
                priority = data.get("priority", "中")
                
                priority_emoji = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(priority, "🟡")
                
                message = f"""
⏰ **待办事项提醒**

{priority_emoji} 任务：{title}
📅 截止日期：{due_date}
⭐ 优先级：{priority}

别忘了完成这个任务哦！
                """
                
                keyboard = [[
                    InlineKeyboardButton("✅ 完成任务", callback_data=f"complete_todo_{data.get('id', '')}"),
                    InlineKeyboardButton("⏰ 稍后提醒", callback_data=f"snooze_todo_{data.get('id', '')}")
                ]]
                
                await self.send_rich_message(user_id, {
                    "text": message.strip(),
                    "buttons": keyboard
                })
                
            return True
            
        except Exception as e:
            logger.error(f"发送Telegram通知失败: {e}")
            return False
    
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[Dict]: 用户信息
        """
        # 注意：这里需要在实际的消息处理过程中收集用户信息
        # 这里只是一个示例接口
        return {
            "platform": self.platform,
            "user_id": user_id,
            "username": None,  # 需要从实际交互中获取
            "first_name": None,
            "last_name": None,
            "language_code": None
        } 