"""
待办事项任务类
处理待办事项的创建和管理
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from .base_task import BaseTask, TaskResult
from ..storage.notion_client import NotionClient
from ..config.settings import settings


class TodoTask(BaseTask):
    """待办事项任务类"""
    
    def __init__(self):
        super().__init__("待办事项")
        self.notion_client = NotionClient()
    
    async def execute(self, data: Dict[str, Any]) -> TaskResult:
        """
        执行待办事项任务
        
        Args:
            data: 待办事项数据
            
        Returns:
            TaskResult: 执行结果
        """
        try:
            # 解析截止日期
            due_date = None
            if data.get('due_date'):
                due_date_str = data.get('due_date')
                if isinstance(due_date_str, str):
                    try:
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    except ValueError:
                        # 尝试解析简单的日期格式
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                        due_date = due_date.replace(tzinfo=timezone.utc)
            
            # 创建待办事项记录
            page_id = await self.notion_client.add_todo(
                title=data.get('title', '未知任务'),
                priority=data.get('priority', '中'),
                due_date=due_date,
                category=data.get('category', '其他'),
                description=data.get('description', '')
            )
            
            if page_id:
                return TaskResult(
                    success=True,
                    data={
                        'page_id': page_id,
                        'title': data.get('title'),
                        'priority': data.get('priority'),
                        'due_date': due_date.isoformat() if due_date else None,
                        'category': data.get('category')
                    },
                    message=f"待办事项创建成功：{data.get('title', '未知任务')}"
                )
            else:
                return TaskResult(
                    success=False,
                    error="Notion记录创建失败",
                    message="待办事项创建失败，请稍后重试"
                )
                
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="创建待办事项过程中出现错误"
            )
    
    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        验证待办事项数据
        
        Args:
            data: 待验证的数据
            
        Returns:
            bool: 数据是否有效
        """
        # 检查必填字段
        if not data.get('title'):
            self.logger.error("缺少待办事项标题")
            return False
        
        # 检查优先级
        priority = data.get('priority', '中')
        if priority not in ['高', '中', '低']:
            self.logger.warning(f"未知的优先级: {priority}，将默认为中")
            data['priority'] = '中'
        
        # 验证截止日期格式
        if data.get('due_date'):
            try:
                due_date_str = data.get('due_date')
                if isinstance(due_date_str, str):
                    # 尝试解析日期
                    try:
                        datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    except ValueError:
                        datetime.strptime(due_date_str, '%Y-%m-%d')
            except (ValueError, TypeError):
                self.logger.error("截止日期格式不正确")
                return False
        
        return True
    
    async def query(self, filters: Optional[Dict[str, Any]] = None) -> TaskResult:
        """
        查询待办事项
        
        Args:
            filters: 查询过滤条件
            
        Returns:
            TaskResult: 查询结果
        """
        try:
            filter_condition = None
            sorts = [{"property": "截止日期", "direction": "ascending"}]
            
            if filters:
                filter_parts = []
                
                # 按状态过滤 - 支持中英文字段名
                status_filter = filters.get('status') or filters.get('状态')
                if status_filter:
                    filter_parts.append({
                        "property": "状态",
                        "select": {"equals": status_filter}
                    })
                
                # 按优先级过滤 - 支持中英文字段名
                priority_filter = filters.get('priority') or filters.get('优先级')
                if priority_filter:
                    filter_parts.append({
                        "property": "优先级",
                        "select": {"equals": priority_filter}
                    })
                
                # 按分类过滤 - 支持中英文字段名
                category_filter = filters.get('category') or filters.get('分类')
                if category_filter:
                    filter_parts.append({
                        "property": "分类",
                        "select": {"equals": category_filter}
                    })
                
                # 按截止日期过滤 - 支持中英文字段名
                due_date_filter = filters.get('due_date') or filters.get('截止日期')
                if due_date_filter:
                    # 确保日期格式正确
                    if isinstance(due_date_filter, str):
                        try:
                            # 如果是日期字符串，转换为ISO格式
                            if len(due_date_filter) == 10:  # YYYY-MM-DD format
                                due_date_filter += "T00:00:00.000Z"
                            
                            filter_parts.append({
                                "property": "截止日期",
                                "date": {"equals": due_date_filter}
                            })
                        except Exception as e:
                            self.logger.warning(f"日期格式解析失败: {due_date_filter}, {e}")
                
                # 即将到期的任务
                if filters.get('due_soon'):
                    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
                    filter_parts.append({
                        "property": "截止日期",
                        "date": {"on_or_before": tomorrow.isoformat()}
                    })
                
                # 已过期的任务
                if filters.get('overdue'):
                    now = datetime.now(timezone.utc)
                    filter_parts.append({
                        "and": [
                            {
                                "property": "截止日期",
                                "date": {"before": now.isoformat()}
                            },
                            {
                                "property": "状态",
                                "select": {"does_not_equal": "已完成"}
                            }
                        ]
                    })
                
                # 组合过滤条件
                if len(filter_parts) == 1:
                    filter_condition = filter_parts[0]
                elif len(filter_parts) > 1:
                    filter_condition = {"and": filter_parts}
            
            self.logger.info(f"执行查询，过滤条件: {filter_condition}")
            
            # 执行查询
            results = await self.notion_client.query_database(
                database_name="todos",
                filter_condition=filter_condition,
                sorts=sorts,
                limit=filters.get('limit', 20) if filters else 20
            )
            
            # 如果有过滤条件但没有结果，尝试无过滤条件查询做对比
            if filter_condition and len(results) == 0:
                self.logger.info("有过滤条件的查询无结果，尝试查询所有记录进行调试")
                all_results = await self.notion_client.query_database(
                    database_name="todos",
                    filter_condition=None,
                    sorts=sorts,
                    limit=5
                )
                self.logger.info(f"数据库中共有 {len(all_results)} 条待办记录")
                
                # 如果有记录，记录调试信息
                if all_results:
                    sample_record = all_results[0]
                    self.logger.info(f"示例记录字段: {list(sample_record.keys())}")
                    self.logger.info(f"示例记录状态: {sample_record.get('状态')}")
                    self.logger.info(f"示例记录优先级: {sample_record.get('优先级')}")
                    self.logger.info(f"示例记录截止日期: {sample_record.get('截止日期')}")
            
            self.logger.info(f"查询完成，返回 {len(results)} 条记录")
            return TaskResult(
                success=True,
                data={"records": results, "count": len(results)},
                message=f"找到 {len(results)} 条待办事项"
            )
            
        except Exception as e:
            self.logger.error(f"查询待办事项失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="查询待办事项失败"
            )
    
    async def delete_all(self) -> TaskResult:
        """
        删除所有待办事项
        
        Returns:
            TaskResult: 删除结果
        """
        try:
            # 先查询所有待办事项
            all_todos = await self.notion_client.query_database(
                database_name="todos",
                filter_condition=None,
                sorts=None,
                limit=None  # 获取所有记录
            )
            
            if not all_todos:
                return TaskResult(
                    success=True,
                    data={"deleted_count": 0},
                    message="没有待办事项需要删除"
                )
            
            # 删除所有记录
            deleted_count = 0
            failed_count = 0
            
            for todo in all_todos:
                page_id = todo.get("id")
                if page_id:
                    success = await self.notion_client.delete_page(page_id)
                    if success:
                        deleted_count += 1
                    else:
                        failed_count += 1
            
            if failed_count == 0:
                return TaskResult(
                    success=True,
                    data={"deleted_count": deleted_count},
                    message=f"已成功删除 {deleted_count} 条待办事项"
                )
            else:
                return TaskResult(
                    success=True,  # 部分成功也算成功
                    data={"deleted_count": deleted_count, "failed_count": failed_count},
                    message=f"删除了 {deleted_count} 条待办事项，{failed_count} 条删除失败"
                )
            
        except Exception as e:
            self.logger.error(f"删除所有待办事项失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="删除待办事项过程中出现错误"
            )
    
    async def update_by_name(
        self, 
        task_name: str, 
        new_status: str = "", 
        new_priority: str = "", 
        new_date: str = ""
    ) -> TaskResult:
        """
        根据任务名称更新待办事项
        
        Args:
            task_name: 任务名称
            new_status: 新状态
            new_priority: 新优先级
            new_date: 新截止日期
            
        Returns:
            TaskResult: 更新结果
        """
        try:
            # 先查询匹配的任务
            all_todos = await self.notion_client.query_database(
                database_name="todos",
                filter_condition=None,
                sorts=None,
                limit=None
            )
            
            if not all_todos:
                return TaskResult(
                    success=False,
                    error="没有找到任何任务",
                    message="待办事项列表为空"
                )
            
            # 寻找匹配的任务（支持模糊匹配）
            matched_tasks = []
            for todo in all_todos:
                title = todo.get("标题", "").lower()
                if task_name.lower() in title or title in task_name.lower():
                    matched_tasks.append(todo)
            
            self.logger.info(f"找到 {len(matched_tasks)} 个匹配「{task_name}」的任务")
            
            if not matched_tasks:
                return TaskResult(
                    success=False,
                    error="任务未找到",
                    message=f"未找到名称包含「{task_name}」的任务"
                )
            
            # 选择最佳匹配任务
            best_match = None
            if len(matched_tasks) == 1:
                best_match = matched_tasks[0]
                self.logger.info(f"找到唯一匹配任务: {best_match.get('标题')}")
            else:
                # 多个匹配时，使用AI智能选择
                self.logger.info(f"找到多个匹配任务，使用AI选择最佳匹配")
                best_match = await self._select_best_match_with_ai(
                    task_name, matched_tasks, new_status, new_priority, new_date
                )
                
                if not best_match:
                    # AI选择失败，提供任务列表让用户确认
                    task_list = []
                    for i, task in enumerate(matched_tasks, 1):
                        title = task.get("标题", "")
                        status = task.get("状态", "")
                        due_date = task.get("截止日期", "")
                        task_list.append(f"{i}. {title} ({status}, 截止: {due_date})")
                    
                    return TaskResult(
                        success=False,
                        error="多个匹配任务",
                        message=f"找到多个包含「{task_name}」的任务，请明确指定：\n" + "\n".join(task_list)
                    )
            
            page_id = best_match.get("id")
            if not page_id:
                return TaskResult(
                    success=False,
                    error="无效的任务ID",
                    message="找到的任务缺少有效ID"
                )
            
            # 准备更新数据
            update_data = {}
            
            if new_status:
                update_data["状态"] = {
                    "select": {"name": new_status}
                }
            
            if new_priority:
                update_data["优先级"] = {
                    "select": {"name": new_priority}
                }
            
            if new_date:
                try:
                    # 解析日期
                    from datetime import datetime
                    if len(new_date) == 10:  # YYYY-MM-DD格式
                        date_obj = datetime.strptime(new_date, '%Y-%m-%d')
                        update_data["截止日期"] = {
                            "date": {"start": new_date}
                        }
                except Exception as e:
                    self.logger.warning(f"日期格式解析失败: {new_date}, {e}")
            
            if not update_data:
                return TaskResult(
                    success=False,
                    error="没有可更新的数据",
                    message="请指定要更新的状态、优先级或截止日期"
                )
            
            # 执行更新
            self.logger.info(f"更新任务 {best_match.get('标题')} (ID: {page_id})")
            success = await self.notion_client.update_page(page_id, update_data)
            
            if success:
                task_title = best_match.get("标题", task_name)
                update_info = []
                if new_status:
                    update_info.append(f"状态: {new_status}")
                if new_priority:
                    update_info.append(f"优先级: {new_priority}")
                if new_date:
                    update_info.append(f"截止日期: {new_date}")
                
                return TaskResult(
                    success=True,
                    data={
                        "task_name": task_title,
                        "page_id": page_id,
                        "updates": update_info
                    },
                    message=f"已更新任务「{task_title}」: {', '.join(update_info)}"
                )
            else:
                return TaskResult(
                    success=False,
                    error="Notion更新失败",
                    message="更新任务时出错，请稍后重试"
                )
            
        except Exception as e:
            self.logger.error(f"更新待办事项失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="更新待办事项过程中出现错误"
            )
    
    async def _select_best_match_with_ai(
        self, 
        task_name: str, 
        matched_tasks: List[Dict], 
        new_status: str = "", 
        new_priority: str = "", 
        new_date: str = ""
    ) -> Optional[Dict]:
        """
        使用AI智能选择最佳匹配的任务
        
        Args:
            task_name: 用户提到的任务名称
            matched_tasks: 匹配的任务列表
            new_status: 要设置的新状态
            new_priority: 要设置的新优先级
            new_date: 要设置的新日期
            
        Returns:
            Optional[Dict]: 最佳匹配的任务，如果无法确定则返回None
        """
        try:
            # 构建候选任务信息
            candidates_info = []
            for i, task in enumerate(matched_tasks):
                task_info = {
                    "index": i,
                    "title": task.get("标题", ""),
                    "status": task.get("状态", ""),
                    "priority": task.get("优先级", ""),
                    "due_date": task.get("截止日期", ""),
                    "category": task.get("分类", ""),
                    "description": task.get("描述", "")
                }
                candidates_info.append(task_info)
            
            prompt = f"""
你需要从以下候选任务中选择最适合用户更新意图的任务。

用户想要更新的任务名称：{task_name}
更新内容：
- 新状态：{new_status if new_status else '无'}
- 新优先级：{new_priority if new_priority else '无'}
- 新截止日期：{new_date if new_date else '无'}

候选任务列表：
{json.dumps(candidates_info, ensure_ascii=False, indent=2)}

请分析选择最合适的任务，考虑因素：
1. 任务标题与用户提到的名称的相似度
2. 任务的当前状态（例如，不要更新已完成的任务为完成状态）
3. 任务的优先级和分类
4. 截止日期的合理性

请以JSON格式返回选择结果：
{{
    "selected_index": 选中任务的索引号,
    "confidence": 0.0-1.0的置信度,
    "reason": "选择理由"
}}

如果无法确定最佳选择，请返回 {{"selected_index": -1, "confidence": 0.0, "reason": "无法确定"}}
"""
            
            # 导入必要的模块
            from ..ai.gemini_client import GeminiClient
            import asyncio
            import json
            
            gemini_client = GeminiClient()
            
            response = await asyncio.to_thread(
                gemini_client.model.generate_content,
                prompt
            )
            
            response_text = response.text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                
                selected_index = result.get("selected_index", -1)
                confidence = result.get("confidence", 0.0)
                reason = result.get("reason", "")
                
                self.logger.info(f"AI选择结果: index={selected_index}, confidence={confidence}, reason={reason}")
                
                if selected_index >= 0 and selected_index < len(matched_tasks) and confidence >= 0.7:
                    selected_task = matched_tasks[selected_index]
                    self.logger.info(f"AI选择任务: {selected_task.get('标题')} (置信度: {confidence})")
                    return selected_task
                else:
                    self.logger.warning(f"AI选择置信度不足或索引无效: {selected_index}, {confidence}")
                    return None
            
        except Exception as e:
            self.logger.error(f"AI任务选择失败: {e}")
            return None
        
        return None
    
    def get_required_fields(self) -> List[str]:
        """获取必填字段"""
        return ['title']
    
    def get_optional_fields(self) -> List[str]:
        """获取可选字段"""
        return ['priority', 'due_date', 'category', 'description']
    
    def get_task_description(self) -> str:
        """获取任务描述"""
        return "创建和管理待办事项"
    
    def format_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化待办事项数据"""
        formatted_data = super().format_data(data)
        
        # 确保优先级有效
        if 'priority' not in formatted_data or formatted_data['priority'] not in ['高', '中', '低']:
            formatted_data['priority'] = '中'
        
        # 设置默认分类
        if 'category' not in formatted_data or not formatted_data['category']:
            formatted_data['category'] = '其他'
        
        return formatted_data
    
    async def complete_todo(self, todo_id: str) -> TaskResult:
        """
        完成待办事项
        
        Args:
            todo_id: 待办事项ID
            
        Returns:
            TaskResult: 操作结果
        """
        try:
            success = await self.notion_client.update_page(
                page_id=todo_id,
                properties={"状态": "已完成"}
            )
            
            if success:
                return TaskResult(
                    success=True,
                    data={"todo_id": todo_id},
                    message="待办事项已完成"
                )
            else:
                return TaskResult(
                    success=False,
                    error="更新待办事项状态失败",
                    message="完成待办事项失败"
                )
                
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="完成待办事项过程中出现错误"
            )
    
    async def get_today_todos(self) -> TaskResult:
        """
        获取今日待办事项
        
        Returns:
            TaskResult: 今日待办事项列表
        """
        try:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            
            filters = {
                'status': '待完成'
            }
            
            query_result = await self.query(filters)
            
            if not query_result.success:
                return query_result
            
            all_records = query_result.data.get('records', [])
            
            # 过滤出今日到期或逾期的任务
            today_todos = []
            overdue_todos = []
            
            for record in all_records:
                due_date_str = record.get('截止日期')
                if due_date_str:
                    try:
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                        if due_date.date() == today.date():
                            today_todos.append(record)
                        elif due_date < today:
                            overdue_todos.append(record)
                    except (ValueError, AttributeError):
                        continue
            
            # 按优先级排序
            priority_order = {'高': 1, '中': 2, '低': 3}
            today_todos.sort(key=lambda x: priority_order.get(x.get('优先级', '中'), 2))
            overdue_todos.sort(key=lambda x: priority_order.get(x.get('优先级', '中'), 2))
            
            return TaskResult(
                success=True,
                data={
                    "today_todos": today_todos,
                    "overdue_todos": overdue_todos,
                    "today_count": len(today_todos),
                    "overdue_count": len(overdue_todos)
                },
                message=f"今日待办：{len(today_todos)} 项，逾期：{len(overdue_todos)} 项"
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="获取今日待办事项失败"
            )
    
    async def get_priority_todos(self, priority: str = "高") -> TaskResult:
        """
        获取指定优先级的待办事项
        
        Args:
            priority: 优先级（高/中/低）
            
        Returns:
            TaskResult: 待办事项列表
        """
        try:
            filters = {
                'status': '待完成',
                'priority': priority
            }
            
            return await self.query(filters)
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message=f"获取{priority}优先级待办事项失败"
            )
    
    async def update_todo_priority(self, todo_id: str, new_priority: str) -> TaskResult:
        """
        更新待办事项优先级
        
        Args:
            todo_id: 待办事项ID
            new_priority: 新优先级
            
        Returns:
            TaskResult: 操作结果
        """
        try:
            if new_priority not in ['高', '中', '低']:
                return TaskResult(
                    success=False,
                    error="无效的优先级",
                    message="优先级必须是：高、中、低 之一"
                )
            
            success = await self.notion_client.update_page(
                page_id=todo_id,
                properties={"优先级": new_priority}
            )
            
            if success:
                return TaskResult(
                    success=True,
                    data={"todo_id": todo_id, "new_priority": new_priority},
                    message=f"待办事项优先级已更新为：{new_priority}"
                )
            else:
                return TaskResult(
                    success=False,
                    error="更新待办事项优先级失败",
                    message="优先级更新失败"
                )
                
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="更新优先级过程中出现错误"
            ) 