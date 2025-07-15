# 使用Python 3.11作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p logs config

# 设置权限
RUN chmod +x main.py

# 创建启动脚本
RUN echo '#!/bin/bash\n\
set -e\n\
echo "🚀 RSecretary 容器启动中..."\n\
echo "📅 时间: $(date)"\n\
echo "📋 检查配置和依赖..."\n\
\n\
# 运行配置检查\n\
if python main.py check; then\n\
    echo "✅ 配置检查通过！"\n\
    echo "🎯 启动 RSecretary 服务..."\n\
    exec python main.py start\n\
else\n\
    echo ""\n\
    echo "❌ 配置检查失败！"\n\
    echo "📝 请确保以下环境变量已正确设置："\n\
    echo "   🔑 GEMINI_API_KEY - Gemini AI API密钥"\n\
    echo "   📄 NOTION_TOKEN - Notion集成令牌"\n\
    echo "   🤖 机器人Token (至少一个):"\n\
    echo "      • TELEGRAM_BOT_TOKEN - Telegram机器人令牌"\n\
    echo "      • SYNOLOGY_CHAT_WEBHOOK_URL - Synology Chat webhook"\n\
    echo ""\n\
    echo "🐳 Docker运行示例："\n\
    echo "docker run -e GEMINI_API_KEY=your_key -e NOTION_TOKEN=your_token ranjie/rsecretary"\n\
    echo ""\n\
    echo "📖 详细文档: https://github.com/your-repo/RSecretary"\n\
    echo "🔧 使用 docker logs <container_name> 查看详细错误"\n\
    echo ""\n\
    exit 1\n\
fi' > /app/start.sh && chmod +x /app/start.sh

# 暴露端口（如果有web服务）
EXPOSE 8080

# 设置健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python main.py status || exit 1

# 启动应用
CMD ["/app/start.sh"]