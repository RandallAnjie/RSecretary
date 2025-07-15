"""
消息处理器
智能解析用户消息并协调AI和任务系统
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from ..ai.gemini_client import GeminiClient
from ..tasks.base_task import TaskFactory
from .task_dispatcher import TaskDispatcher


class MessageProcessor:
    """
    消息处理器
    负责智能解析用户消息、任务识别和执行协调
    """
    
    def __init__(self, scheduler=None):
        """初始化消息处理器"""
        self.gemini_client = GeminiClient()
        self.task_dispatcher = TaskDispatcher()
        self.scheduler = scheduler  # 定时任务调度器引用
        
        # 注册所有任务类型
        self._register_tasks()
        
        # 对话上下文存储（简单实现，生产环境建议使用Redis等）
        self.conversation_contexts = {}
        
        logger.info("消息处理器初始化完成")
    
    def _register_tasks(self) -> None:
        """注册所有任务类型到工厂"""
        from ..tasks.accounting import AccountingTask
        from ..tasks.subscription import SubscriptionTask
        from ..tasks.todo import TodoTask
        
        TaskFactory.register_task("accounting", AccountingTask)
        TaskFactory.register_task("subscription", SubscriptionTask)
        TaskFactory.register_task("todo", TodoTask)
        
        logger.info("任务类型注册完成")
    
    async def process_message(
        self, 
        message: str, 
        user_id: str, 
        platform: str = "unknown"
    ) -> str:
        """
        处理用户消息
        
        Args:
            message: 用户消息
            user_id: 用户ID
            platform: 平台名称
            
        Returns:
            str: 处理结果回复
        """
        try:
            logger.info(f"处理来自 {platform} 用户 {user_id} 的消息: {message[:100]}...")
            
            # 获取对话上下文
            context = self._get_conversation_context(user_id)
            
            # 使用AI分析消息意图
            analysis = await self.gemini_client.analyze_task(message)
            task_type = analysis.get("task_type", "chat")
            confidence = analysis.get("confidence", 0.0)
            
            logger.info(f"AI分析结果: 任务类型={task_type}, 置信度={confidence}")
            
            # 更新对话上下文
            self._update_conversation_context(user_id, message, analysis)
            
            # 根据任务类型处理
            if task_type == "chat" or confidence < 0.6:
                # 普通聊天
                return await self._handle_chat(message, context)
            
            elif task_type in ["accounting", "subscription", "todo"]:
                # 任务处理
                return await self._handle_task(task_type, message, analysis, user_id)
            
            elif task_type == "query":
                # 查询处理
                return await self._handle_query(message, analysis, user_id)
            
            elif task_type == "delete":
                # 删除处理
                return await self._handle_delete(message, analysis, user_id)
            
            elif task_type == "update":
                # 更新处理
                return await self._handle_update(message, analysis, user_id)
            
            else:
                # 未知类型，回退到聊天
                return await self._handle_chat(message, context)
                
        except Exception as e:
            logger.error(f"消息处理失败: {e}")
            return "抱歉，我现在无法处理您的消息，请稍后再试。"
    
    async def _handle_chat(self, message: str, context: Optional[str]) -> str:
        """
        处理普通聊天
        
        Args:
            message: 用户消息
            context: 对话上下文
            
        Returns:
            str: AI回复
        """
        try:
            # 检查是否是特殊命令
            message_lower = message.lower().strip()
            
            # 每日推送订阅管理
            if self.scheduler and "每日推送" in message:
                if "订阅" in message or "开启" in message:
                    return "要订阅每日推送，请使用命令：/subscribe_daily"
                elif "取消" in message or "关闭" in message:
                    return "要取消每日推送，请使用命令：/unsubscribe_daily"
                elif "手动" in message or "立即" in message:
                    return "要手动获取今日报告，请使用命令：/daily_report"
            
            # 普通AI聊天
            reply = await self.gemini_client.chat(message, context)
            return reply
        except Exception as e:
            logger.error(f"聊天处理失败: {e}")
            return "我现在有点困惑，能再说一遍吗？"
    
    async def _handle_task(
        self, 
        task_type: str, 
        message: str, 
        analysis: Dict[str, Any],
        user_id: str
    ) -> str:
        """
        处理任务执行
        
        Args:
            task_type: 任务类型
            message: 原始消息
            analysis: AI分析结果
            user_id: 用户ID
            
        Returns:
            str: 执行结果回复
        """
        try:
            # 总是使用专门的数据提取方法，确保数据格式正确
            if task_type == "accounting":
                extracted_data = await self.gemini_client.extract_accounting_data(message)
            elif task_type == "subscription":
                extracted_data = await self.gemini_client.extract_subscription_data(message)
            elif task_type == "todo":
                extracted_data = await self.gemini_client.extract_todo_data(message)
            else:
                # 如果是其他类型，尝试从分析结果中获取
                extracted_data = analysis.get("extracted_data", {})
            
            # 执行任务
            result = await self.task_dispatcher.execute_task(task_type, extracted_data, user_id)
            
            if result.success:
                # 生成智能回复
                smart_reply = await self.gemini_client.generate_smart_reply(message, result.to_dict())
                return smart_reply
            else:
                # 任务执行失败
                error_msg = result.error or "任务执行失败"
                return f"抱歉，{result.message}。错误信息：{error_msg}"
                
        except Exception as e:
            logger.error(f"任务处理失败: {e}")
            return f"处理您的{self._get_task_name(task_type)}请求时出现了问题，请稍后再试。"
    
    async def _handle_query(
        self, 
        message: str, 
        analysis: Dict[str, Any],
        user_id: str
    ) -> str:
        """
        处理查询请求
        
        Args:
            message: 用户消息
            analysis: AI分析结果
            user_id: 用户ID
            
        Returns:
            str: 查询结果回复
        """
        try:
            # 分析查询意图
            query_intent = await self._analyze_query_intent(message)
            
            if not query_intent:
                # 默认查询待办事项
                query_intent = {
                    "type": "todo",
                    "filters": {"status": "待完成"}
                }
                logger.info("查询意图分析失败，使用默认查询：待办事项")
            
            query_type = query_intent.get("type")
            filters = query_intent.get("filters", {})
            
            # 为待办事项查询添加默认过滤条件
            if query_type == "todo" and not filters:
                filters = {}  # 先不加过滤条件，查看所有记录
                logger.info("待办事项查询：不使用状态过滤，查询所有记录")
            
            # 执行查询
            result = await self.task_dispatcher.query_data(query_type, filters, user_id)
            
            if result.success:
                # 生成友好的查询回复
                query_results = result.data.get("records", [])
                reply = await self.gemini_client.generate_query_response(
                    query_results, 
                    self._get_task_name(query_type)
                )
                return reply
            else:
                return f"查询失败：{result.message}"
                
        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            return "查询过程中出现了问题，请稍后再试。"
    
    async def _analyze_query_intent(self, message: str) -> Optional[Dict[str, Any]]:
        """
        分析查询意图
        
        Args:
            message: 用户消息
            
        Returns:
            Optional[Dict]: 查询意图分析结果
        """
        from datetime import datetime, timedelta
        
        # 获取今天和明天的日期
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        current_weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]
        
        prompt = f"""
