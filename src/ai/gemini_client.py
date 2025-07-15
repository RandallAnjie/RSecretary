"""
Gemini AI 客户端
处理智能对话和任务解析
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union, Tuple
import google.generativeai as genai
from loguru import logger
from ..config.settings import settings


class GeminiClient:
    """
    Gemini AI 客户端
    处理智能对话、任务解析和自然语言理解
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Gemini客户端
        
        Args:
            api_key: Gemini API密钥，如果不提供则从配置中获取
        """
        self.api_key = api_key or settings.gemini.api_key
        if not self.api_key:
            raise ValueError("Gemini API密钥未配置")
        
        # 配置Gemini
        genai.configure(api_key=self.api_key)
        
        # 初始化模型
        self.model = genai.GenerativeModel(
            model_name=settings.gemini.model,
            generation_config=genai.types.GenerationConfig(
                temperature=settings.gemini.temperature,
                max_output_tokens=settings.gemini.max_tokens,
            )
        )
        
        # 任务识别提示词
        self.task_recognition_prompt = """
你是一个智能助理，专门帮助用户管理任务。

**当前时间信息**：
当前日期：{current_date}
当前时间：{current_datetime}
星期：{current_weekday}

请分析用户的消息，判断是否包含以下类型的任务：

1. 记账任务 (accounting) - 用户想要记录收入或支出
2. 订阅管理任务 (subscription) - 用户想要记录或管理订阅服务
3. 待办事项任务 (todo) - 用户想要创建待办事项
4. 查询任务 (query) - 用户想要查询已有的记录
5. 删除任务 (delete) - 用户想要删除或清除记录
6. 更新任务 (update) - 用户想要修改已有的记录
7. 普通聊天 (chat) - 普通对话，不涉及具体任务

**重要：任务状态更新识别规则**
以下表达都应该被识别为更新(update)：
- "XXX已经完成"、"XXX完成了"、"XXX做完了"
- "XXX已经做好了"、"XXX搞定了"、"XXX弄好了"
- "完成XXX"、"搞定XXX"、"做完XXX"
- "XXX的状态改为..."、"把XXX标记为..."
- "XXX延期到..."、"XXX推迟到..."
- "XXX的优先级改为..."、"XXX很紧急"

**重要：删除/清除类语句识别规则**
以下表达都应该被识别为删除(delete)：
- "清除所有..."、"删除所有..."、"移除所有..."
- "清空..."、"重置..."、"清理..."
- "取消所有..."、"撤销所有..."

**重要：查询类语句识别规则**
以下表达都应该被识别为查询(query)：
- "我有哪些..."、"有什么..."、"显示..."、"查看..."
- "说说..."、"告诉我..."、"看看..."
- "最重要的..."、"优先级高的..."、"紧急的..."
- "今天的..."、"明天的..."、"本周的..."、"最近的..."
- "状态..."、"进度..."、"完成情况..."

**创建任务的关键词**：
- "新增"、"添加"、"创建"、"记录"、"设置"、"提醒我"
- "需要做"、"要去"、"计划"、"安排"

**日期时间理解**：
- "今天" = {current_date}
- "明天" = {tomorrow_date}
- "下午" = 当天14:00-18:00
- "晚上" = 当天18:00-22:00
- "上午" = 当天09:00-12:00

请以JSON格式返回分析结果：
{{
    "task_type": "任务类型",
    "confidence": 0.0-1.0,
    "extracted_data": {{
        // 根据任务类型提取的相关数据
    }},
    "response_text": "给用户的回复文本"
}}

