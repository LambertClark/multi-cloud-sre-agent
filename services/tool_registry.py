"""
工具注册表
管理Agent生成的可复用工具，实现工具发现、调用和质量评分
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import os
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolStatus(Enum):
    """工具状态"""
    ACTIVE = "active"  # 活跃可用
    DEPRECATED = "deprecated"  # 已废弃
    FAILED = "failed"  # 失败（质量不达标）


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
            "default": self.default
        }


@dataclass
class ToolMetrics:
    """工具质量指标"""
    total_calls: int = 0  # 总调用次数
    successful_calls: int = 0  # 成功次数
    failed_calls: int = 0  # 失败次数
    average_execution_time: float = 0.0  # 平均执行时间（秒）
    last_used: Optional[str] = None  # 最后使用时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def quality_score(self) -> float:
        """
        质量评分（0-100）

        计算公式：
        - 成功率权重：70%
        - 使用频率权重：20%
        - 执行速度权重：10%
        """
        # 成功率分数（0-70）
        success_score = self.success_rate * 70

        # 使用频率分数（0-20），基于对数刻度
        import math
        if self.total_calls > 0:
            frequency_score = min(20, math.log10(self.total_calls + 1) * 10)
        else:
            frequency_score = 0

        # 执行速度分数（0-10），越快越好
        if self.average_execution_time > 0:
            # 假设理想执行时间为1秒，超过5秒得0分
            speed_score = max(0, 10 - (self.average_execution_time - 1) * 2)
        else:
            speed_score = 5  # 没有数据时给中等分

        return success_score + frequency_score + speed_score

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "average_execution_time": self.average_execution_time,
            "success_rate": self.success_rate,
            "quality_score": self.quality_score,
            "last_used": self.last_used,
            "created_at": self.created_at
        }


@dataclass
class GeneratedTool:
    """
    生成的工具定义

    工具是Agent生成的可复用代码，包含完整的元信息
    """
    name: str  # 工具名称（唯一标识）
    description: str  # 工具描述
    code: str  # 工具代码
    test_code: str  # 测试代码
    parameters: List[ToolParameter]  # 参数列表
    return_type: str  # 返回类型
    cloud_provider: str  # 云平台（aws/azure/gcp/kubernetes）
    service: str  # 服务名称（ec2/s3/monitor等）
    category: str  # 分类（query/monitor/diagnostic等）
    tags: List[str] = field(default_factory=list)  # 标签
    version: str = "1.0.0"  # 版本号
    status: ToolStatus = ToolStatus.ACTIVE  # 状态
    metrics: ToolMetrics = field(default_factory=ToolMetrics)  # 质量指标
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元信息

    @property
    def tool_id(self) -> str:
        """工具唯一ID（基于名称和版本的哈希）"""
        content = f"{self.name}:{self.version}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    @property
    def code_hash(self) -> str:
        """代码哈希（用于检测代码变化）"""
        return hashlib.md5(self.code.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "test_code": self.test_code,
            "parameters": [p.to_dict() for p in self.parameters],
            "return_type": self.return_type,
            "cloud_provider": self.cloud_provider,
            "service": self.service,
            "category": self.category,
            "tags": self.tags,
            "version": self.version,
            "status": self.status.value,
            "metrics": self.metrics.to_dict(),
            "metadata": self.metadata,
            "tool_id": self.tool_id,
            "code_hash": self.code_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedTool":
        """从字典创建（用于反序列化）"""
        # 重建ToolParameter列表
        parameters = [
            ToolParameter(**p) for p in data.get("parameters", [])
        ]

        # 重建ToolMetrics
        metrics_data = data.get("metrics", {})
        metrics = ToolMetrics(
            total_calls=metrics_data.get("total_calls", 0),
            successful_calls=metrics_data.get("successful_calls", 0),
            failed_calls=metrics_data.get("failed_calls", 0),
            average_execution_time=metrics_data.get("average_execution_time", 0.0),
            last_used=metrics_data.get("last_used"),
            created_at=metrics_data.get("created_at", datetime.now().isoformat())
        )

        return cls(
            name=data["name"],
            description=data["description"],
            code=data["code"],
            test_code=data.get("test_code", ""),
            parameters=parameters,
            return_type=data.get("return_type", "Any"),
            cloud_provider=data.get("cloud_provider", "unknown"),
            service=data.get("service", "unknown"),
            category=data.get("category", "query"),
            tags=data.get("tags", []),
            version=data.get("version", "1.0.0"),
            status=ToolStatus(data.get("status", "active")),
            metrics=metrics,
            metadata=data.get("metadata", {})
        )


class ToolRegistry:
    """
    工具注册表

    功能：
    1. 注册新工具
    2. 查询工具
    3. 更新工具指标
    4. 持久化工具
    5. 工具推荐
    """

    def __init__(self, registry_dir: str = "generated/tools"):
        """
        Args:
            registry_dir: 工具注册表目录
        """
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        # 工具索引文件
        self.index_file = self.registry_dir / "tool_index.json"

        # 内存中的工具缓存
        self.tools: Dict[str, GeneratedTool] = {}

        # 加载现有工具
        self._load_tools()

    def _load_tools(self):
        """从磁盘加载工具索引"""
        if not self.index_file.exists():
            logger.info("工具索引文件不存在，创建新索引")
            self._save_index()
            return

        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)

            for tool_data in index_data.get("tools", []):
                tool = GeneratedTool.from_dict(tool_data)
                self.tools[tool.name] = tool

            logger.info(f"加载了 {len(self.tools)} 个工具")

        except Exception as e:
            logger.error(f"加载工具索引失败: {e}")
            self.tools = {}

    def _save_index(self):
        """保存工具索引到磁盘"""
        try:
            index_data = {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "total_tools": len(self.tools),
                "tools": [tool.to_dict() for tool in self.tools.values()]
            }

            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)

            logger.info(f"保存了 {len(self.tools)} 个工具到索引")

        except Exception as e:
            logger.error(f"保存工具索引失败: {e}")

    def _save_tool_code(self, tool: GeneratedTool):
        """保存工具代码到独立文件"""
        try:
            # 创建工具目录: generated/tools/{cloud_provider}/{service}/
            tool_dir = self.registry_dir / tool.cloud_provider / tool.service
            tool_dir.mkdir(parents=True, exist_ok=True)

            # 保存代码文件
            code_file = tool_dir / f"{tool.name}.py"
            with open(code_file, 'w', encoding='utf-8') as f:
                # 添加头部注释
                f.write(f'"""\n')
                f.write(f'{tool.description}\n\n')
                f.write(f'工具ID: {tool.tool_id}\n')
                f.write(f'版本: {tool.version}\n')
                f.write(f'生成时间: {tool.metrics.created_at}\n')
                f.write(f'"""\n\n')
                f.write(tool.code)

            # 保存测试代码
            if tool.test_code:
                test_file = tool_dir / f"test_{tool.name}.py"
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write(tool.test_code)

            logger.info(f"保存工具代码: {code_file}")

        except Exception as e:
            logger.error(f"保存工具代码失败: {e}")

    def register(self, tool: GeneratedTool, force_update: bool = False) -> Dict[str, Any]:
        """
        注册新工具

        Args:
            tool: 工具对象
            force_update: 强制更新（即使代码相同）

        Returns:
            注册结果
        """
        is_update = False

        # 检查是否已存在同名工具
        if tool.name in self.tools:
            existing_tool = self.tools[tool.name]

            # 如果代码相同且不强制更新，不需要注册
            if existing_tool.code_hash == tool.code_hash and not force_update:
                return {
                    "success": False,
                    "reason": "工具已存在且代码相同",
                    "existing_tool_id": existing_tool.tool_id,
                    "version": existing_tool.version
                }

            # 代码不同或强制更新，升级版本
            logger.info(f"工具 {tool.name} 已存在，创建新版本")
            # 解析版本号并递增
            try:
                major, minor, patch = map(int, existing_tool.version.split('.'))
                tool.version = f"{major}.{minor}.{patch + 1}"
            except:
                # 如果版本号解析失败，使用默认版本
                tool.version = "1.0.1"

            is_update = True

        # 注册工具
        self.tools[tool.name] = tool

        # 保存到磁盘
        self._save_tool_code(tool)
        self._save_index()

        logger.info(
            f"{'更新' if is_update else '注册'}工具: {tool.name} (v{tool.version}) "
            f"[{tool.cloud_provider}/{tool.service}]"
        )

        return {
            "success": True,
            "tool_id": tool.tool_id,
            "tool_name": tool.name,
            "version": tool.version,
            "is_update": is_update,
            "message": f"工具 '{tool.name}' {'更新' if is_update else '注册'}成功"
        }

    def get_tool(self, name: str) -> Optional[GeneratedTool]:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            工具对象，如果不存在返回None
        """
        return self.tools.get(name)

    def search_tools(
        self,
        query: Optional[str] = None,
        cloud_provider: Optional[str] = None,
        service: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_quality_score: float = 0.0,
        limit: int = 10
    ) -> List[GeneratedTool]:
        """
        搜索工具

        Args:
            query: 查询文本（匹配名称和描述）
            cloud_provider: 云平台过滤
            service: 服务过滤
            category: 分类过滤
            tags: 标签过滤
            min_quality_score: 最小质量分数
            limit: 返回数量限制

        Returns:
            工具列表（按质量分数排序）
        """
        results = []

        for tool in self.tools.values():
            # 状态过滤
            if tool.status != ToolStatus.ACTIVE:
                continue

            # 质量分数过滤
            if tool.metrics.quality_score < min_quality_score:
                continue

            # 云平台过滤
            if cloud_provider and tool.cloud_provider != cloud_provider:
                continue

            # 服务过滤
            if service and tool.service != service:
                continue

            # 分类过滤
            if category and tool.category != category:
                continue

            # 标签过滤
            if tags and not any(tag in tool.tags for tag in tags):
                continue

            # 查询文本过滤
            if query:
                query_lower = query.lower()
                if (query_lower not in tool.name.lower() and
                    query_lower not in tool.description.lower()):
                    continue

            results.append(tool)

        # 按质量分数排序
        results.sort(key=lambda t: t.metrics.quality_score, reverse=True)

        return results[:limit]

    def update_metrics(
        self,
        tool_name: str,
        success: bool,
        execution_time: float
    ):
        """
        更新工具指标

        Args:
            tool_name: 工具名称
            success: 是否成功
            execution_time: 执行时间
        """
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"工具 {tool_name} 不存在，无法更新指标")
            return

        # 更新调用次数
        tool.metrics.total_calls += 1
        if success:
            tool.metrics.successful_calls += 1
        else:
            tool.metrics.failed_calls += 1

        # 更新平均执行时间（移动平均）
        n = tool.metrics.total_calls
        tool.metrics.average_execution_time = (
            (tool.metrics.average_execution_time * (n - 1) + execution_time) / n
        )

        # 更新最后使用时间
        tool.metrics.last_used = datetime.now().isoformat()

        # 如果质量分数太低，标记为失败
        if tool.metrics.quality_score < 20 and tool.metrics.total_calls > 10:
            tool.status = ToolStatus.FAILED
            logger.warning(f"工具 {tool_name} 质量分数过低，标记为失败")

        # 保存更新
        self._save_index()

        logger.debug(
            f"更新工具指标: {tool_name} - "
            f"成功率: {tool.metrics.success_rate:.2%}, "
            f"质量分数: {tool.metrics.quality_score:.1f}"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取注册表统计信息

        Returns:
            统计数据
        """
        total_tools = len(self.tools)
        active_tools = sum(1 for t in self.tools.values() if t.status == ToolStatus.ACTIVE)

        # 按云平台统计
        by_provider = {}
        for tool in self.tools.values():
            provider = tool.cloud_provider
            if provider not in by_provider:
                by_provider[provider] = 0
            by_provider[provider] += 1

        # 按分类统计
        by_category = {}
        for tool in self.tools.values():
            category = tool.category
            if category not in by_category:
                by_category[category] = 0
            by_category[category] += 1

        # 平均质量分数
        if total_tools > 0:
            avg_quality = sum(t.metrics.quality_score for t in self.tools.values()) / total_tools
        else:
            avg_quality = 0.0

        # Top 10工具
        top_tools = sorted(
            self.tools.values(),
            key=lambda t: t.metrics.quality_score,
            reverse=True
        )[:10]

        return {
            "total_tools": total_tools,
            "active_tools": active_tools,
            "deprecated_tools": sum(1 for t in self.tools.values() if t.status == ToolStatus.DEPRECATED),
            "failed_tools": sum(1 for t in self.tools.values() if t.status == ToolStatus.FAILED),
            "average_quality_score": avg_quality,
            "by_provider": by_provider,
            "by_category": by_category,
            "top_tools": [
                {
                    "name": t.name,
                    "quality_score": t.metrics.quality_score,
                    "total_calls": t.metrics.total_calls,
                    "success_rate": t.metrics.success_rate
                }
                for t in top_tools
            ]
        }


# 全局工具注册表实例
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry(registry_dir: str = "generated/tools") -> ToolRegistry:
    """获取全局工具注册表实例"""
    global _tool_registry

    if _tool_registry is None:
        _tool_registry = ToolRegistry(registry_dir=registry_dir)

    return _tool_registry
