"""
任务分发器
负责管理和执行各种任务
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from ..tasks.base_task import BaseTask, TaskFactory, TaskResult


class TaskDispatcher:
    """
    任务分发器
    负责任务的创建、执行、查询和管理
    """
    
    def __init__(self):
        """初始化任务分发器"""
        # 任务执行历史（简单实现，生产环境建议使用数据库）
        self.task_history = {}
        
        logger.info("任务分发器初始化完成")
    
    async def execute_task(
        self, 
        task_type: str, 
        task_data: Dict[str, Any], 
        user_id: str
    ) -> TaskResult:
        """
        执行指定类型的任务
        
        Args:
            task_type: 任务类型
            task_data: 任务数据
            user_id: 用户ID
            
        Returns:
            TaskResult: 任务执行结果
        """
        try:
            logger.info(f"执行任务: {task_type}, 用户: {user_id}")
            
            # 创建任务实例
            task = TaskFactory.create_task(task_type)
            if not task:
                return TaskResult(
                    success=False,
                    error=f"未知的任务类型: {task_type}",
                    message="不支持的任务类型"
                )
            
            # 记录任务开始
            execution_id = self._record_task_start(task_type, task_data, user_id)
            
            # 执行任务
            result = await task.safe_execute(task_data)
            
            # 记录任务结果
            self._record_task_result(execution_id, result)
            
            logger.info(f"任务执行完成: {task_type}, 成功: {result.success}")
            return result
            
        except Exception as e:
            logger.error(f"任务分发失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="任务执行过程中出现了系统错误"
            )
    
    async def query_data(
        self, 
        data_type: str, 
        filters: Optional[Dict[str, Any]] = None,
        user_id: str = ""
    ) -> TaskResult:
        """
        查询指定类型的数据
        
        Args:
            data_type: 数据类型
            filters: 查询过滤条件
            user_id: 用户ID
            
        Returns:
            TaskResult: 查询结果
        """
        try:
            logger.info(f"查询数据: {data_type}, 用户: {user_id}")
            
            # 创建任务实例
            task = TaskFactory.create_task(data_type)
            if not task:
                return TaskResult(
                    success=False,
                    error=f"未知的数据类型: {data_type}",
                    message="不支持的查询类型"
                )
            
            # 执行查询
            result = await task.query(filters)
            
            logger.info(f"数据查询完成: {data_type}, 成功: {result.success}")
            return result
            
        except Exception as e:
            logger.error(f"数据查询失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="查询过程中出现了系统错误"
            )
    
    async def delete_all_data(
        self, 
        data_type: str, 
        user_id: str = ""
    ) -> TaskResult:
        """
        删除指定类型的所有数据
        
        Args:
            data_type: 数据类型
            user_id: 用户ID
            
        Returns:
            TaskResult: 删除结果
        """
        try:
            logger.info(f"删除所有数据: {data_type}, 用户: {user_id}")
            
            # 创建任务实例
            task = TaskFactory.create_task(data_type)
            if not task:
                return TaskResult(
                    success=False,
                    error=f"未知的数据类型: {data_type}",
                    message="不支持的删除类型"
                )
            
            # 执行删除操作
            result = await task.delete_all()
            
            logger.info(f"删除操作完成: {data_type}, 成功: {result.success}")
            return result
            
        except Exception as e:
            logger.error(f"删除操作失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="删除过程中出现了系统错误"
            )
    
    async def update_task_status(
        self,
        data_type: str,
        task_name: str,
        new_status: str = "",
        new_priority: str = "",
        new_date: str = "",
        user_id: str = ""
    ) -> TaskResult:
        """
        更新任务状态
        
        Args:
            data_type: 数据类型
            task_name: 任务名称
            new_status: 新状态
            new_priority: 新优先级
            new_date: 新截止日期
            user_id: 用户ID
            
        Returns:
            TaskResult: 更新结果
        """
        try:
            logger.info(f"更新任务状态: {data_type}, 任务: {task_name}, 用户: {user_id}")
            
            # 创建任务实例
            task = TaskFactory.create_task(data_type)
            if not task:
                return TaskResult(
                    success=False,
                    error=f"未知的数据类型: {data_type}",
                    message="不支持的更新类型"
                )
            
            # 执行更新操作
            result = await task.update_by_name(task_name, new_status, new_priority, new_date)
            
            logger.info(f"任务更新完成: {data_type}, 成功: {result.success}")
            return result
            
        except Exception as e:
            logger.error(f"任务更新失败: {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message="更新过程中出现了系统错误"
            )
    
    async def batch_execute_tasks(
        self, 
        tasks: List[Dict[str, Any]], 
        user_id: str
    ) -> List[TaskResult]:
        """
        批量执行任务
        
        Args:
            tasks: 任务列表，每个任务包含 type 和 data
            user_id: 用户ID
            
        Returns:
            List[TaskResult]: 执行结果列表
        """
        try:
            logger.info(f"批量执行 {len(tasks)} 个任务, 用户: {user_id}")
            
            # 并发执行任务
            task_coroutines = [
                self.execute_task(task["type"], task["data"], user_id)
                for task in tasks
            ]
            
            results = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            # 处理异常结果
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append(TaskResult(
                        success=False,
                        error=str(result),
                        message=f"第 {i+1} 个任务执行失败"
                    ))
                else:
                    processed_results.append(result)
            
            success_count = sum(1 for r in processed_results if r.success)
            logger.info(f"批量任务执行完成: {success_count}/{len(tasks)} 成功")
            
            return processed_results
            
        except Exception as e:
            logger.error(f"批量任务执行失败: {e}")
            return [TaskResult(
                success=False,
                error=str(e),
                message="批量任务执行过程中出现了系统错误"
            )]
    
    async def get_task_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务执行状态
        
        Args:
            execution_id: 执行ID
            
        Returns:
            Optional[Dict]: 任务状态信息
        """
        return self.task_history.get(execution_id)
    
    async def get_user_task_history(
        self, 
        user_id: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取用户任务执行历史
        
        Args:
            user_id: 用户ID
            limit: 返回记录限制
            
        Returns:
            List[Dict]: 任务历史记录
        """
        try:
            user_tasks = [
                task for task in self.task_history.values()
                if task.get("user_id") == user_id
            ]
            
            # 按时间倒序排列
            user_tasks.sort(key=lambda x: x.get("start_time", ""), reverse=True)
            
            return user_tasks[:limit]
            
        except Exception as e:
            logger.error(f"获取用户任务历史失败: {e}")
            return []
    
    async def get_task_statistics(self, user_id: str = "") -> Dict[str, Any]:
        """
        获取任务执行统计
        
        Args:
            user_id: 用户ID，空则统计所有用户
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            # 过滤任务
            tasks = list(self.task_history.values())
            if user_id:
                tasks = [task for task in tasks if task.get("user_id") == user_id]
            
            # 统计分析
            total_tasks = len(tasks)
            successful_tasks = len([task for task in tasks if task.get("success", False)])
            failed_tasks = total_tasks - successful_tasks
            
            # 按类型统计
            type_stats = {}
            for task in tasks:
                task_type = task.get("task_type", "unknown")
                if task_type not in type_stats:
                    type_stats[task_type] = {"total": 0, "success": 0, "failed": 0}
                
                type_stats[task_type]["total"] += 1
                if task.get("success", False):
                    type_stats[task_type]["success"] += 1
                else:
                    type_stats[task_type]["failed"] += 1
            
            # 最近活跃时间
            recent_tasks = [
                task for task in tasks
                if task.get("start_time") and 
                datetime.fromisoformat(task["start_time"]).date() == datetime.now().date()
            ]
            
            stats = {
                "total_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": round(successful_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0,
                "type_statistics": type_stats,
                "today_tasks": len(recent_tasks),
                "available_task_types": TaskFactory.get_available_task_types()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取任务统计失败: {e}")
            return {}
    
    async def validate_task_data(
        self, 
        task_type: str, 
        task_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        验证任务数据
        
        Args:
            task_type: 任务类型
            task_data: 任务数据
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误消息列表)
        """
        try:
            task = TaskFactory.create_task(task_type)
            if not task:
                return False, [f"未知的任务类型: {task_type}"]
            
            # 检查必填字段
            required_fields = task.get_required_fields()
            errors = []
            
            for field in required_fields:
                if field not in task_data or not task_data[field]:
                    errors.append(f"缺少必填字段: {field}")
            
            # 使用任务的验证方法
            if not errors:
                is_valid = await task.validate_data(task_data)
                if not is_valid:
                    errors.append("任务数据验证失败")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"任务数据验证失败: {e}")
            return False, [f"验证过程中出现错误: {str(e)}"]
    
    def get_available_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有可用的任务类型及其信息
        
        Returns:
            Dict[str, Dict]: 任务类型信息
        """
        available_tasks = {}
        
        for task_type in TaskFactory.get_available_task_types():
            task_info = TaskFactory.get_task_info(task_type)
            if task_info:
                available_tasks[task_type] = task_info
        
        return available_tasks
    
    def _record_task_start(
        self, 
        task_type: str, 
        task_data: Dict[str, Any], 
        user_id: str
    ) -> str:
        """
        记录任务开始
        
        Args:
            task_type: 任务类型
            task_data: 任务数据
            user_id: 用户ID
            
        Returns:
            str: 执行ID
        """
        execution_id = f"{user_id}_{task_type}_{datetime.now().timestamp()}"
        
        self.task_history[execution_id] = {
            "execution_id": execution_id,
            "task_type": task_type,
            "user_id": user_id,
            "task_data": task_data,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running"
        }
        
        return execution_id
    
    def _record_task_result(self, execution_id: str, result: TaskResult) -> None:
        """
        记录任务结果
        
        Args:
            execution_id: 执行ID
            result: 任务结果
        """
        if execution_id in self.task_history:
            self.task_history[execution_id].update({
                "end_time": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "success": result.success,
                "result_data": result.data,
                "message": result.message,
                "error": result.error
            })
    
    async def cleanup_old_history(self, days_to_keep: int = 30) -> None:
        """
        清理旧的任务历史记录
        
        Args:
            days_to_keep: 保留天数
        """
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (days_to_keep * 24 * 3600)
            
            old_executions = [
                execution_id for execution_id, task in self.task_history.items()
                if task.get("start_time") and 
                datetime.fromisoformat(task["start_time"]).timestamp() < cutoff_time
            ]
            
            for execution_id in old_executions:
                del self.task_history[execution_id]
            
            if old_executions:
                logger.info(f"清理了 {len(old_executions)} 条旧的任务历史记录")
                
        except Exception as e:
            logger.error(f"清理任务历史失败: {e}") 