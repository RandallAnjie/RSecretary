"""
配置管理模块
处理YAML配置文件和环境变量的加载
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from loguru import logger


class GeminiConfig(BaseModel):
    """Gemini AI配置"""
    api_key: str = Field(default="", description="Gemini API密钥")
    model: str = Field(default="gemini-pro", description="使用的模型")
    temperature: float = Field(default=0.7, description="创造性参数")
    max_tokens: int = Field(default=1000, description="最大输出令牌数")


class NotionConfig(BaseModel):
    """Notion配置"""
    token: str = Field(default="", description="Notion集成令牌")
    databases: Dict[str, str] = Field(default_factory=dict, description="数据库ID映射")


class BotConfig(BaseModel):
    """机器人配置"""
    enabled: bool = Field(default=False, description="是否启用")


class TelegramBotConfig(BotConfig):
    """Telegram机器人配置"""
    token: str = Field(default="", description="机器人令牌")


class WeChatBotConfig(BotConfig):
    """微信机器人配置"""
    auto_login: bool = Field(default=False, description="自动登录")


class QQBotConfig(BotConfig):
    """QQ机器人配置"""
    qq_number: str = Field(default="", description="QQ号")
    password: str = Field(default="", description="QQ密码")


class FeishuBotConfig(BotConfig):
    """飞书机器人配置"""
    app_id: str = Field(default="", description="应用ID")
    app_secret: str = Field(default="", description="应用密钥")


class SynologyChatBotConfig(BotConfig):
    """Synology Chat机器人配置"""
    webhook_url: str = Field(default="", description="Webhook URL")
    token: str = Field(default="", description="访问令牌")
    verify_ssl: bool = Field(default=True, description="是否验证SSL证书")
    use_ngrok: bool = Field(default=False, description="是否使用Ngrok进行调试")
    ngrok_auth_token: str = Field(default="", description="Ngrok认证令牌")
    ngrok_domain: str = Field(default="", description="Ngrok自定义域名")
    local_port: int = Field(default=8844, description="本地监听端口")


class BotsConfig(BaseModel):
    """所有机器人配置"""
    telegram: TelegramBotConfig = Field(default_factory=TelegramBotConfig)
    wechat: WeChatBotConfig = Field(default_factory=WeChatBotConfig)
    qq: QQBotConfig = Field(default_factory=QQBotConfig)
    feishu: FeishuBotConfig = Field(default_factory=FeishuBotConfig)
    synology_chat: SynologyChatBotConfig = Field(default_factory=SynologyChatBotConfig)


class SystemConfig(BaseModel):
    """系统配置"""
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: str = Field(default="logs/rsecretary.log", description="日志文件路径")
    timezone: str = Field(default="Asia/Shanghai", description="时区")


class TasksConfig(BaseModel):
    """任务配置"""
    default_currency: str = Field(default="CNY", description="默认货币")
    auto_save: bool = Field(default=True, description="自动保存")
    backup_interval: int = Field(default=3600, description="备份间隔（秒）")


class Settings:
    """
    应用配置管理器
    支持YAML配置文件和环境变量
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/config.yaml"
        self.project_root = Path(__file__).parent.parent.parent
        
        # 加载环境变量
        load_dotenv()
        
        # 初始化配置
        self.gemini = GeminiConfig()
        self.notion = NotionConfig()
        self.bots = BotsConfig()
        self.system = SystemConfig()
        self.tasks = TasksConfig()
        
        # 加载配置
        self._load_config()
        self._load_env_overrides()
        
        logger.info("配置加载完成")
    
    def _load_config(self) -> None:
        """从YAML文件加载配置"""
        config_file = self.project_root / self.config_path
        
        if not config_file.exists():
            logger.warning(f"配置文件不存在: {config_file}")
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                logger.warning("配置文件为空")
                return
            
            # 加载各模块配置
            if 'gemini' in config_data:
                self.gemini = GeminiConfig(**config_data['gemini'])
            
            if 'notion' in config_data:
                self.notion = NotionConfig(**config_data['notion'])
            
            if 'bots' in config_data:
                bots_data = config_data['bots']
                self.bots = BotsConfig(
                    telegram=TelegramBotConfig(**bots_data.get('telegram', {})),
                    wechat=WeChatBotConfig(**bots_data.get('wechat', {})),
                    qq=QQBotConfig(**bots_data.get('qq', {})),
                    feishu=FeishuBotConfig(**bots_data.get('feishu', {})),
                    synology_chat=SynologyChatBotConfig(**bots_data.get('synology_chat', {}))
                )
            
            if 'system' in config_data:
                self.system = SystemConfig(**config_data['system'])
            
            if 'tasks' in config_data:
                self.tasks = TasksConfig(**config_data['tasks'])
                
            logger.info("从YAML文件加载配置成功")
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    
    def _load_env_overrides(self) -> None:
        """从环境变量加载配置覆盖"""
        # Gemini配置
        if api_key := os.getenv('GEMINI_API_KEY'):
            self.gemini.api_key = api_key
        
        # Notion配置
        if token := os.getenv('NOTION_TOKEN'):
            self.notion.token = token
        
        # Telegram机器人配置
        if telegram_token := os.getenv('TELEGRAM_BOT_TOKEN'):
            self.bots.telegram.token = telegram_token
            if telegram_token:
                self.bots.telegram.enabled = True
        
        # 飞书配置
        if feishu_app_id := os.getenv('FEISHU_APP_ID'):
            self.bots.feishu.app_id = feishu_app_id
        if feishu_app_secret := os.getenv('FEISHU_APP_SECRET'):
            self.bots.feishu.app_secret = feishu_app_secret
        if self.bots.feishu.app_id and self.bots.feishu.app_secret:
            self.bots.feishu.enabled = True
        
        # Synology Chat配置
        if webhook_url := os.getenv('SYNOLOGY_WEBHOOK_URL'):
            self.bots.synology_chat.webhook_url = webhook_url
        if synology_token := os.getenv('SYNOLOGY_TOKEN'):
            self.bots.synology_chat.token = synology_token
        if self.bots.synology_chat.webhook_url:
            self.bots.synology_chat.enabled = True
        
        # 系统配置
        if log_level := os.getenv('LOG_LEVEL'):
            self.system.log_level = log_level
        if timezone := os.getenv('TIMEZONE'):
            self.system.timezone = timezone
        
        logger.info("环境变量覆盖配置完成")
    
    def get_enabled_bots(self) -> Dict[str, BotConfig]:
        """获取已启用的机器人配置"""
        enabled_bots = {}
        
        if self.bots.telegram.enabled:
            enabled_bots['telegram'] = self.bots.telegram
        if self.bots.wechat.enabled:
            enabled_bots['wechat'] = self.bots.wechat
        if self.bots.qq.enabled:
            enabled_bots['qq'] = self.bots.qq
        if self.bots.feishu.enabled:
            enabled_bots['feishu'] = self.bots.feishu
        if self.bots.synology_chat.enabled:
            enabled_bots['synology_chat'] = self.bots.synology_chat
        
        return enabled_bots
    
    def validate_config(self) -> bool:
        """验证配置的完整性"""
        errors = []
        
        # 检查必需的API密钥
        if not self.gemini.api_key:
            errors.append("Gemini API密钥未配置")
        
        if not self.notion.token:
            errors.append("Notion令牌未配置")
        
        # 检查是否至少启用了一个机器人
        if not self.get_enabled_bots():
            errors.append("未启用任何机器人平台")
        
        # 检查Notion数据库配置
        required_databases = ['accounting', 'subscriptions', 'todos']
        for db in required_databases:
            if db not in self.notion.databases or not self.notion.databases[db]:
                errors.append(f"Notion数据库 '{db}' 未配置")
        
        if errors:
            for error in errors:
                logger.error(f"配置验证失败: {error}")
            return False
        
        logger.info("配置验证通过")
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式"""
        return {
            'gemini': self.gemini.model_dump(),
            'notion': self.notion.model_dump(),
            'bots': self.bots.model_dump(),
            'system': self.system.model_dump(),
            'tasks': self.tasks.model_dump()
        }


# 全局配置实例
settings = Settings() 