**当前时间信息**：
当前日期：{today}
当前时间：{now.strftime('%H:%M')}
星期：{current_weekday}

请分析用户的查询意图，确定查询类型和条件，以JSON格式返回：
{{
    "type": "查询类型(accounting/subscription/todo)",
    "filters": {{
        // 查询过滤条件
    }}
}}

查询类型说明：
- accounting: 记账、支出、收入、财务相关查询
- subscription: 订阅、会员、续费相关查询  
- todo: 任务、待办、提醒事项相关查询

**重要：日期过滤规则**
- "今天的" → 添加截止日期过滤: {{"截止日期": "{today}"}}
- "明天的" → 添加截止日期过滤: {{"截止日期": "{tomorrow}"}}
- "最重要的"、"优先级高的" → 添加优先级过滤: {{"优先级": "高"}}
- "紧急的" → 添加优先级过滤: {{"优先级": "高"}}
- "进行中的" → 添加状态过滤: {{"状态": "进行中"}}
- "未完成的"、"待办的" → 添加状态过滤: {{"状态": "待完成"}}

常见查询示例：
- "我有哪些任务" → {{"type": "todo", "filters": {{}}}}
- "今天的任务有哪些" → {{"type": "todo", "filters": {{"截止日期": "{today}"}}}}
- "明天的任务" → {{"type": "todo", "filters": {{"截止日期": "{tomorrow}"}}}}
- "说说最重要的待办" → {{"type": "todo", "filters": {{"优先级": "高"}}}}
- "进行中的任务" → {{"type": "todo", "filters": {{"状态": "进行中"}}}}
- "本月花了多少钱" → {{"type": "accounting", "filters": {{}}}}
- "我的订阅" → {{"type": "subscription", "filters": {{"状态": "活跃"}}}}

