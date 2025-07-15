"""
定时任务调度器
实现每日自动推送和其他定时任务
"""

import asyncio
import schedule
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Callable
from loguru import logger

from ..ai.gemini_client import GeminiClient
from ..tasks.accounting import AccountingTask
from ..tasks.todo import TodoTask


class TaskScheduler:
    """
    定时任务调度器
    """
    
    def __init__(self):
        """初始化任务调度器"""
        self.is_running = False
        self.schedule_thread = None
        self.bots = {}  # 存储机器人实例
        self.daily_push_users = set()  # 订阅每日推送的用户
        
        # 初始化任务组件
        self.gemini_client = GeminiClient()
        self.accounting_task = AccountingTask()
        self.todo_task = TodoTask()
        
        logger.info("定时任务调度器初始化完成")
    
    def add_bot(self, platform: str, bot_instance):
        """
        添加机器人实例
        
        Args:
            platform: 平台名称
            bot_instance: 机器人实例
        """
        self.bots[platform] = bot_instance
        logger.info(f"添加机器人实例: {platform}")
    
    def add_daily_push_user(self, user_id: str, platform: str = "synology_chat"):
        """
        添加每日推送订阅用户
        
        Args:
            user_id: 用户ID
            platform: 平台名称
        """
        self.daily_push_users.add(f"{platform}:{user_id}")
        logger.info(f"添加每日推送用户: {platform}:{user_id}")
    
    def remove_daily_push_user(self, user_id: str, platform: str = "synology_chat"):
        """
        移除每日推送订阅用户
        
        Args:
            user_id: 用户ID
            platform: 平台名称
        """
        user_key = f"{platform}:{user_id}"
        self.daily_push_users.discard(user_key)
        logger.info(f"移除每日推送用户: {platform}:{user_id}")
    
    def setup_daily_tasks(self):
        """设置每日定时任务"""
        # 每天早上8点发送每日推送
        schedule.every().day.at("08:00").do(self._run_async_task, self._daily_morning_push)
        
        # 每天晚上10点发送晚安和明天预览（可选）
        # schedule.every().day.at("22:00").do(self._run_async_task, self._daily_evening_push)
        
        logger.info("每日定时任务设置完成")
    
    def start(self):
        """启动定时任务调度器"""
        if self.is_running:
            logger.warning("定时任务调度器已在运行")
            return
        
        self.setup_daily_tasks()
        self.is_running = True
        
        # 在单独线程中运行调度器
        self.schedule_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.schedule_thread.start()
        
        logger.info("定时任务调度器启动成功")
    
    def stop(self):
        """停止定时任务调度器"""
        self.is_running = False
        schedule.clear()
        logger.info("定时任务调度器已停止")
    
    def _run_scheduler(self):
        """运行调度器循环"""
        while self.is_running:
            schedule.run_pending()
            threading.Event().wait(60)  # 每分钟检查一次
    
    def _run_async_task(self, coro):
        """在新的事件循环中运行异步任务"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro())
            loop.close()
        except Exception as e:
            logger.error(f"执行异步任务失败: {e}")
    
    async def _daily_morning_push(self):
        """每日早晨推送"""
        try:
            logger.info("开始执行每日早晨推送")
            
            for user_key in self.daily_push_users:
                try:
                    platform, user_id = user_key.split(":", 1)
                    await self._send_daily_report(platform, user_id)
                except Exception as e:
                    logger.error(f"发送每日推送失败 {user_key}: {e}")
            
            logger.info("每日早晨推送完成")
            
        except Exception as e:
            logger.error(f"每日早晨推送执行失败: {e}")
    
    async def _send_daily_report(self, platform: str, user_id: str):
        """
        发送每日报告给特定用户
        
        Args:
            platform: 平台名称
            user_id: 用户ID
        """
        try:
            # 获取机器人实例
            bot = self.bots.get(platform)
            if not bot:
                logger.error(f"未找到平台 {platform} 的机器人实例")
                return
            
            # 生成每日报告内容
            report_content = await self._generate_daily_report(user_id)
            
            # 发送报告
            success = await bot.send_message(user_id, report_content)
            
            if success:
                logger.info(f"每日报告发送成功: {platform}:{user_id}")
            else:
                logger.error(f"每日报告发送失败: {platform}:{user_id}")
                
        except Exception as e:
            logger.error(f"发送每日报告失败: {e}")
    
    async def _generate_daily_report(self, user_id: str) -> str:
        """
        生成每日报告内容
        
        Args:
            user_id: 用户ID
            
        Returns:
            str: 每日报告内容
        """
        try:
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
            weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]
            
            # 生成早安问候
            greeting = await self._generate_morning_greeting()
            
            # 获取昨日收支情况
            yesterday_financial = await self._get_yesterday_financial_summary(yesterday)
            
            # 获取今日待办事项
            today_todos = await self._get_today_todos(today)
            
            # 组装报告
            report_parts = [
                f"【早安】{greeting}",
                f"今天是 {today} {weekday}",
                "",
                "【昨日收支】",
                yesterday_financial,
                "",
                "【今日待办】", 
                today_todos,
                "",
                "祝您今天工作顺利，心情愉快！"
            ]
            
            return "\n".join(report_parts)
            
        except Exception as e:
            logger.error(f"生成每日报告失败: {e}")
            return f"早安！今天是 {datetime.now().strftime('%Y-%m-%d')}，系统生成报告时出现问题，请稍后查看详细信息。"
    
    async def _generate_morning_greeting(self) -> str:
        """生成个性化早安问候"""
        try:
            prompt = """
