"""
Notion API 客户端
处理与Notion数据库的所有交互
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from notion_client import Client
from notion_client.helpers import collect_paginated_api
from loguru import logger
from ..config.settings import settings


class NotionClient:
    """
    Notion API 客户端
    提供对Notion数据库的CRUD操作
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化Notion客户端
        
        Args:
            token: Notion集成令牌，如果不提供则从配置中获取
        """
        self.token = token or settings.notion.token
        if not self.token:
            raise ValueError("Notion令牌未配置")
        
        self.client = Client(auth=self.token)
        self.databases = settings.notion.databases
        
        logger.info("Notion客户端初始化完成")
    
    async def test_connection(self) -> bool:
        """
        测试Notion连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 获取用户信息来测试连接
            user = self.client.users.me()
            logger.info(f"Notion连接成功，用户: {user.get('name', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Notion连接失败: {e}")
            return False
    
    def _format_property_value(self, prop_type: str, value: Any) -> Dict[str, Any]:
        """
        格式化属性值为Notion API格式
        
        Args:
            prop_type: 属性类型
            value: 属性值
            
        Returns:
            Dict: 格式化后的属性值
        """
        if prop_type == "title":
            return {"title": [{"text": {"content": str(value)}}]}
        elif prop_type == "rich_text":
            return {"rich_text": [{"text": {"content": str(value)}}]}
        elif prop_type == "number":
            return {"number": float(value) if value is not None else None}
        elif prop_type == "select":
            return {"select": {"name": str(value)} if value else None}
        elif prop_type == "multi_select":
            if isinstance(value, list):
                return {"multi_select": [{"name": str(v)} for v in value]}
            else:
                return {"multi_select": [{"name": str(value)}]}
        elif prop_type == "date":
            if isinstance(value, datetime):
                return {"date": {"start": value.isoformat()}}
            elif isinstance(value, str):
                return {"date": {"start": value}}
            else:
                return {"date": None}
        elif prop_type == "checkbox":
            return {"checkbox": bool(value)}
        elif prop_type == "url":
            return {"url": str(value) if value else None}
        elif prop_type == "email":
            return {"email": str(value) if value else None}
        elif prop_type == "phone_number":
            return {"phone_number": str(value) if value else None}
        else:
            # 默认作为富文本处理
            return {"rich_text": [{"text": {"content": str(value)}}]}
    
    def _extract_property_value(self, prop: Dict[str, Any]) -> Any:
        """
        从Notion属性中提取值
        
        Args:
            prop: Notion属性对象
            
        Returns:
            Any: 提取的值
        """
        prop_type = prop.get("type")
        
        if prop_type == "title":
            title_list = prop.get("title", [])
            return "".join([item.get("plain_text", "") for item in title_list])
        elif prop_type == "rich_text":
            rich_text_list = prop.get("rich_text", [])
            return "".join([item.get("plain_text", "") for item in rich_text_list])
        elif prop_type == "number":
            return prop.get("number")
        elif prop_type == "select":
            select_obj = prop.get("select")
            return select_obj.get("name") if select_obj else None
        elif prop_type == "multi_select":
            multi_select_list = prop.get("multi_select", [])
            return [item.get("name") for item in multi_select_list]
        elif prop_type == "date":
            date_obj = prop.get("date")
            if date_obj:
                return date_obj.get("start")
            return None
        elif prop_type == "checkbox":
            return prop.get("checkbox", False)
        elif prop_type == "url":
            return prop.get("url")
        elif prop_type == "email":
            return prop.get("email")
        elif prop_type == "phone_number":
            return prop.get("phone_number")
        elif prop_type == "created_time":
            return prop.get("created_time")
        elif prop_type == "last_edited_time":
            return prop.get("last_edited_time")
        else:
            return None
    
    async def create_page(self, database_name: str, properties: Dict[str, Any]) -> Optional[str]:
        """
        在指定数据库中创建新页面
        
        Args:
            database_name: 数据库名称 (accounting, subscriptions, todos)
            properties: 页面属性
            
        Returns:
            Optional[str]: 创建的页面ID，失败返回None
        """
        try:
            database_id = self.databases.get(database_name)
            if not database_id:
                logger.error(f"数据库 '{database_name}' 未配置")
                return None
            
            # 获取数据库架构来确定属性类型
            database_info = self.client.databases.retrieve(database_id=database_id)
            db_properties = database_info.get("properties", {})
            
            # 格式化属性
            formatted_properties = {}
            for prop_name, prop_value in properties.items():
                if prop_name in db_properties:
                    prop_type = db_properties[prop_name].get("type")
                    formatted_properties[prop_name] = self._format_property_value(prop_type, prop_value)
                else:
                    logger.warning(f"属性 '{prop_name}' 在数据库 '{database_name}' 中不存在")
            
            # 创建页面
            response = self.client.pages.create(
                parent={"database_id": database_id},
                properties=formatted_properties
            )
            
            page_id = response.get("id")
            logger.info(f"在数据库 '{database_name}' 中创建页面成功: {page_id}")
            return page_id
            
        except Exception as e:
            logger.error(f"创建页面失败: {e}")
            return None
    
    async def query_database(
        self, 
        database_name: str, 
        filter_condition: Optional[Dict] = None,
        sorts: Optional[List[Dict]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        查询数据库
        
        Args:
            database_name: 数据库名称
            filter_condition: 过滤条件
            sorts: 排序条件
            limit: 结果限制数量
            
        Returns:
            List[Dict]: 查询结果
        """
        try:
            database_id = self.databases.get(database_name)
            if not database_id:
                logger.error(f"数据库 '{database_name}' 未配置")
                return []
            
            query_params = {
                "database_id": database_id
            }
            
            if filter_condition:
                query_params["filter"] = filter_condition
            if sorts:
                query_params["sorts"] = sorts
            if limit:
                query_params["page_size"] = min(limit, 100)  # Notion API限制
            
            # 执行查询
            if limit and limit <= 100:
                response = self.client.databases.query(**query_params)
                results = response.get("results", [])
            else:
                # 使用分页收集所有结果
                results = collect_paginated_api(
                    self.client.databases.query,
                    **query_params
                )
            
            # 解析结果
            parsed_results = []
            for page in results:
                page_data = {
                    "id": page.get("id"),
                    "created_time": page.get("created_time"),
                    "last_edited_time": page.get("last_edited_time"),
                    "url": page.get("url")
                }
                
                # 解析属性
                properties = page.get("properties", {})
                for prop_name, prop_value in properties.items():
                    page_data[prop_name] = self._extract_property_value(prop_value)
                
                parsed_results.append(page_data)
            
            logger.info(f"查询数据库 '{database_name}' 成功，返回 {len(parsed_results)} 条记录")
            return parsed_results
            
        except Exception as e:
            logger.error(f"查询数据库失败: {e}")
            return []
    
    async def update_page(self, page_id: str, properties: Dict[str, Any]) -> bool:
        """
        更新页面属性
        
        Args:
            page_id: 页面ID
            properties: 要更新的属性
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 先获取页面信息来确定属性类型
            page_info = self.client.pages.retrieve(page_id=page_id)
            parent = page_info.get("parent", {})
            
            if parent.get("type") == "database_id":
                database_id = parent.get("database_id")
                database_info = self.client.databases.retrieve(database_id=database_id)
                db_properties = database_info.get("properties", {})
                
                # 格式化属性
                formatted_properties = {}
                for prop_name, prop_value in properties.items():
                    if prop_name in db_properties:
                        prop_type = db_properties[prop_name].get("type")
                        formatted_properties[prop_name] = self._format_property_value(prop_type, prop_value)
                
                # 更新页面
                self.client.pages.update(
                    page_id=page_id,
                    properties=formatted_properties
                )
                
                logger.info(f"更新页面成功: {page_id}")
                return True
            else:
                logger.error(f"页面 {page_id} 不在数据库中")
                return False
                
        except Exception as e:
            logger.error(f"更新页面失败: {e}")
            return False
    
    async def delete_page(self, page_id: str) -> bool:
        """
        删除页面（实际上是归档）
        
        Args:
            page_id: 页面ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            self.client.pages.update(
                page_id=page_id,
                archived=True
            )
            logger.info(f"归档页面成功: {page_id}")
            return True
        except Exception as e:
            logger.error(f"归档页面失败: {e}")
            return False
    
    # 特定任务的便捷方法
    
    async def add_accounting_entry(
        self, 
        title: str, 
        amount: float, 
        category: str,
        date: Optional[datetime] = None,
        description: str = "",
        type_: str = "支出"
    ) -> Optional[str]:
        """
        添加记账记录
        
        Args:
            title: 记录标题
            amount: 金额
            category: 分类
            date: 日期，默认为当前时间
            description: 描述
            type_: 类型（收入/支出）
            
        Returns:
            Optional[str]: 创建的页面ID
        """
        if date is None:
            date = datetime.now(timezone.utc)
        
        properties = {
            "标题": title,
            "金额": amount,
            "分类": category,
            "日期": date,
            "描述": description,
            "类型": type_
        }
        
        return await self.create_page("accounting", properties)
    
    async def add_subscription(
        self,
        name: str,
        price: float,
        billing_cycle: str,
        next_billing: datetime,
        category: str = "",
        description: str = ""
    ) -> Optional[str]:
        """
        添加订阅记录
        
        Args:
            name: 订阅名称
            price: 价格
            billing_cycle: 计费周期
            next_billing: 下次计费日期
            category: 分类
            description: 描述
            
        Returns:
            Optional[str]: 创建的页面ID
        """
        properties = {
            "名称": name,
            "价格": price,
            "计费周期": billing_cycle,
            "下次计费": next_billing,
            "分类": category,
            "描述": description,
            "状态": "活跃"
        }
        
        return await self.create_page("subscriptions", properties)
    
    async def add_todo(
        self,
        title: str,
        priority: str = "中",
        due_date: Optional[datetime] = None,
        category: str = "",
        description: str = ""
    ) -> Optional[str]:
        """
        添加待办事项
        
        Args:
            title: 待办标题
            priority: 优先级
            due_date: 截止日期
            category: 分类
            description: 描述
            
        Returns:
            Optional[str]: 创建的页面ID
        """
        properties = {
            "标题": title,
            "优先级": priority,
            "状态": "待完成",
            "分类": category,
            "描述": description
        }
        
        if due_date:
            properties["截止日期"] = due_date
        
        return await self.create_page("todos", properties) 