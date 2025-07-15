"""
基础任务类
定义所有任务的通用接口和行为
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from loguru import logger


class TaskResult:
    """任务执行结果"""
    
    def __init__(
        self, 
        success: bool, 
        data: Optional[Dict[str, Any]] = None, 
        message: str = "",
        error: Optional[str] = None
    ):
        self.success = success
        self.data = data or {}
        self.message = message
        self.error = error
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }


class BaseTask(ABC):
    """
    基础任务类
    所有任务类都应该继承这个基类
    """
    
    def __init__(self, name: str):
        """
        初始化任务
        
        Args:
            name: 任务名称
        """
        self.name = name
        self.created_at = datetime.now(timezone.utc)
        self.logger = logger.bind(task=name)
    
    @abstractmethod
    async def execute(self, data: Dict[str, Any]) -> TaskResult:
        """
        执行任务
        
        Args:
            data: 任务所需的数据
            
        Returns:
            TaskResult: 任务执行结果
        """
        pass
    
    @abstractmethod
    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        验证任务数据的有效性
        
        Args:
            data: 待验证的数据
            
        Returns:
            bool: 数据是否有效
        """
        pass
    
    async def query(self, filters: Optional[Dict[str, Any]] = None) -> TaskResult:
        """
        查询数据（默认实现）
        
        Args:
            filters: 查询过滤条件
            
        Returns:
            TaskResult: 查询结果
        """
        # 基类提供空实现，子类可以重写
        return TaskResult(
            success=False,
            error="查询功能未实现",
            message="此任务类型不支持查询功能"
        )
    
    async def delete_all(self) -> TaskResult:
        """
        删除所有数据（默认实现）
        
        Returns:
            TaskResult: 删除结果
        """
        # 基类提供空实现，子类可以重写
        return TaskResult(
            success=False,
            error="删除功能未实现",
            message="此任务类型不支持删除功能"
        )
    
    async def update_by_name(
        self, 
        task_name: str, 
        new_status: str = "", 
        new_priority: str = "", 
        new_date: str = ""
    ) -> TaskResult:
        """
        根据任务名称更新任务状态（默认实现）
        
        Args:
            task_name: 任务名称
            new_status: 新状态
            new_priority: 新优先级  
            new_date: 新截止日期
            
        Returns:
            TaskResult: 更新结果
        """
        # 基类提供空实现，子类可以重写
        return TaskResult(
            success=False,
            error="更新功能未实现",
            message="此任务类型不支持根据名称更新功能"
        )
    
    def get_required_fields(self) -> List[str]:
        """
        获取任务所需的必填字段
        
        Returns:
            List[str]: 必填字段列表
        """
        return []
    
    def get_optional_fields(self) -> List[str]:
        """
        获取任务的可选字段
        
        Returns:
            List[str]: 可选字段列表
        """
        return []
    
    def get_task_description(self) -> str:
        """
        获取任务描述
        
        Returns:
            str: 任务描述
        """
        return f"任务类型: {self.name}"
    
    def format_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化任务数据
        
        Args:
            data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的数据
        """
        # 默认实现：移除空值和None值
        formatted_data = {}
        for key, value in data.items():
            if value is not None and value != "":
                formatted_data[key] = value
        return formatted_data
    
    def log_task_start(self, data: Dict[str, Any]) -> None:
        """记录任务开始日志"""
        self.logger.info(f"开始执行任务: {self.name}")
        self.logger.debug(f"任务数据: {data}")
    
    def log_task_success(self, result: TaskResult) -> None:
        """记录任务成功日志"""
        self.logger.info(f"任务执行成功: {self.name}")
        if result.message:
            self.logger.info(f"执行结果: {result.message}")
    
    def log_task_error(self, error: str) -> None:
        """记录任务错误日志"""
        self.logger.error(f"任务执行失败: {self.name}, 错误: {error}")
    
    async def safe_execute(self, data: Dict[str, Any]) -> TaskResult:
        """
        安全执行任务，包含错误处理和日志记录
        
        Args:
            data: 任务数据
            
        Returns:
            TaskResult: 任务执行结果
        """
        try:
            self.log_task_start(data)
            
            # 验证数据
            if not await self.validate_data(data):
                error_msg = "任务数据验证失败"
                self.log_task_error(error_msg)
                return TaskResult(
                    success=False,
                    error=error_msg,
                    message="请检查输入数据的格式和完整性"
                )
            
            # 格式化数据
            formatted_data = self.format_data(data)
            
            # 执行任务
            result = await self.execute(formatted_data)
            
            if result.success:
                self.log_task_success(result)
            else:
                self.log_task_error(result.error or "任务执行失败")
            
            return result
            
        except Exception as e:
            error_msg = f"任务执行出现异常: {str(e)}"
            self.log_task_error(error_msg)
            return TaskResult(
                success=False,
                error=error_msg,
                message="任务执行过程中出现了意外错误"
            )


class TaskFactory:
    """任务工厂类"""
    
    _task_classes = {}
    
    @classmethod
    def register_task(cls, task_type: str, task_class: type):
        """
        注册任务类
        
        Args:
            task_type: 任务类型标识
            task_class: 任务类
        """
        cls._task_classes[task_type] = task_class
        logger.info(f"注册任务类型: {task_type}")
    
    @classmethod
    def create_task(cls, task_type: str) -> Optional[BaseTask]:
        """
        创建任务实例
        
        Args:
            task_type: 任务类型
            
        Returns:
            Optional[BaseTask]: 任务实例，如果类型不存在则返回None
        """
        if task_type in cls._task_classes:
            task_class = cls._task_classes[task_type]
            return task_class()
        else:
            logger.error(f"未知的任务类型: {task_type}")
            return None
    
    @classmethod
    def get_available_task_types(cls) -> List[str]:
        """
        获取所有可用的任务类型
        
        Returns:
            List[str]: 任务类型列表
        """
        return list(cls._task_classes.keys())
    
    @classmethod
    def get_task_info(cls, task_type: str) -> Optional[Dict[str, Any]]:
        """
        获取任务类型信息
        
        Args:
            task_type: 任务类型
            
        Returns:
            Optional[Dict]: 任务信息，包括必填字段、可选字段和描述
        """
        if task_type in cls._task_classes:
            task_class = cls._task_classes[task_type]
            task_instance = task_class()
            return {
                "name": task_instance.name,
                "description": task_instance.get_task_description(),
                "required_fields": task_instance.get_required_fields(),
                "optional_fields": task_instance.get_optional_fields()
            }
        return None 