请生成一条温馨的早安问候语，要求：
1. 亲切自然，不要过于正式
2. 可以包含对新一天的美好祝愿
3. 控制在50字以内
4. 体现AI助理的贴心和温暖

示例风格：
- "早安！新的一天开始了，愿您精神饱满，收获满满！"
- "早上好！希望今天的每一刻都充满阳光和好心情～"
"""
            
            response = await asyncio.to_thread(
                self.gemini_client.model.generate_content,
                prompt
            )
            
            greeting = response.text.strip()
            # 移除可能的引号
            greeting = greeting.strip('"').strip("'")
            
            return greeting
            
        except Exception as e:
            logger.error(f"生成早安问候失败: {e}")
            return "早安！新的一天开始了，愿您工作顺利，心情愉快！"
    
    async def _get_yesterday_financial_summary(self, yesterday_date: str) -> str:
        """
        获取昨日财务摘要
        
        Args:
            yesterday_date: 昨日日期 (YYYY-MM-DD)
            
        Returns:
            str: 财务摘要文本
        """
        try:
            # 查询昨日的记账记录
            filters = {"日期": yesterday_date}
            result = await self.accounting_task.query(filters)
            
            if not result.success:
                return "昨日记账数据获取失败"
            
            records = result.data.get("records", [])
            
            if not records:
                return "昨日暂无收支记录"
            
            # 统计收支
            income = 0.0
            expense = 0.0
            
            for record in records:
                amount = float(record.get("金额", 0))
                record_type = record.get("类型", "")
                
                if record_type == "收入":
                    income += amount
                elif record_type == "支出":
                    expense += amount
            
            # 格式化输出
            summary_parts = []
            
            if income > 0:
                summary_parts.append(f"收入：{income:.2f}元")
            
            if expense > 0:
                summary_parts.append(f"支出：{expense:.2f}元")
            
            if income > 0 or expense > 0:
                net = income - expense
                if net > 0:
                    summary_parts.append(f"净收入：{net:.2f}元")
                elif net < 0:
                    summary_parts.append(f"净支出：{abs(net):.2f}元")
                else:
                    summary_parts.append("收支平衡")
                
                summary_parts.append(f"共 {len(records)} 笔记录")
            
            return " | ".join(summary_parts) if summary_parts else "昨日暂无收支记录"
            
        except Exception as e:
            logger.error(f"获取昨日财务摘要失败: {e}")
            return "昨日收支情况获取失败"
    
    async def _get_today_todos(self, today_date: str) -> str:
        """
        获取今日待办事项
        
        Args:
            today_date: 今日日期 (YYYY-MM-DD)
            
        Returns:
            str: 待办事项文本
        """
        try:
            # 查询今日的待办事项（截止日期为今天或之前的未完成任务）
            all_result = await self.todo_task.query({})
            
            if not all_result.success:
                return "今日待办事项获取失败"
            
            all_todos = all_result.data.get("records", [])
            
            # 筛选今日相关的待办事项
            today_todos = []
            overdue_todos = []
            
            for todo in all_todos:
                status = todo.get("状态", "")
                due_date = todo.get("截止日期", "")
                
                # 跳过已完成和已取消的任务
                if status in ["已完成", "已取消"]:
                    continue
                
                # 没有截止日期的任务也包含在内
                if not due_date:
                    today_todos.append(todo)
                    continue
                
                # 比较日期
                if due_date == today_date:
                    today_todos.append(todo)
                elif due_date < today_date:
                    overdue_todos.append(todo)
            
            # 格式化输出
            todo_parts = []
            
            if overdue_todos:
                todo_parts.append("【逾期任务】")
                for todo in overdue_todos[:3]:  # 最多显示3个逾期任务
                    title = todo.get("标题", "")
                    priority = todo.get("优先级", "")
                    due_date = todo.get("截止日期", "")
                    priority_text = {"高": "【高】", "中": "【中】", "低": "【低】"}.get(priority, "")
                    todo_parts.append(f"- {title} {priority_text} (逾期: {due_date})")
                
                if len(overdue_todos) > 3:
                    todo_parts.append(f"... 还有 {len(overdue_todos) - 3} 个逾期任务")
                todo_parts.append("")
            
            if today_todos:
                todo_parts.append("【今日任务】")
                for todo in today_todos[:5]:  # 最多显示5个今日任务
                    title = todo.get("标题", "")
                    priority = todo.get("优先级", "")
                    status = todo.get("状态", "")
                    priority_text = {"高": "【高】", "中": "【中】", "低": "【低】"}.get(priority, "")
                    status_text = {"进行中": "【进行中】", "待完成": "【待完成】"}.get(status, "")
                    todo_parts.append(f"- {title} {priority_text} {status_text}")
                
                if len(today_todos) > 5:
                    todo_parts.append(f"... 还有 {len(today_todos) - 5} 个任务")
            else:
                todo_parts.append("今日暂无特定截止日期的任务")
            
            return "\n".join(todo_parts) if todo_parts else "今日暂无待办事项"
            
        except Exception as e:
            logger.error(f"获取今日待办事项失败: {e}")
            return "今日待办事项获取失败"
    
    # 手动触发功能（用于测试和按需推送）
    async def send_manual_daily_report(self, platform: str, user_id: str) -> str:
        """
        手动发送每日报告
        
        Args:
            platform: 平台名称
            user_id: 用户ID
            
        Returns:
            str: 每日报告内容
        """
        try:
            # 直接生成并返回报告内容，而不是发送消息
            report_content = await self._generate_daily_report(user_id)
            return report_content
        except Exception as e:
            logger.error(f"手动生成每日报告失败: {e}")
            return f"生成报告失败: {str(e)}"
    
    def get_daily_push_users(self) -> set:
        """获取当前订阅每日推送的用户列表"""
        return self.daily_push_users.copy()
    
    def is_user_subscribed(self, user_id: str, platform: str = "synology_chat") -> bool:
        """
        检查用户是否已订阅每日推送
        
        Args:
            user_id: 用户ID  
            platform: 平台名称
            
        Returns:
            bool: 是否已订阅
        """
        user_key = f"{platform}:{user_id}"
        return user_key in self.daily_push_users
    
    async def test_daily_push(self) -> str:
        """
        测试每日推送功能（立即执行一次）
        
        Returns:
            str: 测试结果
        """
        try:
            logger.info("开始测试每日推送功能")
            
            if not self.daily_push_users:
                return "⚠️ 暂无订阅用户，无法测试推送功能"
            
            success_count = 0
            total_count = len(self.daily_push_users)
            
            for user_key in self.daily_push_users:
                try:
                    platform, user_id = user_key.split(":", 1)
                    await self._send_daily_report(platform, user_id)
                    success_count += 1
                    logger.info(f"测试推送成功: {user_key}")
                except Exception as e:
                    logger.error(f"测试推送失败 {user_key}: {e}")
            
            result = f"✅ 测试完成！成功推送 {success_count}/{total_count} 个用户"
            logger.info(result)
            return result
            
        except Exception as e:
            error_msg = f"❌ 测试推送功能失败: {e}"
            logger.error(error_msg)
            return error_msg 