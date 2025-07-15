"""
Synology Chat机器人实现
使用webhook方式与Synology Chat集成
"""

import asyncio
import json
import aiohttp
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from aiohttp import web
from loguru import logger

from .base_bot import BaseBot, BotEvent
from ..config.settings import settings


class SynologyChatBot(BaseBot):
    """Synology Chat机器人实现"""
    
    def __init__(self, webhook_url: Optional[str] = None, token: Optional[str] = None):
        """
        初始化Synology Chat机器人
        
        Args:
            webhook_url: Incoming Webhook URL
            token: 访问令牌
        """
        super().__init__("RSecretary", "Synology Chat")
        
        self.webhook_url = webhook_url or settings.bots.synology_chat.webhook_url
        self.token = token or settings.bots.synology_chat.token
        
        if not self.webhook_url:
            raise ValueError("Synology Chat Webhook URL未配置")
        if not self.token:
            raise ValueError("Synology Chat Token未配置")
        
        # 解析webhook URL获取基本信息
        self._parse_webhook_url()
        
        # Web服务器用于接收outgoing webhooks
        self.app = web.Application()
        self.runner = None
        self.site = None
        
        # Ngrok配置
        self.use_ngrok = settings.bots.synology_chat.use_ngrok
        self.ngrok_auth_token = settings.bots.synology_chat.ngrok_auth_token
        self.ngrok_domain = settings.bots.synology_chat.ngrok_domain
        self.local_port = settings.bots.synology_chat.local_port
        self.ngrok_process = None
        self.ngrok_url = None
        
        # SSL配置
        self.verify_ssl = settings.bots.synology_chat.verify_ssl
        
        logger.info("Synology Chat机器人初始化完成")
        if self.use_ngrok:
            logger.info("已启用Ngrok调试模式")
        if not self.verify_ssl:
            logger.warning("SSL证书验证已禁用，仅建议在开发环境使用")
    
    def _parse_webhook_url(self) -> None:
        """解析webhook URL获取hostname等信息"""
        try:
            # Webhook URL格式: https://hostname:port/webapi/entry.cgi?api=SYNO.Chat.External&method=incoming&version=2&token=...
            import urllib.parse
            parsed = urllib.parse.urlparse(self.webhook_url)
            self.hostname = parsed.hostname
            self.port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            self.use_https = parsed.scheme == 'https'
            
            logger.info(f"Synology Chat服务器: {self.hostname}:{self.port} (HTTPS: {self.use_https})")
            
        except Exception as e:
            logger.error(f"解析webhook URL失败: {e}")
            raise
    
    async def _setup_ngrok(self) -> bool:
        """
        设置Ngrok隧道
        
        Returns:
            bool: 设置是否成功
        """
        if not self.use_ngrok:
            return True
            
        try:
            # 检查是否安装了ngrok
            result = subprocess.run(['ngrok', 'version'], 
                                    capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.error("Ngrok未安装或不在PATH中")
                return False
            
            logger.info(f"检测到Ngrok: {result.stdout.strip()}")
            
            # 设置认证令牌（如果提供）
            if self.ngrok_auth_token:
                auth_result = subprocess.run(['ngrok', 'config', 'add-authtoken', self.ngrok_auth_token],
                                           capture_output=True, text=True, timeout=10)
                if auth_result.returncode == 0:
                    logger.info("Ngrok认证令牌设置成功")
                else:
                    logger.warning(f"设置Ngrok认证令牌失败: {auth_result.stderr}")
            
            # 构建ngrok命令
            ngrok_cmd = ['ngrok', 'http', str(self.local_port), '--log=stdout']
            
            # 如果有自定义域名
            if self.ngrok_domain:
                ngrok_cmd.extend(['--domain', self.ngrok_domain])
            
            # 启动ngrok进程
            logger.info(f"启动Ngrok隧道: {' '.join(ngrok_cmd)}")
            self.ngrok_process = subprocess.Popen(
                ngrok_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 等待ngrok启动并获取URL
            max_attempts = 30
            for attempt in range(max_attempts):
                try:
                    # 尝试获取ngrok API信息
                    async with aiohttp.ClientSession() as session:
                        async with session.get('http://127.0.0.1:4040/api/tunnels') as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                tunnels = data.get('tunnels', [])
                                if tunnels:
                                    self.ngrok_url = tunnels[0]['public_url']
                                    logger.info(f"Ngrok隧道已建立: {self.ngrok_url}")
                                    logger.info(f"Webhook URL: {self.ngrok_url}/webhook")
                                    return True
                except:
                    pass
                
                await asyncio.sleep(1)
            
            logger.error("Ngrok启动超时")
            return False
            
        except subprocess.TimeoutExpired:
            logger.error("Ngrok命令执行超时")
            return False
        except Exception as e:
            logger.error(f"设置Ngrok失败: {e}")
            return False
    
    async def _cleanup_ngrok(self) -> None:
        """清理Ngrok进程"""
        if self.ngrok_process:
            try:
                self.ngrok_process.terminate()
                self.ngrok_process.wait(timeout=5)
                logger.info("Ngrok进程已终止")
            except subprocess.TimeoutExpired:
                self.ngrok_process.kill()
                logger.warning("强制终止Ngrok进程")
            except Exception as e:
                logger.error(f"清理Ngrok进程失败: {e}")
    
    async def initialize(self) -> bool:
        """
        初始化Synology Chat机器人连接
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 设置ngrok（如果启用）
            if not await self._setup_ngrok():
                if self.use_ngrok:
                    logger.error("Ngrok设置失败")
                    return False
            
            # 设置webhook处理器
            self._setup_webhook_handlers()
            
            # 测试连接 - 发送一条测试消息
            test_success = await self.send_message("system", "🤖 RSecretary机器人已启动！")
            
            if test_success:
                logger.info("Synology Chat机器人连接测试成功")
                return True
            else:
                logger.error("Synology Chat机器人连接测试失败")
                return False
            
        except Exception as e:
            logger.error(f"Synology Chat机器人初始化失败: {e}")
            return False
    
    def _setup_webhook_handlers(self) -> None:
        """设置webhook处理器"""
        # Outgoing webhook处理器
        self.app.router.add_post('/webhook', self._handle_outgoing_webhook)
        
        # 健康检查
        self.app.router.add_get('/health', self._handle_health_check)
        
        # Ngrok信息查看
        self.app.router.add_get('/ngrok-info', self._handle_ngrok_info)
    
    async def start(self) -> None:
        """启动Synology Chat机器人"""
        try:
            self.is_running = True
            self.start_time = datetime.now(timezone.utc)
            
            # 启动web服务器监听outgoing webhooks
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.local_port)
            await self.site.start()
            
            logger.info(f"Synology Chat机器人启动成功，监听端口: {self.local_port}")
            
            if self.use_ngrok and self.ngrok_url:
                logger.info(f"🌐 Ngrok隧道: {self.ngrok_url}")
                logger.info(f"📡 配置Outgoing Webhook URL: {self.ngrok_url}/webhook")
                logger.info(f"🔧 调试面板: http://127.0.0.1:4040")
            else:
                logger.info(f"📡 Outgoing Webhook URL: http://your-server-ip:{self.local_port}/webhook")
            
            # 持续运行直到收到停止信号
            while self.is_running:
                await asyncio.sleep(1)  # 每秒检查一次运行状态
            
        except Exception as e:
            logger.error(f"Synology Chat机器人启动失败: {e}")
            self.is_running = False
            raise
    
    async def stop(self) -> None:
        """停止Synology Chat机器人"""
        try:
            logger.info("正在停止Synology Chat机器人...")
            self.is_running = False  # 设置停止标志
            
            # 停止Web服务器
            if hasattr(self, 'site') and self.site:
                await self.site.stop()
            
            if hasattr(self, 'runner') and self.runner:
                await self.runner.cleanup()
            
            # 清理Ngrok进程
            await self._cleanup_ngrok()
            
            logger.info("Synology Chat机器人已停止")
            
        except Exception as e:
            logger.error(f"停止Synology Chat机器人失败: {e}")
    
    async def send_message(self, user_id: str, message: str, **kwargs) -> bool:
        """
        发送消息到Synology Chat
        
        Args:
            user_id: 用户ID（对于Synology Chat这个参数不使用，所有消息发送到配置的频道）
            message: 消息内容
            **kwargs: 额外参数
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 清理消息格式
            cleaned_message = self._clean_message(message)
            
            # 准备payload
            payload = {
                "text": cleaned_message
            }
            
            # 如果有附件URL
            if 'file_url' in kwargs:
                payload['file_url'] = kwargs['file_url']
            
            # 发送请求
            connector = None
            if not self.verify_ssl:
                # 创建忽略SSL验证的连接器
                import ssl
                import aiohttp
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    ssl=self.verify_ssl if self.use_https else None
                ) as response:
                    if response.status == 200:
                        self.message_count += 1
                        logger.debug(f"消息发送成功到Synology Chat")
                        return True
                    else:
                        logger.error(f"发送消息失败: HTTP {response.status}")
                        self.error_count += 1
                        return False
                        
        except Exception as e:
            logger.error(f"发送消息到Synology Chat失败: {e}")
            self.error_count += 1
            return False
    
    def _clean_message(self, message: str) -> str:
        """
        清理消息格式，适配Synology Chat
        
        Args:
            message: 原始消息
            
        Returns:
            str: 清理后的消息
        """
        # Synology Chat对Markdown支持有限，需要转换为纯文本格式
        cleaned = message
        
        # 移除Markdown格式标记
        import re
        
        # 移除代码块标记
        cleaned = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).replace('```', ''), cleaned)
        cleaned = cleaned.replace('```', '')
        
        # 转换粗体文本（**text** 或 __text__）为纯文本
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'__(.*?)__', r'\1', cleaned)
        
        # 转换斜体文本（*text* 或 _text_）为纯文本
        cleaned = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'\1', cleaned)
        cleaned = re.sub(r'(?<!_)_(?!_)([^_]+)_(?!_)', r'\1', cleaned)
        
        # 处理链接格式 - 转换为Synology Chat支持的格式
        # Markdown链接 [text](url) 转换为 <url|text>
        cleaned = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', cleaned)
        
        # 处理Notion链接，简化显示
        # 替换长链接为简化格式
        cleaned = re.sub(r'<(https://www\.notion\.so/[^|>]+)\|([^>]+)>', r'<\1|链接>', cleaned)
        cleaned = re.sub(r'https://www\.notion\.so/[a-zA-Z0-9]+', r'<\g<0>|链接>', cleaned)
        
        # 处理表情符号和特殊字符
        emoji_map = {
            '🔥': '【高】',
            '📝': '【待完成】',
            '✅': '【已完成】',
            '⏰': '【进行中】',
            '❌': '【已取消】',
            '📢': '【通知】',
            '🌐': '【网络】',
            '📡': '【配置】',
            '🔧': '【调试】',
            '📅': '【日期】'
        }
        
        for emoji, text in emoji_map.items():
            cleaned = cleaned.replace(emoji, text)
        
        # 处理过长的消息
        if len(cleaned) > 2000:
            cleaned = cleaned[:1950] + "\n\n...(消息太长，已截断)"
        
        return cleaned
    
    async def send_rich_message(
        self, 
        user_id: str, 
        content: Dict[str, Any], 
        **kwargs
    ) -> bool:
        """
        发送富文本消息
        
        Args:
            user_id: 用户ID
            content: 消息内容
            **kwargs: 额外参数
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 构建消息文本
            message_parts = []
            
            if content.get('title'):
                message_parts.append(f"**{content['title']}**")
            
            if content.get('description'):
                message_parts.append(content['description'])
            
            if content.get('fields'):
                for field in content['fields']:
                    if isinstance(field, dict):
                        name = field.get('name', '')
                        value = field.get('value', '')
                        message_parts.append(f"• {name}: {value}")
            
            message = '\n'.join(message_parts)
            
            # 发送消息
            return await self.send_message(user_id, message, **kwargs)
            
        except Exception as e:
            logger.error(f"发送富文本消息失败: {e}")
            return False
    
    async def _handle_outgoing_webhook(self, request: web.Request) -> web.Response:
        """
        处理来自Synology Chat的outgoing webhook
        
        Args:
            request: HTTP请求
            
        Returns:
            web.Response: HTTP响应
        """
        try:
            # 解析表单数据
            data = await request.post()
            
            # 验证token
            client_token = data.get('token', '')
            if client_token != self.token:
                logger.warning(f"Outgoing webhook token验证失败: {client_token}")
                return web.json_response({"text": "Token验证失败"}, status=401)
            
            # 提取消息信息
            user_id = data.get('user_id', '')
            username = data.get('username', '')
            text = data.get('text', '')
            channel_name = data.get('channel_name', '')
            
            logger.info(f"收到Synology Chat消息: {username}({user_id}): {text}")
            
            # 处理消息
            if text.strip():
                # 自动订阅每日推送（如果用户还未订阅）
                await self._auto_subscribe_daily_push(user_id, username)
                
                # 检查是否是命令
                if text.startswith('/'):
                    response_text = await self._handle_command(text, user_id, username)
                else:
                    # 创建事件
                    event = BotEvent(
                        event_type="message",
                        user_id=user_id,
                        message=text,
                        platform=self.platform,
                        raw_data=dict(data)
                    )
                    
                    # 处理消息
                    response_text = await self.process_message(user_id, text)
                
                # 返回响应（这会作为机器人的回复发送到频道）
                return web.json_response({"text": response_text})
            
            return web.json_response({"text": ""})  # 空响应
            
        except Exception as e:
            logger.error(f"处理outgoing webhook失败: {e}")
            return web.json_response({"text": "处理消息时出错"}, status=500)
    
    async def _handle_health_check(self, request: web.Request) -> web.Response:
        """健康检查端点"""
        return web.json_response({
            "status": "ok",
            "platform": self.platform,
            "name": self.name,
            "is_running": self.is_running,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "use_ngrok": self.use_ngrok,
            "ngrok_url": self.ngrok_url if self.use_ngrok else None
        })
    
    async def _handle_ngrok_info(self, request: web.Request) -> web.Response:
        """Ngrok信息查看端点"""
        if not self.use_ngrok:
            return web.json_response({"error": "Ngrok未启用"}, status=404)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://127.0.0.1:4040/api/tunnels') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return web.json_response({
                            "ngrok_enabled": True,
                            "tunnels": data.get('tunnels', []),
                            "webhook_url": f"{self.ngrok_url}/webhook" if self.ngrok_url else None
                        })
                    else:
                        return web.json_response({"error": "无法连接到Ngrok API"}, status=503)
        except Exception as e:
            return web.json_response({"error": f"获取Ngrok信息失败: {str(e)}"}, status=500)
    
    async def _auto_subscribe_daily_push(self, user_id: str, username: str) -> None:
        """
        自动订阅每日推送（如果用户还未订阅）
        
        Args:
            user_id: 用户ID
            username: 用户名
        """
        try:
            if hasattr(self, 'message_processor') and self.message_processor.scheduler:
                scheduler = self.message_processor.scheduler
                
                # 检查用户是否已订阅
                if not scheduler.is_user_subscribed(user_id, "synology_chat"):
                    # 自动添加订阅
                    scheduler.add_daily_push_user(user_id, "synology_chat")
                    logger.info(f"自动订阅每日推送: {username} ({user_id})")
                    
                    # 发送欢迎消息（可选）
                    # 这里可以选择是否发送欢迎消息，暂时注释掉
                    # welcome_msg = f"✅ 欢迎使用 RSecretary！\n\n您已自动订阅每日推送功能：\n- 🌅 每天早上8点发送早安问候\n- 💰 昨日收支情况统计\n- 📝 今日待办事项提醒\n\n输入 /help 查看更多命令"
                    # await self.send_message(user_id, welcome_msg)
                    
        except Exception as e:
            logger.error(f"自动订阅每日推送失败: {e}")
    
    async def _handle_command(self, command: str, user_id: str, username: str) -> str:
        """
        处理命令
        
        Args:
            command: 命令文本
            user_id: 用户ID
            username: 用户名
            
        Returns:
            str: 命令处理结果
        """
        try:
            command = command.strip()
            
            if command == "/subscribe_daily":
                # 订阅每日推送
                if hasattr(self, 'message_processor') and self.message_processor.scheduler:
                    scheduler = self.message_processor.scheduler
                    
                    if scheduler.is_user_subscribed(user_id, "synology_chat"):
                        return f"✅ 您已经订阅了每日推送！\n\n用户 {username} 当前订阅状态：已激活\n\n【推送时间】每天早上 8:00\n【推送内容】\n- 🌅 早安问候\n- 💰 昨日收支情况\n- 📝 今日待办事项\n\n输入 /daily_report 可立即查看今日报告\n输入 /unsubscribe_daily 可取消订阅"
                    else:
                        scheduler.add_daily_push_user(user_id, "synology_chat")
                        return f"✅ 订阅成功！\n用户 {username} 已成功订阅每日推送。\n\n【推送时间】每天早上 8:00\n\n【推送内容】\n- 🌅 早安问候\n- 💰 昨日收支情况\n- 📝 今日待办事项\n\n输入 /daily_report 可立即查看今日报告"
                else:
                    return "订阅功能暂时不可用，调度器未初始化"
            
            elif command == "/unsubscribe_daily":
                # 取消每日推送订阅
                if hasattr(self, 'message_processor') and self.message_processor.scheduler:
                    scheduler = self.message_processor.scheduler
                    scheduler.remove_daily_push_user(user_id, "synology_chat")
                    return f"✅ 取消成功！\n用户 {username} 已取消每日推送订阅。\n\n如需重新订阅，请输入 /subscribe_daily"
                else:
                    return "取消订阅功能暂时不可用，调度器未初始化"
            
            elif command == "/daily_report":
                # 手动获取每日报告
                if hasattr(self, 'message_processor') and self.message_processor.scheduler:
                    scheduler = self.message_processor.scheduler
                    result = await scheduler.send_manual_daily_report("synology_chat", user_id)
                    return f"📊 今日报告\n\n{result}\n\n💡 要订阅每日自动推送，请输入 /subscribe_daily"
                else:
                    return "每日报告功能暂时不可用，调度器未初始化"
            
            elif command == "/help":
                # 帮助信息
                return """【RSecretary 智能助理】

