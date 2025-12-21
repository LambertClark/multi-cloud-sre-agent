"""
权限管理系统
管理生成代码对云资源的访问权限，遵循最小权限原则
"""
from typing import Dict, List, Set, Optional, Any
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """权限级别"""
    READ_ONLY = "read_only"  # 只读（查询、描述、列出）
    READ_WRITE = "read_write"  # 读写（创建、更新，但不删除）
    FULL = "full"  # 完全权限（包括删除）


class CloudProvider(Enum):
    """云服务提供商"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"
    VOLCANO = "volcano"


@dataclass
class Permission:
    """权限定义"""
    provider: CloudProvider
    service: str  # 服务名称（如：ec2, s3, monitor）
    actions: Set[str]  # 允许的操作
    level: PermissionLevel
    description: str = ""


class PermissionManager:
    """
    权限管理器

    职责：
    1. 定义不同云平台的权限策略
    2. 验证代码操作是否在允许范围内
    3. 遵循最小权限原则（默认只读）
    """

    # AWS只读操作（安全）
    AWS_READ_ONLY_ACTIONS = {
        'ec2': {
            'describe_instances', 'describe_volumes', 'describe_snapshots',
            'describe_security_groups', 'describe_vpcs', 'describe_subnets',
            'describe_regions', 'describe_availability_zones',
            'describe_instance_status', 'describe_instance_types'
        },
        's3': {
            'list_buckets', 'list_objects', 'list_objects_v2',
            'get_object', 'head_object', 'head_bucket',
            'get_bucket_location', 'get_bucket_versioning'
        },
        'cloudwatch': {
            'describe_alarms', 'describe_alarm_history',
            'get_metric_data', 'get_metric_statistics',
            'list_metrics', 'describe_anomaly_detectors'
        },
        'logs': {
            'describe_log_groups', 'describe_log_streams',
            'filter_log_events', 'get_log_events'
        },
        'xray': {
            'get_trace_graph', 'get_trace_summaries',
            'batch_get_traces', 'get_service_graph'
        }
    }

    # Azure只读操作
    AZURE_READ_ONLY_ACTIONS = {
        'monitor': {
            'list', 'get', 'list_metrics', 'list_metric_definitions',
            'activity_logs_list', 'metrics_list'
        },
        'compute': {
            'list', 'get', 'instance_view', 'list_by_resource_group'
        },
        'storage': {
            'list', 'list_keys', 'get_properties', 'list_by_resource_group'
        }
    }

    # GCP只读操作
    GCP_READ_ONLY_ACTIONS = {
        'monitoring': {
            'list_time_series', 'list_metric_descriptors',
            'get_metric_descriptor', 'list_monitored_resource_descriptors'
        },
        'compute': {
            'list', 'get', 'aggregated_list', 'list_instances'
        }
    }

    # Kubernetes只读操作
    K8S_READ_ONLY_ACTIONS = {
        'core': {
            'list_pod_for_all_namespaces', 'list_namespaced_pod',
            'read_namespaced_pod', 'read_namespaced_pod_log',
            'list_node', 'read_node', 'list_namespace',
            'list_namespaced_service', 'list_namespaced_config_map'
        },
        'apps': {
            'list_namespaced_deployment', 'read_namespaced_deployment',
            'list_namespaced_replica_set', 'list_namespaced_stateful_set'
        },
        'batch': {
            'list_namespaced_job', 'read_namespaced_job',
            'list_namespaced_cron_job'
        }
    }

    # 危险操作（删除资源，禁止）
    DANGEROUS_ACTIONS = {
        'terminate', 'delete', 'remove', 'destroy',
        'drop', 'truncate', 'purge', 'kill'
    }

    def __init__(self, default_level: PermissionLevel = PermissionLevel.READ_ONLY):
        """
        Args:
            default_level: 默认权限级别（推荐READ_ONLY）
        """
        self.default_level = default_level
        self.permissions: Dict[str, Permission] = {}

        # 初始化默认权限
        self._initialize_default_permissions()

    def _initialize_default_permissions(self):
        """初始化默认权限（只读）"""
        # AWS权限
        for service, actions in self.AWS_READ_ONLY_ACTIONS.items():
            self.add_permission(
                provider=CloudProvider.AWS,
                service=service,
                actions=actions,
                level=PermissionLevel.READ_ONLY,
                description=f"AWS {service}只读权限"
            )

        # Azure权限
        for service, actions in self.AZURE_READ_ONLY_ACTIONS.items():
            self.add_permission(
                provider=CloudProvider.AZURE,
                service=service,
                actions=actions,
                level=PermissionLevel.READ_ONLY,
                description=f"Azure {service}只读权限"
            )

        # GCP权限
        for service, actions in self.GCP_READ_ONLY_ACTIONS.items():
            self.add_permission(
                provider=CloudProvider.GCP,
                service=service,
                actions=actions,
                level=PermissionLevel.READ_ONLY,
                description=f"GCP {service}只读权限"
            )

        # Kubernetes权限
        for service, actions in self.K8S_READ_ONLY_ACTIONS.items():
            self.add_permission(
                provider=CloudProvider.KUBERNETES,
                service=service,
                actions=actions,
                level=PermissionLevel.READ_ONLY,
                description=f"Kubernetes {service}只读权限"
            )

    def add_permission(
        self,
        provider: CloudProvider,
        service: str,
        actions: Set[str],
        level: PermissionLevel,
        description: str = ""
    ):
        """
        添加权限

        Args:
            provider: 云服务提供商
            service: 服务名称
            actions: 允许的操作集合
            level: 权限级别
            description: 描述
        """
        key = f"{provider.value}.{service}"

        permission = Permission(
            provider=provider,
            service=service,
            actions=actions,
            level=level,
            description=description
        )

        self.permissions[key] = permission
        logger.info(f"添加权限: {key} - {level.value} - {len(actions)}个操作")

    def check_action(
        self,
        provider: str,
        service: str,
        action: str
    ) -> Dict[str, Any]:
        """
        检查操作是否被允许

        Args:
            provider: 云服务提供商
            service: 服务名称
            action: 操作名称

        Returns:
            检查结果
        """
        # 1. 首先检查是否是危险操作
        action_lower = action.lower()
        for dangerous_word in self.DANGEROUS_ACTIONS:
            if dangerous_word in action_lower:
                return {
                    "allowed": False,
                    "reason": f"危险操作 '{action}' 被禁止（包含关键字: {dangerous_word}）",
                    "level": "blocked",
                    "suggestion": "生成的代码只能进行只读查询，不能删除或修改资源"
                }

        # 2. 检查权限表
        key = f"{provider}.{service}"
        permission = self.permissions.get(key)

        if not permission:
            return {
                "allowed": False,
                "reason": f"未找到 {key} 的权限定义",
                "level": "warning",
                "suggestion": f"请先为 {key} 配置权限策略"
            }

        # 3. 检查操作是否在允许列表中
        if action in permission.actions:
            return {
                "allowed": True,
                "level": permission.level.value,
                "permission": {
                    "provider": permission.provider.value,
                    "service": permission.service,
                    "description": permission.description
                }
            }

        # 4. 模糊匹配（处理不同的命名风格）
        action_normalized = action.lower().replace('_', '').replace('-', '')

        for allowed_action in permission.actions:
            allowed_normalized = allowed_action.lower().replace('_', '').replace('-', '')

            if action_normalized == allowed_normalized:
                return {
                    "allowed": True,
                    "level": permission.level.value,
                    "matched_action": allowed_action,
                    "permission": {
                        "provider": permission.provider.value,
                        "service": permission.service,
                        "description": permission.description
                    }
                }

        # 5. 未找到匹配的操作
        return {
            "allowed": False,
            "reason": f"操作 '{action}' 不在 {key} 的允许列表中",
            "level": "warning",
            "allowed_actions": list(permission.actions),
            "suggestion": "使用允许列表中的操作，或扩展权限策略"
        }

    def get_allowed_actions(self, provider: str, service: str) -> List[str]:
        """
        获取允许的操作列表

        Args:
            provider: 云服务提供商
            service: 服务名称

        Returns:
            允许的操作列表
        """
        key = f"{provider}.{service}"
        permission = self.permissions.get(key)

        if permission:
            return list(permission.actions)
        return []

    def get_permission_summary(self) -> Dict[str, Any]:
        """
        获取权限摘要

        Returns:
            权限摘要信息
        """
        summary = {
            "total_permissions": len(self.permissions),
            "default_level": self.default_level.value,
            "by_provider": {},
            "by_level": {level.value: 0 for level in PermissionLevel}
        }

        for permission in self.permissions.values():
            provider = permission.provider.value

            if provider not in summary["by_provider"]:
                summary["by_provider"][provider] = {
                    "services": 0,
                    "total_actions": 0
                }

            summary["by_provider"][provider]["services"] += 1
            summary["by_provider"][provider]["total_actions"] += len(permission.actions)
            summary["by_level"][permission.level.value] += 1

        return summary


# 全局权限管理器实例
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """获取全局权限管理器实例"""
    global _permission_manager

    if _permission_manager is None:
        _permission_manager = PermissionManager(default_level=PermissionLevel.READ_ONLY)

    return _permission_manager
