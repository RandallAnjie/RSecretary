# RSecretary - 智能AI助理系统

🤖 一个支持多平台机器人的智能生活助理，基于 Gemini AI 和 Notion 数据库，帮您智能管理记账、订阅和待办事项。

## 核心功能

### 📅 每日自动推送
- **推送时间**: 每天早上 8:00
- **推送内容**: 
  - 🌅 AI生成个性化早安问候
  - 💰 昨日收支统计（收入/支出/净收入）  
  - 📝 今日待办和逾期任务提醒

### 🤖 智能对话
- 基于 Google Gemini AI 的自然语言理解
- 支持上下文对话，理解您的真实意图
- 无需复杂命令，用自然语言即可完成所有操作

### 📝 记账管理
- 智能识别收入和支出信息
- 自动分类和标签管理
- 支持多种货币和账户
- 提供详细的财务统计和分析

### 💰 订阅管理
- 记录和管理各种订阅服务
- 智能提醒续费日期
- 计算月度和年度订阅成本
- 支持订阅状态管理

### ✅ 待办事项
- 智能创建和管理任务
- 支持优先级和截止日期
- 自动提醒和任务跟踪
- 灵活的任务分类系统

### 🤖 多平台支持
- **Telegram** - 支持
- **Synology Chat** - 计划支持

### 📊 数据存储
- 使用 Notion 作为数据库
- 数据安全可靠，支持备份
- 可视化数据展示
- 支持数据导出和分析

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Gemini API 密钥
- Notion 集成令牌
- 至少一个机器人平台的访问权限

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/your-username/RSecretary.git
cd RSecretary
```

2. **创建虚拟环境**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置系统**
```bash
# 复制配置模板
cp config/config.yaml.example config/config.yaml

# 编辑配置文件
vim config/config.yaml
```

### 📋 配置指南

#### 1. Gemini AI 配置

1. 访问 [Google AI Studio](https://makersuite.google.com/)
2. 创建 API 密钥
3. 在配置文件中填入：

```yaml
gemini:
  api_key: "your_gemini_api_key_here"
  model: "gemini-pro"
  temperature: 0.7
  max_tokens: 1000
```

#### 2. Notion 配置

1. 访问 [Notion Integrations](https://www.notion.so/my-integrations)
2. 创建新的集成并获取令牌
3. 创建以下数据库并获取ID, [数据库模板](https://www.notion.so/randallanjie/RSecretaryShare-231a3930a20380fb9816e2b155173297?source=copy_link)
   - 记账数据库
   - 订阅数据库  
   - 待办事项数据库
4. 配置数据库权限，确保集成可以读写

> 如何获取数据库ID:
> 在 Notion 中打开数据库，复制 URL 中的最后一部分（例如 `https://www.notion.so/yourworkspace/DatabaseName-1234567890abcdef1234567890abcdef?v=123456789`，ID 为 `1234567890abcdef1234567890abcdef`）

```yaml
notion:
  token: "your_notion_integration_token_here"
  databases:
    accounting: "your_accounting_database_id"
    subscriptions: "your_subscriptions_database_id"
    todos: "your_todos_database_id"
```

#### 3. Telegram 机器人配置

