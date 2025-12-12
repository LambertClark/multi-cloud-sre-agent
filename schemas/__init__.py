"""
多云SRE统一数据模型
定义跨云平台的标准化Schema
"""
from .health_schema import (
    HealthStatus,
    HealthCheckResult,
    ResourceHealth,
    MetricHealth,
    LogHealth,
    TraceHealth,
)
from .resource_schema import (
    CloudResource,
    ComputeResource,
    ContainerResource,
    NetworkResource,
)
from .metric_schema import (
    MetricDataPoint,
    MetricQuery,
    MetricResult,
)

__all__ = [
    # Health Schemas
    'HealthStatus',
    'HealthCheckResult',
    'ResourceHealth',
    'MetricHealth',
    'LogHealth',
    'TraceHealth',

    # Resource Schemas
    'CloudResource',
    'ComputeResource',
    'ContainerResource',
    'NetworkResource',

    # Metric Schemas
    'MetricDataPoint',
    'MetricQuery',
    'MetricResult',
]