用户消息："""

        logger.info("Gemini客户端初始化完成")
    
    async def chat(self, message: str, context: Optional[str] = None) -> str:
        """
        普通聊天对话
        
        Args:
            message: 用户消息
            context: 对话上下文
            
        Returns:
            str: AI回复
        """
        try:
            prompt = f"{context}\n\n用户：{message}" if context else message
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            reply = response.text.strip()
            logger.info(f"AI普通聊天回复: {reply[:100]}...")
            return reply
            
        except Exception as e:
            logger.error(f"AI聊天失败: {e}")
            return "抱歉，我现在无法处理您的消息，请稍后再试。"
    
    async def analyze_task(self, message: str) -> Dict[str, Any]:
        """
        分析用户消息，识别任务类型和提取相关数据
        
        Args:
            message: 用户消息
            
        Returns:
            Dict: 任务分析结果
        """
        try:
            from datetime import datetime, timedelta
            
            # 获取当前时间信息
            now = datetime.now()
            current_date = now.strftime('%Y-%m-%d')
            current_datetime = now.strftime('%Y-%m-%d %H:%M:%S')
            current_weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]
            tomorrow_date = (now + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 格式化提示词，插入时间信息
            formatted_prompt = self.task_recognition_prompt.format(
                current_date=current_date,
                current_datetime=current_datetime,
                current_weekday=current_weekday,
                tomorrow_date=tomorrow_date
            )
            
            prompt = f"{formatted_prompt}\n{message}"
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            # 尝试解析JSON响应
            response_text = response.text.strip()
            
            # 提取JSON部分
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    logger.info(f"任务分析成功: {result.get('task_type', 'unknown')}")
                    return result
                except json.JSONDecodeError:
                    logger.warning("JSON解析失败，返回普通聊天")
            
            # 如果解析失败，返回普通聊天
            return {
                "task_type": "chat",
                "confidence": 0.8,
                "extracted_data": {},
                "response_text": response_text
            }
            
        except Exception as e:
            logger.error(f"任务分析失败: {e}")
            return {
                "task_type": "chat",
                "confidence": 0.5,
                "extracted_data": {},
                "response_text": "我理解了您的消息，让我来帮您处理。"
            }
    
    async def extract_accounting_data(self, message: str) -> Dict[str, Any]:
        """
        从消息中提取记账相关数据
        
        Args:
            message: 用户消息
            
        Returns:
            Dict: 提取的记账数据
        """
        prompt = f"""
请从用户消息中提取记账信息，以JSON格式返回：
{{
    "title": "记录标题",
    "amount": 金额数字,
    "category": "分类",
    "type": "收入或支出",
    "description": "详细描述",
    "date": "YYYY-MM-DD格式日期，默认今天"
}}

如果某些信息缺失，请根据常识推断或设为合理默认值。

用户消息：{message}
"""
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            response_text = response.text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                
                # 设置默认日期
                if 'date' not in result or not result['date']:
                    result['date'] = datetime.now().strftime('%Y-%m-%d')
                
                logger.info(f"记账数据提取成功: {result}")
                return result
            
        except Exception as e:
            logger.error(f"记账数据提取失败: {e}")
        
        # 返回默认结构
        return {
            "title": "未知支出",
            "amount": 0.0,
            "category": "其他",
            "type": "支出",
            "description": message,
            "date": datetime.now().strftime('%Y-%m-%d')
        }
    
    async def extract_subscription_data(self, message: str) -> Dict[str, Any]:
        """
        从消息中提取订阅相关数据
        
        Args:
            message: 用户消息
            
        Returns:
            Dict: 提取的订阅数据
        """
        prompt = f"""
请从用户消息中提取订阅信息，以JSON格式返回：
{{
    "name": "订阅服务名称",
    "price": 价格数字,
    "billing_cycle": "计费周期(月/年/周)",
    "category": "分类",
    "description": "详细描述",
    "next_billing_date": "下次计费日期YYYY-MM-DD"
}}

用户消息：{message}
"""
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            response_text = response.text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                logger.info(f"订阅数据提取成功: {result}")
                return result
            
        except Exception as e:
            logger.error(f"订阅数据提取失败: {e}")
        
        return {
            "name": "未知订阅",
            "price": 0.0,
            "billing_cycle": "月",
            "category": "其他",
            "description": message,
            "next_billing_date": datetime.now().strftime('%Y-%m-%d')
        }
    
    async def extract_todo_data(self, message: str) -> Dict[str, Any]:
        """
        从消息中提取待办事项相关数据
        
        Args:
            message: 用户消息
            
        Returns:
            Dict: 提取的待办事项数据
        """
        from datetime import datetime, timedelta
        
        # 获取当前时间信息
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        current_weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]
        tomorrow_date = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        
        prompt = f"""
**当前时间信息**：
当前日期：{current_date}
当前时间：{current_time}
星期：{current_weekday}

请从用户消息中提取待办事项信息，以JSON格式返回：
{{
    "title": "任务标题",
    "priority": "优先级(高/中/低)",
    "category": "分类",
    "description": "详细描述",
    "due_date": "截止日期(YYYY-MM-DD格式)"
}}