🎉 **默认功能**：
✅ 每日推送已自动开启！每天早上8:00推送

📅 **每日推送管理**：
/subscribe_daily - 查看订阅状态/重新订阅
/unsubscribe_daily - 取消每日推送
/daily_report - 立即查看今日报告

ℹ️ **其他命令**：
/help - 显示帮助信息

【每日推送内容】
🌅 早安问候语 - AI生成个性化问候
💰 昨日收支 - 收入、支出、净收入统计
📝 今日待办 - 今日到期和逾期任务提醒

【智能交互示例】
💬 "帮我记录今天花了50元买咖啡"
💬 "我今天有哪些任务？" 
💬 "发布代码这个任务已经完成了"
💬 "查看本月的收支情况"

【推送时间】每天早上 8:00 自动推送
默认所有用户都已开启，无需手动订阅！"""
            
            else:
                return f"❓ 未知命令: {command}\n\n输入 /help 查看可用命令列表"
                
        except Exception as e:
            logger.error(f"处理命令失败: {e}")
            return f"❌ 命令处理出错: {str(e)}\n\n请输入 /help 查看帮助信息"
    
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
            # 根据通知类型构建消息
            if notification_type == "task_completed":
                message = f"✅ 任务完成: {data.get('task_name', '未知任务')}"
            elif notification_type == "reminder":
                message = f"⏰ 提醒: {data.get('reminder_text', '您有一个提醒')}"
            elif notification_type == "error":
                message = f"❌ 错误: {data.get('error_message', '系统出现错误')}"
            else:
                message = f"📢 通知: {data.get('message', '您有一条新通知')}"
            
            return await self.send_message(user_id, message)
            
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            return False
    
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息（Synology Chat webhook模式下信息有限）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[Dict]: 用户信息
        """
        return {
            "id": user_id,
            "platform": self.platform,
            "username": f"user_{user_id}"
        } 