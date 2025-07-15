"""
记账任务类
处理收入和支出记录
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from .base_task import BaseTask, TaskResult
from ..storage.notion_client import NotionClient
from ..config.settings import settings


class AccountingTask(BaseTask):
    """记账任务类"""
    
    def __init__(self):
        super().__init__("记账")
        self.notion_client = NotionClient()
    
    async def execute(self, data: Dict[str, Any]) -> TaskResult:
        """
        执行记账任务
        
        Args:
            data: 记账数据
            
        Returns:
            TaskResult: 执行结果
        """
        try:
            # 解析日期
            date_str = data.get('date')
            if isinstance(date_str, str):
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    # 尝试解析简单的日期格式
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    date = date.replace(tzinfo=timezone.utc)
            else:
                date = datetime.now(timezone.utc)
            
            # 创建记账记录
            page_id = await self.notion_client.add_accounting_entry(
                title=data.get('title', '未知支出'),
                amount=float(data.get('amount', 0.0)),
                category=data.get('category', '其他'),
                date=date,
                description=data.get('description', ''),
                type_=data.get('type', '支出')
            )
            
            if page_id:
                return TaskResult(
                    success=True,
                    data={
                        'page_id': page_id,
                        'title': data.get('title'),
                        'amount': data.get('amount'),
                        'type': data.get('type'),
                        'category': data.get('category')
                    },
                    message=f"记账成功：{data.get('type', '支出')} {data.get('amount', 0)}元 - {data.get('title', '未知')}"
                )
            else:
                return TaskResult(
                    success=False,
                    error="Notion记录创建失败",
                    message="记账失败，请稍后重试"
                )
                
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="记账过程中出现错误"
            )
    
    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        验证记账数据
        
        Args:
            data: 待验证的数据
            
        Returns:
            bool: 数据是否有效
        """
        # 检查必填字段
        if not data.get('title'):
            self.logger.error("缺少记账标题")
            return False
        
        # 检查金额
        try:
            amount = float(data.get('amount', 0))
            if amount <= 0:
                self.logger.error("金额必须大于0")
                return False
        except (ValueError, TypeError):
            self.logger.error("金额格式不正确")
            return False
        
        # 检查类型
        type_ = data.get('type', '支出')
        if type_ not in ['收入', '支出']:
            self.logger.warning(f"未知的记账类型: {type_}，将默认为支出")
            data['type'] = '支出'
        
        return True
    
    async def query(self, filters: Optional[Dict[str, Any]] = None) -> TaskResult:
        """
        查询记账记录
        
        Args:
            filters: 查询过滤条件
            
        Returns:
            TaskResult: 查询结果
        """
        try:
            filter_condition = None
            sorts = [{"property": "日期", "direction": "descending"}]
            
            if filters:
                filter_parts = []
                
                # 按类型过滤
                if 'type' in filters:
                    filter_parts.append({
                        "property": "类型",
                        "select": {"equals": filters['type']}
                    })
                
                # 按分类过滤
                if 'category' in filters:
                    filter_parts.append({
                        "property": "分类",
                        "select": {"equals": filters['category']}
                    })
                
                # 按日期范围过滤
                if 'date_from' in filters or 'date_to' in filters:
                    date_filter = {"property": "日期", "date": {}}
                    if 'date_from' in filters:
                        date_filter["date"]["on_or_after"] = filters['date_from']
                    if 'date_to' in filters:
                        date_filter["date"]["on_or_before"] = filters['date_to']
                    filter_parts.append(date_filter)
                
                # 组合过滤条件
                if len(filter_parts) == 1:
                    filter_condition = filter_parts[0]
                elif len(filter_parts) > 1:
                    filter_condition = {"and": filter_parts}
            
            # 执行查询
            results = await self.notion_client.query_database(
                database_name="accounting",
                filter_condition=filter_condition,
                sorts=sorts,
                limit=filters.get('limit', 20) if filters else 20
            )
            
            return TaskResult(
                success=True,
                data={"records": results, "count": len(results)},
                message=f"找到 {len(results)} 条记账记录"
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="查询记账记录失败"
            )
    
    async def delete_all(self) -> TaskResult:
        """
        删除所有记账记录
        
        Returns:
            TaskResult: 删除结果
        """
        try:
            # 先查询所有记账记录
            all_records = await self.notion_client.query_database(
                database_name="accounting",
                filter_condition=None,
                sorts=None,
                limit=None  # 获取所有记录
            )
            
            if not all_records:
                return TaskResult(
                    success=True,
                    data={"deleted_count": 0},
                    message="没有记账记录需要删除"
                )
            
            # 删除所有记录
            deleted_count = 0
            failed_count = 0
            
            for record in all_records:
                page_id = record.get("id")
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
                    message=f"已成功删除 {deleted_count} 条记账记录"
                )
            else:
                return TaskResult(
                    success=True,  # 部分成功也算成功
                    data={"deleted_count": deleted_count, "failed_count": failed_count},
                    message=f"删除了 {deleted_count} 条记账记录，{failed_count} 条删除失败"
                )
            
        except Exception as e:
            self.logger.error(f"删除所有记账记录失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="删除记账记录过程中出现错误"
            )
    
    def get_required_fields(self) -> List[str]:
        """获取必填字段"""
        return ['title', 'amount']
    
    def get_optional_fields(self) -> List[str]:
        """获取可选字段"""
        return ['category', 'type', 'description', 'date']
    
    def get_task_description(self) -> str:
        """获取任务描述"""
        return "记录收入或支出信息到Notion数据库"
    
    def format_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化记账数据"""
        formatted_data = super().format_data(data)
        
        # 确保金额为浮点数
        if 'amount' in formatted_data:
            try:
                formatted_data['amount'] = float(formatted_data['amount'])
            except (ValueError, TypeError):
                formatted_data['amount'] = 0.0
        
        # 确保类型有效
        if 'type' not in formatted_data or formatted_data['type'] not in ['收入', '支出']:
            formatted_data['type'] = '支出'
        
        # 设置默认分类
        if 'category' not in formatted_data or not formatted_data['category']:
            formatted_data['category'] = '其他'
        
        # 设置默认日期
        if 'date' not in formatted_data:
            formatted_data['date'] = datetime.now().strftime('%Y-%m-%d')
        
        return formatted_data
    
    async def get_statistics(self, period: str = "本月") -> TaskResult:
        """
        获取记账统计信息
        
        Args:
            period: 统计周期 (本月/本年/全部)
            
        Returns:
            TaskResult: 统计结果
        """
        try:
            # 根据周期设置过滤条件
            filters = {}
            if period == "本月":
                now = datetime.now()
                filters['date_from'] = f"{now.year}-{now.month:02d}-01"
                if now.month == 12:
                    filters['date_to'] = f"{now.year + 1}-01-01"
                else:
                    filters['date_to'] = f"{now.year}-{now.month + 1:02d}-01"
            elif period == "本年":
                now = datetime.now()
                filters['date_from'] = f"{now.year}-01-01"
                filters['date_to'] = f"{now.year + 1}-01-01"
            
            # 查询所有记录
            query_result = await self.query(filters)
            
            if not query_result.success:
                return query_result
            
            records = query_result.data.get('records', [])
            
            # 计算统计信息
            total_income = 0.0
            total_expense = 0.0
            category_stats = {}
            
            for record in records:
                amount = record.get('金额', 0) or 0
                record_type = record.get('类型', '支出')
                category = record.get('分类', '其他')
                
                if record_type == '收入':
                    total_income += amount
                else:
                    total_expense += amount
                
                # 分类统计
                if category not in category_stats:
                    category_stats[category] = {'收入': 0.0, '支出': 0.0}
                category_stats[category][record_type] += amount
            
            stats = {
                'period': period,
                'total_income': total_income,
                'total_expense': total_expense,
                'net_amount': total_income - total_expense,
                'record_count': len(records),
                'category_stats': category_stats
            }
            
            return TaskResult(
                success=True,
                data=stats,
                message=f"{period}统计：收入 {total_income}元，支出 {total_expense}元，净额 {total_income - total_expense}元"
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="获取统计信息失败"
            ) 