**日期时间解析规则**：
- "今天" → {current_date}
- "明天" → {tomorrow_date}
- "下午" → 今天下午(无具体时间时默认为今天)
- "晚上" → 今天晚上(无具体时间时默认为今天)
- "上午" → 今天上午(无具体时间时默认为今天)
- "这个开会是今天下午" → {current_date}

**优先级判断**：
- 包含"重要"、"紧急"、"必须" → "高"
- 包含"一般"、"普通" → "中"  
- 包含"不急"、"随时" → "低"
- 默认 → "中"

**分类判断**：
- 工作相关：开会、汇报、项目 → "工作"
- 生活相关：买菜、购物、生日 → "生活"
- 学习相关：学习、读书、课程 → "学习"
- 健康相关：锻炼、体检、医院 → "健康"
- 默认 → "其他"

如果某些信息缺失，请根据常识推断或设为合理默认值。

用户消息：{message}
"""
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            response_text = response.text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                
                # 确保字段名正确
                if 'title' not in result and 'task' in result:
                    result['title'] = result.pop('task')
                
                # 设置默认日期
                if 'due_date' not in result or not result['due_date']:
                    result['due_date'] = current_date
                
                # 验证优先级
                if result.get('priority') not in ['高', '中', '低']:
                    result['priority'] = '中'
                
                logger.info(f"待办事项数据提取成功: {result}")
                return result
            
        except Exception as e:
            logger.error(f"待办事项数据提取失败: {e}")
        
        # 返回默认结构
        return {
            "title": "未知任务",
            "priority": "中",
            "category": "其他",
            "description": "",
            "due_date": current_date
        }
    
    async def generate_query_response(self, query_results: List[Dict], query_type: str) -> str:
        """
        根据查询结果生成友好的回复
        
        Args:
            query_results: 查询结果列表
            query_type: 查询类型
            
        Returns:
            str: 生成的回复文本
        """
        if not query_results:
            return f"没有找到相关的{query_type}记录。"
        
        # 如果结果超过10个，按重要性排序并取前10个
        displayed_results = query_results
        total_count = len(query_results)
        
        if total_count > 10:
            # 对于待办事项，按优先级和状态排序
            if query_type == "待办事项":
                priority_order = {"高": 3, "中": 2, "低": 1}
                status_order = {"进行中": 3, "待完成": 2, "已完成": 1, "已取消": 0}
                
                displayed_results = sorted(query_results, key=lambda x: (
                    status_order.get(x.get("状态", ""), 0),
                    priority_order.get(x.get("优先级", ""), 0),
                    x.get("截止日期", "9999-12-31")
                ), reverse=True)[:10]
            else:
                # 其他类型按日期排序
                displayed_results = sorted(query_results, key=lambda x: x.get("日期", x.get("创建时间", "")), reverse=True)[:10]

        prompt = f"""
请根据以下{query_type}查询结果，生成一个详细、结构化的中文回复给用户：

查询结果数据：
{json.dumps(displayed_results, ensure_ascii=False, indent=2)}

总记录数：{total_count}
显示记录数：{len(displayed_results)}

**重要格式要求（适配Synology Chat）**：
1. **不要使用Markdown格式**（如 **粗体** 或 *斜体*）
2. **使用纯文本格式**，用符号和缩进来组织信息
3. **链接格式**：使用 <URL|显示文本> 格式
4. **避免使用表情符号**，用文字描述代替
5. **使用清晰的分组和缩进**

输出格式参考：
您好，这是您的{query_type}：

【进行中】
   - 任务A (优先级高，截止日期 2024-XX-XX)

【待完成】
   - 任务B (优先级中，截止日期 2024-XX-XX)  
   - 任务C (优先级低，无截止日期)

{f"还有 {total_count - len(displayed_results)} 个未显示" if total_count > len(displayed_results) else ""}

每个项目应包含：
- 标题
- 优先级（高/中/低）
- 截止日期
- 描述（如果有）
- 分类
- Notion链接（格式：<链接地址|链接>）
- 创建时间
- 最后编辑时间