用户消息：{message}
"""
        
        try:
            response = await asyncio.to_thread(
                self.gemini_client.model.generate_content,
                prompt
            )
            
            response_text = response.text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                import json
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                logger.info(f"查询意图分析成功: {result}")
                return result
            
        except Exception as e:
            logger.error(f"查询意图分析失败: {e}")
        
        return None
    
    async def _handle_delete(
        self, 
        message: str, 
        analysis: Dict[str, Any],
        user_id: str
    ) -> str:
        """
        处理删除请求
        
        Args:
            message: 用户消息
            analysis: AI分析结果
            user_id: 用户ID
            
        Returns:
            str: 删除结果回复
        """
        try:
            # 分析删除意图
            delete_intent = await self._analyze_delete_intent(message)
            
            if not delete_intent:
                return "抱歉，我无法理解您要删除什么内容。请明确指出要删除的项目。"
            
            delete_type = delete_intent.get("type", "todo")  # 默认删除待办事项
            target = delete_intent.get("target", "all")  # 默认删除所有
            
            # 执行删除操作
            if target == "all":
                result = await self.task_dispatcher.delete_all_data(delete_type, user_id)
            else:
                # 这里可以扩展支持特定条件的删除
                result = await self.task_dispatcher.delete_all_data(delete_type, user_id)
            
            if result.success:
                return f"已成功清除所有{self._get_task_name(delete_type)}！"
            else:
                return f"删除操作失败：{result.message}"
                
        except Exception as e:
            logger.error(f"删除处理失败: {e}")
            return "删除过程中出现了问题，请稍后再试。"
    
    async def _handle_update(
        self, 
        message: str, 
        analysis: Dict[str, Any],
        user_id: str
    ) -> str:
        """
        处理更新请求
        
        Args:
            message: 用户消息
            analysis: AI分析结果
            user_id: 用户ID
            
        Returns:
            str: 更新结果回复
        """
        try:
            # 分析更新意图
            update_intent = await self._analyze_update_intent(message)
            
            if not update_intent:
                return "抱歉，我无法理解您要更新什么内容。请明确指出要修改的项目和新的值。"
            
            update_type = update_intent.get("type", "todo")
            task_name = update_intent.get("task_name", "")
            new_status = update_intent.get("new_status", "")
            new_priority = update_intent.get("new_priority", "")
            new_date = update_intent.get("new_date", "")
            
            if not task_name:
                return "请明确指出要更新的任务名称。"
            
            # 执行更新操作
            result = await self.task_dispatcher.update_task_status(
                update_type, task_name, new_status, new_priority, new_date, user_id
            )
            
            if result.success:
                task_name_display = result.data.get('task_name', task_name)
                if new_status:
                    return f"✅ 已将任务「{task_name_display}」的状态更新为「{new_status}」"
                elif new_priority:
                    return f"📝 已将任务「{task_name_display}」的优先级更新为「{new_priority}」"
                elif new_date:
                    return f"📅 已将任务「{task_name_display}」的截止日期更新为「{new_date}」"
                else:
                    return f"✅ 已更新任务「{task_name_display}」"
            else:
                return f"更新失败：{result.message}"
                
        except Exception as e:
            logger.error(f"更新处理失败: {e}")
            return "更新过程中出现了问题，请稍后再试。"
    
    async def _analyze_delete_intent(self, message: str) -> Optional[Dict[str, Any]]:
        """
        分析删除意图
        
        Args:
            message: 用户消息
            
        Returns:
            Optional[Dict]: 删除意图分析结果
        """
        prompt = f"""
