"""
订阅管理任务类
处理订阅服务的记录和管理
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from .base_task import BaseTask, TaskResult
from ..storage.notion_client import NotionClient
from ..config.settings import settings


class SubscriptionTask(BaseTask):
    """订阅管理任务类"""
    
    def __init__(self):
        super().__init__("订阅管理")
        self.notion_client = NotionClient()
    
    async def execute(self, data: Dict[str, Any]) -> TaskResult:
        """
        执行订阅管理任务
        
        Args:
            data: 订阅数据
            
        Returns:
            TaskResult: 执行结果
        """
        try:
            # 计算下次计费日期
            next_billing = self._calculate_next_billing(
                data.get('billing_cycle', '月'),
                data.get('next_billing_date')
            )
            
            # 创建订阅记录
            page_id = await self.notion_client.add_subscription(
                name=data.get('name', '未知订阅'),
                price=float(data.get('price', 0.0)),
                billing_cycle=data.get('billing_cycle', '月'),
                next_billing=next_billing,
                category=data.get('category', '其他'),
                description=data.get('description', '')
            )
            
            if page_id:
                return TaskResult(
                    success=True,
                    data={
                        'page_id': page_id,
                        'name': data.get('name'),
                        'price': data.get('price'),
                        'billing_cycle': data.get('billing_cycle'),
                        'next_billing': next_billing.isoformat(),
                        'category': data.get('category')
                    },
                    message=f"订阅记录成功：{data.get('name', '未知订阅')} - {data.get('price', 0)}元/{data.get('billing_cycle', '月')}"
                )
            else:
                return TaskResult(
                    success=False,
                    error="Notion记录创建失败",
                    message="订阅记录失败，请稍后重试"
                )
                
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="订阅记录过程中出现错误"
            )
    
    def _calculate_next_billing(self, billing_cycle: str, next_billing_date: Optional[str] = None) -> datetime:
        """
        计算下次计费日期
        
        Args:
            billing_cycle: 计费周期
            next_billing_date: 指定的下次计费日期
            
        Returns:
            datetime: 下次计费日期
        """
        if next_billing_date:
            try:
                # 尝试解析提供的日期
                if isinstance(next_billing_date, str):
                    date = datetime.fromisoformat(next_billing_date.replace('Z', '+00:00'))
                else:
                    date = next_billing_date
                return date.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                pass
        
        # 根据计费周期计算
        now = datetime.now(timezone.utc)
        
        if billing_cycle == "周":
            return now + timedelta(weeks=1)
        elif billing_cycle == "月":
            # 下个月的同一天
            if now.month == 12:
                return now.replace(year=now.year + 1, month=1)
            else:
                try:
                    return now.replace(month=now.month + 1)
                except ValueError:
                    # 处理特殊情况，如2月30日
                    return now.replace(month=now.month + 1, day=28)
        elif billing_cycle == "年":
            try:
                return now.replace(year=now.year + 1)
            except ValueError:
                # 处理闰年特殊情况
                return now.replace(year=now.year + 1, day=28)
        else:
            # 默认为一个月
            return now + timedelta(days=30)
    
    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        验证订阅数据
        
        Args:
            data: 待验证的数据
            
        Returns:
            bool: 数据是否有效
        """
        # 检查必填字段
        if not data.get('name'):
            self.logger.error("缺少订阅名称")
            return False
        
        # 检查价格
        try:
            price = float(data.get('price', 0))
            if price < 0:
                self.logger.error("价格不能为负数")
                return False
        except (ValueError, TypeError):
            self.logger.error("价格格式不正确")
            return False
        
        # 检查计费周期
        billing_cycle = data.get('billing_cycle', '月')
        if billing_cycle not in ['周', '月', '年']:
            self.logger.warning(f"未知的计费周期: {billing_cycle}，将默认为月")
            data['billing_cycle'] = '月'
        
        return True
    
    async def query(self, filters: Optional[Dict[str, Any]] = None) -> TaskResult:
        """
        查询订阅记录
        
        Args:
            filters: 查询过滤条件
            
        Returns:
            TaskResult: 查询结果
        """
        try:
            filter_condition = None
            sorts = [{"property": "下次计费", "direction": "ascending"}]
            
            if filters:
                filter_parts = []
                
                # 按状态过滤
                if 'status' in filters:
                    filter_parts.append({
                        "property": "状态",
                        "select": {"equals": filters['status']}
                    })
                
                # 按分类过滤
                if 'category' in filters:
                    filter_parts.append({
                        "property": "分类",
                        "select": {"equals": filters['category']}
                    })
                
                # 按计费周期过滤
                if 'billing_cycle' in filters:
                    filter_parts.append({
                        "property": "计费周期",
                        "select": {"equals": filters['billing_cycle']}
                    })
                
                # 即将到期的订阅（7天内）
                if filters.get('expiring_soon'):
                    next_week = datetime.now(timezone.utc) + timedelta(days=7)
                    filter_parts.append({
                        "property": "下次计费",
                        "date": {"on_or_before": next_week.isoformat()}
                    })
                
                # 组合过滤条件
                if len(filter_parts) == 1:
                    filter_condition = filter_parts[0]
                elif len(filter_parts) > 1:
                    filter_condition = {"and": filter_parts}
            
            # 执行查询
            results = await self.notion_client.query_database(
                database_name="subscriptions",
                filter_condition=filter_condition,
                sorts=sorts,
                limit=filters.get('limit', 20) if filters else 20
            )
            
            return TaskResult(
                success=True,
                data={"records": results, "count": len(results)},
                message=f"找到 {len(results)} 条订阅记录"
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="查询订阅记录失败"
            )
    
    async def delete_all(self) -> TaskResult:
        """
        删除所有订阅记录
        
        Returns:
            TaskResult: 删除结果
        """
        try:
            # 先查询所有订阅记录
            all_subscriptions = await self.notion_client.query_database(
                database_name="subscriptions",
                filter_condition=None,
                sorts=None,
                limit=None  # 获取所有记录
            )
            
            if not all_subscriptions:
                return TaskResult(
                    success=True,
                    data={"deleted_count": 0},
                    message="没有订阅记录需要删除"
                )
            
            # 删除所有记录
            deleted_count = 0
            failed_count = 0
            
            for subscription in all_subscriptions:
                page_id = subscription.get("id")
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
                    message=f"已成功删除 {deleted_count} 条订阅记录"
                )
            else:
                return TaskResult(
                    success=True,  # 部分成功也算成功
                    data={"deleted_count": deleted_count, "failed_count": failed_count},
                    message=f"删除了 {deleted_count} 条订阅记录，{failed_count} 条删除失败"
                )
            
        except Exception as e:
            self.logger.error(f"删除所有订阅记录失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="删除订阅记录过程中出现错误"
            )
    
    def get_required_fields(self) -> List[str]:
        """获取必填字段"""
        return ['name', 'price', 'billing_cycle']
    
    def get_optional_fields(self) -> List[str]:
        """获取可选字段"""
        return ['category', 'description', 'next_billing_date']
    
    def get_task_description(self) -> str:
        """获取任务描述"""
        return "记录和管理订阅服务信息"
    
    def format_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化订阅数据"""
        formatted_data = super().format_data(data)
        
        # 确保价格为浮点数
        if 'price' in formatted_data:
            try:
                formatted_data['price'] = float(formatted_data['price'])
            except (ValueError, TypeError):
                formatted_data['price'] = 0.0
        
        # 确保计费周期有效
        if 'billing_cycle' not in formatted_data or formatted_data['billing_cycle'] not in ['周', '月', '年']:
            formatted_data['billing_cycle'] = '月'
        
        # 设置默认分类
        if 'category' not in formatted_data or not formatted_data['category']:
            formatted_data['category'] = '其他'
        
        return formatted_data
    
    async def get_upcoming_renewals(self, days: int = 7) -> TaskResult:
        """
        获取即将续费的订阅
        
        Args:
            days: 提前天数
            
        Returns:
            TaskResult: 即将续费的订阅列表
        """
        try:
            filters = {
                'expiring_soon': True,
                'status': '活跃'
            }
            
            query_result = await self.query(filters)
            
            if not query_result.success:
                return query_result
            
            records = query_result.data.get('records', [])
            
            # 过滤出真正即将到期的
            upcoming = []
            cutoff_date = datetime.now(timezone.utc) + timedelta(days=days)
            
            for record in records:
                next_billing_str = record.get('下次计费')
                if next_billing_str:
                    try:
                        next_billing = datetime.fromisoformat(next_billing_str.replace('Z', '+00:00'))
                        if next_billing <= cutoff_date:
                            upcoming.append(record)
                    except (ValueError, AttributeError):
                        continue
            
            return TaskResult(
                success=True,
                data={"upcoming_renewals": upcoming, "count": len(upcoming)},
                message=f"找到 {len(upcoming)} 个即将在 {days} 天内续费的订阅"
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="获取即将续费订阅失败"
            )
    
    async def get_monthly_cost(self) -> TaskResult:
        """
        计算月度订阅成本
        
        Returns:
            TaskResult: 月度成本统计
        """
        try:
            # 查询所有活跃订阅
            filters = {'status': '活跃'}
            query_result = await self.query(filters)
            
            if not query_result.success:
                return query_result
            
            records = query_result.data.get('records', [])
            
            # 计算月度等价成本
            monthly_cost = 0.0
            cost_by_category = {}
            
            for record in records:
                price = record.get('价格', 0) or 0
                billing_cycle = record.get('计费周期', '月')
                category = record.get('分类', '其他')
                
                # 转换为月度成本
                if billing_cycle == '周':
                    monthly_equivalent = price * 4.33  # 一个月约4.33周
                elif billing_cycle == '年':
                    monthly_equivalent = price / 12
                else:  # 月
                    monthly_equivalent = price
                
                monthly_cost += monthly_equivalent
                
                # 按分类统计
                if category not in cost_by_category:
                    cost_by_category[category] = 0.0
                cost_by_category[category] += monthly_equivalent
            
            stats = {
                'total_monthly_cost': round(monthly_cost, 2),
                'annual_cost': round(monthly_cost * 12, 2),
                'subscription_count': len(records),
                'cost_by_category': {k: round(v, 2) for k, v in cost_by_category.items()}
            }
            
            return TaskResult(
                success=True,
                data=stats,
                message=f"当前月度订阅成本：{stats['total_monthly_cost']}元，年度成本：{stats['annual_cost']}元"
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="计算订阅成本失败"
            )
    
    async def cancel_subscription(self, subscription_id: str) -> TaskResult:
        """
        取消订阅
        
        Args:
            subscription_id: 订阅ID
            
        Returns:
            TaskResult: 操作结果
        """
        try:
            success = await self.notion_client.update_page(
                page_id=subscription_id,
                properties={"状态": "已取消"}
            )
            
            if success:
                return TaskResult(
                    success=True,
                    data={"subscription_id": subscription_id},
                    message="订阅已取消"
                )
            else:
                return TaskResult(
                    success=False,
                    error="更新订阅状态失败",
                    message="取消订阅失败"
                )
                
        except Exception as e:
            return TaskResult(
                success=False,
                error=str(e),
                message="取消订阅过程中出现错误"
            ) 