1. 与 [@BotFather](https://t.me/BotFather) 对话创建机器人
2. 获取机器人令牌
3. 在配置文件中启用：

```yaml
bots:
  telegram:
    enabled: true
    token: "your_telegram_bot_token"
```

### 🔧 运行系统

#### 检查配置
```bash
python main.py check
```

#### 测试连接
```bash
python main.py test
```

#### 启动服务
```bash
python main.py start
```

## 📱 使用指南

### 基础对话

与机器人的对话完全是自然语言，例如：

#### 记账功能
```
用户: 今天午餐花了30元
机器人: 好的，我已经记录了您的支出：午餐 30元

用户: 本月花了多少钱？
机器人: 您本月总支出：1,250元，收入：5,000元，净额：3,750元
```

#### 订阅管理
```
用户: 我订阅了Netflix，每月50元
机器人: 已记录Netflix订阅，月费50元，下次扣费时间：2024年1月15日

用户: 我的订阅有哪些？
机器人: 您当前的活跃订阅：
1. Netflix - 50元/月
2. Spotify - 15元/月
总月度成本：65元
```

#### 待办事项
```
用户: 提醒我明天下午3点开会
机器人: 已创建待办事项：明天下午3点开会，截止时间：2024年1月15日 15:00

用户: 今天有什么任务？
机器人: 您今天的待办事项：
1. 下午3点开会 (高优先级)
2. 完成项目报告 (中优先级)
```


## 使用方法

### 💬 与机器人对话
发送消息给机器人，支持自然语言交互：
- "帮我记录一下今天花了50元买咖啡"
- "我今天有哪些任务"
- "发布代码这个任务已经完成了"

### 📅 每日推送管理
使用以下命令管理每日推送：

```
/daily_report       # 立即查看今日报告
```

**每日推送示例**:
```
【早安】早上好！希望今天的每一刻都充满阳光和好心情～
今天是 2025-07-15 周二

【昨日收支】
收入：1200.00元 | 支出：350.00元 | 净收入：850.00元 | 共 5 笔记录

【今日待办】
【逾期任务】
- 项目报告 【高】 (逾期: 2025-07-14)

【今日任务】  
- 开会 【高】 【待完成】
- 发布代码 【中】 【进行中】
- 买奶茶 【低】 【待完成】

祝您今天工作顺利，心情愉快！
```

### 🔧 任务管理

## 🏗️ 项目架构

```
RSecretary/
├── src/
│   ├── ai/                 # AI模块 (Gemini集成)
│   ├── storage/            # 存储模块 (Notion集成)
│   ├── tasks/              # 任务管理 (记账、订阅、待办)
│   ├── core/               # 核心模块 (消息处理、任务分发)
│   ├── bots/               # 机器人模块 (多平台支持)
│   └── config/             # 配置管理
├── config/                 # 配置文件
├── logs/                   # 日志文件
├── tests/                  # 测试文件
├── requirements.txt        # 依赖列表
├── main.py                 # 主程序入口
└── README.md              # 项目文档
```

### 核心组件

- **MessageProcessor**: 智能消息处理器，负责理解用户意图
- **TaskDispatcher**: 任务分发器，管理各种任务的执行
- **GeminiClient**: Gemini AI客户端，提供自然语言理解
- **NotionClient**: Notion API客户端，处理数据存储
- **BaseBot**: 机器人基类，定义统一的机器人接口

## 🛠️ 开发指南

### 添加新的机器人平台

1. 继承 `BaseBot` 类
2. 实现必要的抽象方法
3. 在主应用中注册机器人
4. 更新配置文件模板

示例：
```python
from src.bots.base_bot import BaseBot

class NewPlatformBot(BaseBot):
    def __init__(self):
        super().__init__("BotName", "PlatformName")
    
    async def initialize(self) -> bool:
        # 初始化连接
        pass
    
    async def start(self) -> None:
        # 启动机器人
        pass
    
    # ... 实现其他必要方法
```

### 添加新的任务类型

1. 继承 `BaseTask` 类
2. 实现任务逻辑
3. 在 `TaskFactory` 中注册
4. 更新AI提示词以识别新任务

### 自定义配置

系统支持灵活的配置管理：

```python
from src.config.settings import settings

# 访问配置
api_key = settings.gemini.api_key
database_id = settings.notion.databases['accounting']

# 验证配置
if settings.validate_config():
    print("配置有效")
```

## 🔍 故障排除

### 常见问题

#### 1. Gemini API 错误
```
错误: Gemini API密钥未配置
解决: 检查配置文件中的 gemini.api_key 设置
```

#### 2. Notion 连接失败
```
错误: Notion令牌未配置
解决: 
1. 确认集成令牌正确
2. 检查数据库ID是否正确
3. 验证集成是否有数据库访问权限
```

#### 3. 机器人无响应
```
解决:
1. 检查机器人令牌是否正确
2. 确认网络连接正常
3. 查看日志文件获取详细错误信息
```

### 日志分析

系统日志保存在 `logs/rsecretary.log`：

```bash
# 查看最新日志
tail -f logs/rsecretary.log

# 搜索错误
grep "ERROR" logs/rsecretary.log
```

## 🤝 贡献指南

我们欢迎任何形式的贡献！

### 贡献方式

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 开发规范

- 遵循 PEP 8 代码风格
- 添加必要的文档字符串
- 编写单元测试
- 提交前运行代码检查

```bash
# 代码格式化
black src/

# 代码检查
flake8 src/
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。