请分析用户的删除意图，确定删除类型和目标，以JSON格式返回：
{{
    "type": "删除数据类型(accounting/subscription/todo)",
    "target": "删除目标(all表示全部，specific表示特定条件)",
    "conditions": {{
        // 如果是特定删除，这里放具体条件
    }}
}}

删除类型说明：
- todo: 待办事项、任务相关删除
- accounting: 记账、支出相关删除  
- subscription: 订阅、会员相关删除

常见删除示例：
- "清除所有任务" → {{"type": "todo", "target": "all"}}
- "删除所有待办事项" → {{"type": "todo", "target": "all"}}
- "清空记账记录" → {{"type": "accounting", "target": "all"}}

用户消息：{message}
"""
        
        try:
            response = await asyncio.to_thread(
                self.gemini_client.model.generate_content,
                prompt
            )
            
            response_text = response.text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                import json
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                logger.info(f"删除意图分析成功: {result}")
                return result
            
        except Exception as e:
            logger.error(f"删除意图分析失败: {e}")
        
        return None
    
    async def _analyze_update_intent(self, message: str) -> Optional[Dict[str, Any]]:
        """
        分析更新意图
        
        Args:
            message: 用户消息
            
        Returns:
            Optional[Dict]: 更新意图分析结果
        """
        from datetime import datetime, timedelta
        
        # 获取当前时间信息
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        
        prompt = f"""
请分析用户的更新意图，确定要更新的任务和更新内容，以JSON格式返回：
{{
    "type": "数据类型(accounting/subscription/todo)",
    "task_name": "要更新的任务名称",
    "new_status": "新状态(已完成/进行中/待完成/已取消)",
    "new_priority": "新优先级(高/中/低)",
    "new_date": "新截止日期(YYYY-MM-DD格式)"
}}

**当前日期信息**：
今天：{today}
明天：{tomorrow}

**更新类型判断**：
- 如果包含"已经完成"、"完成了"、"做完了"等 → 状态更新为"已完成"
- 如果包含"开始做"、"正在做" → 状态更新为"进行中"  
- 如果包含"暂停"、"取消" → 状态更新为"已取消"
- 如果包含"重要"、"紧急"、"优先级高" → 优先级更新为"高"
- 如果包含"不急"、"优先级低" → 优先级更新为"低"
- 如果包含"延期到"、"推迟到"、"改为" → 日期更新

**任务名称提取**：
从用户消息中提取核心任务名称，例如：
- "发布代码已经完成" → 任务名称："发布代码"
- "项目报告做完了" → 任务名称："项目报告"  
- "开会推迟到明天" → 任务名称："开会"

常见更新示例：
- "发布代码已经完成" → {{"type": "todo", "task_name": "发布代码", "new_status": "已完成"}}
- "项目很紧急" → {{"type": "todo", "task_name": "项目", "new_priority": "高"}}
- "开会推迟到明天" → {{"type": "todo", "task_name": "开会", "new_date": "{tomorrow}"}}

