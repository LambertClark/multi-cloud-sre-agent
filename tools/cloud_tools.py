"""
云服务工具注册表
统一管理所有云平台的工具
"""
from typing import Dict, Any, List, Callable, Optional
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


class CloudToolRegistry:
    """云服务工具注册表"""

    def __init__(self):
        self.tools: Dict[str, Dict[str, Callable]] = {}
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self,
        cloud_provider: str,
        service: str,
        operation: str,
        tool_func: Callable,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        注册工具

        Args:
            cloud_provider: 云平台 (aws, azure, gcp, aliyun, volc)
            service: 服务名称 (cloudwatch, monitor, etc)
            operation: 操作名称
            tool_func: 工具函数
            metadata: 工具元数据
        """
        key = f"{cloud_provider}.{service}"

        if key not in self.tools:
            self.tools[key] = {}
            self.tool_metadata[key] = {}

        self.tools[key][operation] = tool_func
        self.tool_metadata[key][operation] = metadata or {}

        logger.info(f"Registered tool: {key}.{operation}")

    def get_tool(self, cloud_provider: str, service: str, operation: str) -> Optional[Callable]:
        """获取工具"""
        key = f"{cloud_provider}.{service}"
        return self.tools.get(key, {}).get(operation)

    def has_tool(self, cloud_provider: str, service: str, operation: str) -> bool:
        """检查工具是否存在"""
        return self.get_tool(cloud_provider, service, operation) is not None

    def list_tools(self, cloud_provider: Optional[str] = None, service: Optional[str] = None) -> List[str]:
        """
        列出工具

        Args:
            cloud_provider: 可选，过滤云平台
            service: 可选，过滤服务

        Returns:
            工具名称列表
        """
        tools = []

        for key, operations in self.tools.items():
            provider, svc = key.split(".")

            # 过滤
            if cloud_provider and provider != cloud_provider:
                continue
            if service and svc != service:
                continue

            for operation in operations.keys():
                tools.append(f"{key}.{operation}")

        return tools

    async def call(
        self,
        cloud_provider: str,
        service: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用工具

        Args:
            cloud_provider: 云平台
            service: 服务
            operation: 操作
            parameters: 参数

        Returns:
            执行结果
        """
        tool_func = self.get_tool(cloud_provider, service, operation)

        if tool_func is None:
            return {
                "success": False,
                "error": f"Tool not found: {cloud_provider}.{service}.{operation}"
            }

        try:
            # 调用工具函数
            result = await tool_func(**parameters)
            return {
                "success": True,
                "data": result
            }
        except Exception as e:
            logger.error(f"Error calling tool {cloud_provider}.{service}.{operation}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_all_langchain_tools(self) -> List[Callable]:
        """获取所有工具作为LangChain工具列表"""
        all_tools = []

        for key, operations in self.tools.items():
            for tool_func in operations.values():
                all_tools.append(tool_func)

        return all_tools


# 全局工具注册表实例
tool_registry = CloudToolRegistry()


def get_tool_registry() -> CloudToolRegistry:
    """获取全局工具注册表"""
    return tool_registry