总记录数和显示记录数信息
"""
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            reply = response.text.strip()
            logger.info(f"查询回复生成成功，显示 {len(displayed_results)}/{total_count} 条记录")
            return reply
            
        except Exception as e:
            logger.error(f"查询回复生成失败: {e}")
            # 降级处理：直接格式化输出
            return self._format_query_results_fallback(displayed_results, query_type, total_count)
    
    def _format_query_results_fallback(self, results: List[Dict], query_type: str, total_count: int) -> str:
        """
        查询结果格式化的降级处理
        """
        if not results:
            return f"没有找到{query_type}记录。"
        
        formatted_lines = [f"您好，这是您的{query_type}：\n"]
        
        # 按状态分组（仅针对待办事项）
        if query_type == "待办事项":
            status_groups = {}
            for item in results:
                status = item.get("状态", "未知")
                if status not in status_groups:
                    status_groups[status] = []
                status_groups[status].append(item)
            
            # 按优先级排序状态
            status_order = ["进行中", "待完成", "已完成", "已取消"]
            for status in status_order:
                if status not in status_groups:
                    continue
                    
                # 添加状态标题
                status_display = {
                    "进行中": "【进行中】",
                    "待完成": "【待完成】", 
                    "已完成": "【已完成】",
                    "已取消": "【已取消】"
                }.get(status, f"【{status}】")
                
                formatted_lines.append(f"\n{status_display}")
                
                # 添加该状态下的任务
                for item in status_groups[status]:
                    title = item.get("标题", "未知任务")
                    priority = item.get("优先级", "")
                    deadline = item.get("截止日期", "")
                    category = item.get("分类", "")
                    description = item.get("描述", "")
                    url = item.get("url", "")
                    created_time = item.get("创建时间", "")
                    edited_time = item.get("最后编辑时间", "")
                    
                    # 构建任务信息
                    task_info = [f"   - 标题：{title}"]
                    
                    if priority:
                        priority_text = {"高": "【高】", "中": "【中】", "低": "【低】"}.get(priority, priority)
                        task_info.append(f"     优先级：{priority_text}")
                    
                    if deadline:
                        task_info.append(f"     截止日期：{deadline}")
                    
                    if description:
                        task_info.append(f"     描述：{description}")
                    
                    if category and category != "未分类":
                        task_info.append(f"     分类：{category}")
                    
                    if url:
                        task_info.append(f"     Notion链接：<{url}|链接>")
                    
                    if created_time:
                        task_info.append(f"     创建时间：{created_time}")
                    
                    if edited_time:
                        task_info.append(f"     最后编辑时间：{edited_time}")
                    
                    formatted_lines.extend(task_info)
                    formatted_lines.append("")  # 空行分隔
        else:
            # 其他类型的简单格式化
            for i, item in enumerate(results[:10], 1):
                title = item.get("标题", item.get("名称", "未知项目"))
                line = f"{i}. {title}"
                formatted_lines.append(line)
        
        # 添加统计信息
        formatted_lines.append(f"总记录数：{total_count}")
        formatted_lines.append(f"显示记录数：{len(results)}")
        
        if total_count > len(results):
            formatted_lines.append(f"\n还有 {total_count - len(results)} 个未显示")
        else:
            formatted_lines.append(f"\n您已查看全部{query_type}。")
        
        return "\n".join(formatted_lines)
    
    async def generate_smart_reply(self, message: str, task_result: Dict[str, Any]) -> str:
        """
        根据任务执行结果生成智能回复
        
        Args:
            message: 原始用户消息
            task_result: 任务执行结果
            
        Returns:
            str: 生成的智能回复
        """
        prompt = f"""
用户发送了消息："{message}"

任务执行结果：
{json.dumps(task_result, ensure_ascii=False, indent=2)}

请生成一个友好、自然的中文回复，确认任务已完成并提供相关信息。要求：
1. 自然亲切的语气
2. 确认具体完成的操作
3. 如果有重要信息，简要提及
4. 保持简洁
"""
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            reply = response.text.strip()
            logger.info("智能回复生成成功")
            return reply
            
        except Exception as e:
            logger.error(f"智能回复生成失败: {e}")
            return "好的，我已经帮您处理完成了！"
    
    async def test_connection(self) -> bool:
        """
        测试Gemini连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                "请简单回复'连接正常'"
            )
            
            if response and response.text:
                logger.info("Gemini连接测试成功")
                return True
            
        except Exception as e:
            logger.error(f"Gemini连接测试失败: {e}")
        
        return False 