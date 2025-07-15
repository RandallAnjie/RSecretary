#!/usr/bin/env python3
"""
RSecretary 主应用程序
AI助理系统入口点
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import List, Optional
import click
from loguru import logger

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config.settings import settings
from src.bots.telegram_bot import TelegramBot
from src.bots.synology_chat_bot import SynologyChatBot
from src.core.message_processor import MessageProcessor
from src.core.scheduler import TaskScheduler


class RSecretaryApp:
    """RSecretary主应用程序"""
    
    def __init__(self):
        """初始化应用程序"""
        self.bots = []
        self.scheduler = None
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # 设置日志
        self._setup_logging()
        
        logger.info("RSecretary 应用程序初始化")
    
    def _setup_logging(self) -> None:
        """设置日志系统"""
        # 移除默认处理器
        logger.remove()
        
        # 控制台日志
        logger.add(
            sys.stdout,
            level=settings.system.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
        
        # 文件日志
        log_file = Path(settings.system.log_file)
        log_file.parent.mkdir(exist_ok=True)
        
        logger.add(
            log_file,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="30 days",
            compression="zip"
        )
    
    async def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            logger.info("开始初始化 RSecretary 组件...")
            
            # 验证配置
            if not settings.validate_config():
                logger.error("配置验证失败")
                return False
            
            # 初始化机器人
            await self._initialize_bots()
            
            # 初始化调度器
            await self._initialize_scheduler()
            
            logger.info("RSecretary 初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
    
    async def _initialize_bots(self) -> None:
        """初始化机器人"""
        enabled_bots = settings.get_enabled_bots()
        
        if not enabled_bots:
            logger.warning("未启用任何机器人平台")
            return
        
        for bot_name, bot_config in enabled_bots.items():
            try:
                if bot_name == "telegram" and bot_config.enabled:
                    bot = TelegramBot(bot_config.token)
                    if await bot.initialize():
                        self.bots.append(bot)
                        logger.info(f"Telegram机器人初始化成功")
                    else:
                        logger.error(f"Telegram机器人初始化失败")
                
                elif bot_name == "synology_chat" and bot_config.enabled:
                    bot = SynologyChatBot(bot_config.webhook_url, bot_config.token)
                    if await bot.initialize():
                        self.bots.append(bot)
                        logger.info(f"Synology Chat机器人初始化成功")
                    else:
                        logger.error(f"Synology Chat机器人初始化失败")
                
                # 其他机器人平台可以在这里添加
                # elif bot_name == "wechat" and bot_config.enabled:
                #     bot = WeChatBot()
                #     ...
                
            except Exception as e:
                logger.error(f"初始化 {bot_name} 机器人失败: {e}")
    
    async def _initialize_scheduler(self) -> None:
        """初始化定时任务调度器"""
        try:
            self.scheduler = TaskScheduler()
            
            # 将机器人实例添加到调度器
            for bot in self.bots:
                self.scheduler.add_bot(bot.platform.lower().replace(" ", "_"), bot)
                # 将调度器引用传递给机器人的消息处理器
                if hasattr(bot, 'message_processor'):
                    bot.message_processor.scheduler = self.scheduler
            
            # 添加默认的每日推送用户（可以从配置文件读取）
            # 这里可以根据实际需求配置默认用户
            # self.scheduler.add_daily_push_user("default_user", "synology_chat")
            
            logger.info("定时任务调度器初始化完成")
            
        except Exception as e:
            logger.error(f"初始化定时任务调度器失败: {e}")
    
    async def start(self) -> None:
        """启动应用程序"""
        try:
            if not self.bots:
                logger.error("没有可用的机器人，无法启动")
                return
            
            logger.info("启动 RSecretary 服务...")
            self.is_running = True
            
            # 启动定时任务调度器
            if self.scheduler:
                self.scheduler.start()
                logger.info("定时任务调度器已启动")
            
            # 设置信号处理器
            self._setup_signal_handlers()
            
            logger.info("🚀 RSecretary 启动成功！")
            logger.info(f"📊 活跃机器人: {len(self.bots)}")
            logger.info("按 Ctrl+C 停止服务")
            
            # 启动所有机器人任务（不等待它们完成）
            bot_tasks = []
            for bot in self.bots:
                task = asyncio.create_task(bot.start())
                bot_tasks.append(task)
                logger.info(f"启动 {bot.platform} 机器人: {bot.name}")
            
            # 只等待停止信号
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
            raise
    
    async def stop(self) -> None:
        """停止应用程序"""
        try:
            logger.info("正在停止 RSecretary 服务...")
            self.is_running = False
            
            # 停止定时任务调度器
            if self.scheduler:
                self.scheduler.stop()
                logger.info("定时任务调度器已停止")
            
            # 停止所有机器人
            for bot in self.bots:
                try:
                    await bot.stop()
                    logger.info(f"已停止 {bot.platform} 机器人")
                except Exception as e:
                    logger.error(f"停止机器人失败: {e}")
            
            # 设置停止事件
            self.shutdown_event.set()
            
            logger.info("✅ RSecretary 服务已停止")
            
        except Exception as e:
            logger.error(f"停止服务失败: {e}")
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"接收到信号 {signum}，开始优雅关闭...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("信号处理器设置完成")
    
    async def health_check(self) -> dict:
        """
        健康检查
        
        Returns:
            dict: 健康状态信息
        """
        try:
            health_status = {
                "service": "RSecretary",
                "status": "healthy" if self.is_running else "stopped",
                "bots": [],
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # 检查各个机器人状态
            for bot in self.bots:
                bot_health = await bot.health_check()
                health_status["bots"].append(bot_health)
            
            # 整体健康状态
            all_healthy = all(bot["healthy"] for bot in health_status["bots"])
            if not all_healthy:
                health_status["status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            return {
                "service": "RSecretary",
                "status": "error",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
    
    def get_stats(self) -> dict:
        """
        获取运行统计
        
        Returns:
            dict: 统计信息
        """
        stats = {
            "service": "RSecretary",
            "is_running": self.is_running,
            "bot_count": len(self.bots),
            "bots": []
        }
        
        for bot in self.bots:
            bot_stats = bot.get_stats()
            stats["bots"].append(bot_stats)
        
        return stats


# CLI接口
@click.group()
@click.version_option(version="1.0.0")
def cli():
    """RSecretary - 智能AI助理系统"""
    pass


@cli.command()
@click.option("--config", "-c", help="配置文件路径")
def start(config: Optional[str]):
    """启动RSecretary服务"""
    async def main():
        app = RSecretaryApp()
        
        if await app.initialize():
            try:
                await app.start()
            except KeyboardInterrupt:
                pass
            finally:
                await app.stop()
        else:
            sys.exit(1)
    
    asyncio.run(main())


@cli.command()
def check():
    """检查配置和依赖"""
    click.echo("🔍 检查RSecretary配置...")
    
    # 检查配置
    try:
        if settings.validate_config():
            click.echo("✅ 配置验证通过")
        else:
            click.echo("❌ 配置验证失败")
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 配置检查失败: {e}")
        sys.exit(1)
    
    # 检查启用的机器人
    enabled_bots = settings.get_enabled_bots()
    if enabled_bots:
        click.echo(f"📱 启用的机器人平台: {', '.join(enabled_bots.keys())}")
    else:
        click.echo("⚠️  未启用任何机器人平台")
    
    click.echo("🎉 检查完成！")


@cli.command()
def test():
    """测试系统连接"""
    async def test_connections():
        click.echo("🧪 测试系统连接...")
        
        try:
            # 测试AI连接
            from src.ai.gemini_client import GeminiClient
            gemini_client = GeminiClient()
            
            click.echo("测试Gemini AI连接...", nl=False)
            if await gemini_client.test_connection():
                click.echo(" ✅")
            else:
                click.echo(" ❌")
            
            # 测试Notion连接
            from src.storage.notion_client import NotionClient
            notion_client = NotionClient()
            
            click.echo("测试Notion连接...", nl=False)
            if await notion_client.test_connection():
                click.echo(" ✅")
            else:
                click.echo(" ❌")
            
            # 测试机器人连接
            enabled_bots = settings.get_enabled_bots()
            for bot_name in enabled_bots:
                if bot_name == "telegram":
                    try:
                        from src.bots.telegram_bot import TelegramBot
                        bot = TelegramBot()
                        click.echo(f"测试{bot_name}机器人连接...", nl=False)
                        if await bot.initialize():
                            click.echo(" ✅")
                            await bot.stop()
                        else:
                            click.echo(" ❌")
                    except Exception as e:
                        click.echo(f" ❌ ({e})")
            
            click.echo("🎉 连接测试完成！")
            
        except Exception as e:
            click.echo(f"❌ 测试失败: {e}")
            sys.exit(1)
    
    asyncio.run(test_connections())


@cli.command()
@click.option("--bot", help="指定机器人类型")
def status(bot: Optional[str]):
    """查看服务状态"""
    # 这里可以实现状态查询逻辑
    # 例如连接到运行中的服务获取状态
    click.echo("📊 RSecretary 状态查询")
    click.echo("此功能需要连接到运行中的服务实例")


if __name__ == "__main__":
    cli() 