用户消息：{message}
"""
        
        try:
            response = await asyncio.to_thread(
                self.gemini_client.model.generate_content,
                prompt
            )
            
            response_text = response.text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                import json
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                logger.info(f"更新意图分析成功: {result}")
                return result
            
        except Exception as e:
            logger.error(f"更新意图分析失败: {e}")
        
        return None
    
    def _get_conversation_context(self, user_id: str) -> Optional[str]:
        """
        获取用户对话上下文
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[str]: 对话上下文
        """
        return self.conversation_contexts.get(user_id, {}).get("context")
    
    def _update_conversation_context(
        self, 
        user_id: str, 
        message: str, 
        analysis: Dict[str, Any]
    ) -> None:
        """
        更新用户对话上下文
        
        Args:
            user_id: 用户ID
            message: 用户消息
            analysis: AI分析结果
        """
        if user_id not in self.conversation_contexts:
            self.conversation_contexts[user_id] = {
                "messages": [],
                "context": "",
                "last_task_type": None,
                "updated_at": datetime.now(timezone.utc)
            }
        
        user_context = self.conversation_contexts[user_id]
        
        # 添加消息到历史
        user_context["messages"].append({
            "message": message,
            "task_type": analysis.get("task_type"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 保留最近10条消息
        if len(user_context["messages"]) > 10:
            user_context["messages"] = user_context["messages"][-10:]
        
        # 更新上下文摘要
        recent_messages = user_context["messages"][-3:]  # 最近3条
        context_summary = "最近的对话:\n"
        for msg in recent_messages:
            context_summary += f"- {msg['message'][:50]}...\n"
        
        user_context["context"] = context_summary
        user_context["last_task_type"] = analysis.get("task_type")
        user_context["updated_at"] = datetime.now(timezone.utc)
    
    def _get_task_name(self, task_type: str) -> str:
        """
        获取任务类型的中文名称
        
        Args:
            task_type: 任务类型
            
        Returns:
            str: 中文名称
        """
        task_names = {
            "accounting": "记账",
            "subscription": "订阅",
            "todo": "待办事项"
        }
        return task_names.get(task_type, task_type)
    
    async def get_task_suggestions(self, user_id: str) -> List[str]:
        """
        获取任务建议
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[str]: 任务建议列表
        """
        suggestions = []
        
        try:
            # 获取今日待办
            todo_task = TaskFactory.create_task("todo")
            if todo_task:
                today_result = await todo_task.get_today_todos()
                if today_result.success:
                    today_count = today_result.data.get("today_count", 0)
                    overdue_count = today_result.data.get("overdue_count", 0)
                    
                    if today_count > 0:
                        suggestions.append(f"您今天有 {today_count} 项待办事项")
                    if overdue_count > 0:
                        suggestions.append(f"您有 {overdue_count} 项逾期待办事项")
            
            # 获取即将续费的订阅
            subscription_task = TaskFactory.create_task("subscription")
            if subscription_task:
                renewal_result = await subscription_task.get_upcoming_renewals(7)
                if renewal_result.success:
                    renewal_count = renewal_result.data.get("count", 0)
                    if renewal_count > 0:
                        suggestions.append(f"您有 {renewal_count} 个订阅即将在7天内续费")
            
        except Exception as e:
            logger.error(f"获取任务建议失败: {e}")
        
        return suggestions
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {}
        
        try:
            # 记账统计
            accounting_task = TaskFactory.create_task("accounting")
            if accounting_task:
                month_stats = await accounting_task.get_statistics("本月")
                if month_stats.success:
                    stats["accounting"] = month_stats.data
            
            # 订阅统计
            subscription_task = TaskFactory.create_task("subscription")
            if subscription_task:
                cost_stats = await subscription_task.get_monthly_cost()
                if cost_stats.success:
                    stats["subscription"] = cost_stats.data
            
            # 待办事项统计
            todo_task = TaskFactory.create_task("todo")
            if todo_task:
                today_stats = await todo_task.get_today_todos()
                if today_stats.success:
                    stats["todo"] = today_stats.data
            
        except Exception as e:
            logger.error(f"获取用户统计失败: {e}")
        
        return stats
    
    def clear_conversation_context(self, user_id: str) -> None:
        """
        清除用户对话上下文
        
        Args:
            user_id: 用户ID
        """
        if user_id in self.conversation_contexts:
            del self.conversation_contexts[user_id]
            logger.info(f"已清除用户 {user_id} 的对话上下文") 