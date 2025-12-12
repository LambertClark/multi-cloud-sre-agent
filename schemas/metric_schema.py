"""
指标统一Schema
适配AWS CloudWatch、阿里云监控、腾讯云监控等
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class MetricNamespace(str, Enum):
    """统一的指标命名空间"""
    # 计算相关
    COMPUTE_CPU = "compute.cpu"
    COMPUTE_MEMORY = "compute.memory"
    COMPUTE_DISK = "compute.disk"
    COMPUTE_NETWORK = "compute.network"

    # 容器相关
    CONTAINER_CPU = "container.cpu"
    CONTAINER_MEMORY = "container.memory"
    CONTAINER_NETWORK = "container.network"

    # 负载均衡
    LB_REQUEST_COUNT = "lb.request_count"
    LB_LATENCY = "lb.latency"
    LB_ERROR_RATE = "lb.error_rate"
    LB_ACTIVE_CONNECTIONS = "lb.active_connections"

    # CDN相关
    CDN_REQUEST_COUNT = "cdn.request_count"
    CDN_CACHE_HIT_RATE = "cdn.cache_hit_rate"
    CDN_BANDWIDTH = "cdn.bandwidth"
    CDN_LATENCY = "cdn.latency"
    CDN_ERROR_RATE = "cdn.error_rate"

    # 数据库相关
    DB_CONNECTIONS = "db.connections"
    DB_CPU = "db.cpu"
    DB_MEMORY = "db.memory"
    DB_IOPS = "db.iops"

    # 自定义
    CUSTOM = "custom"


class StatisticType(str, Enum):
    """统计类型"""
    AVERAGE = "average"
    SUM = "sum"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    SAMPLE_COUNT = "sample_count"
    P50 = "p50"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"


class MetricUnit(str, Enum):
    """指标单位"""
    # 百分比
    PERCENT = "Percent"

    # 时间
    SECONDS = "Seconds"
    MILLISECONDS = "Milliseconds"
    MICROSECONDS = "Microseconds"

    # 字节
    BYTES = "Bytes"
    KILOBYTES = "Kilobytes"
    MEGABYTES = "Megabytes"
    GIGABYTES = "Gigabytes"

    # 速率
    BYTES_PER_SECOND = "Bytes/Second"
    BITS_PER_SECOND = "Bits/Second"

    # 计数
    COUNT = "Count"
    COUNT_PER_SECOND = "Count/Second"

    # 其他
    NONE = "None"


class MetricDataPoint(BaseModel):
    """统一的指标数据点"""
    timestamp: datetime = Field(..., description="时间戳")
    value: float = Field(..., description="指标值")
    unit: MetricUnit = Field(MetricUnit.NONE, description="单位")
    statistic: StatisticType = Field(StatisticType.AVERAGE, description="统计类型")


class MetricQuery(BaseModel):
    """指标查询请求"""
    # 指标标识
    metric_namespace: str = Field(..., description="指标命名空间")
    metric_name: str = Field(..., description="指标名称")

    # 时间范围
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    period_seconds: int = Field(300, description="统计周期（秒）")

    # 统计方式
    statistics: List[StatisticType] = Field(
        default=[StatisticType.AVERAGE],
        description="统计类型列表"
    )

    # 维度过滤
    dimensions: Dict[str, str] = Field(default_factory=dict, description="维度")

    # 云平台特定参数
    cloud_provider: str = Field(..., description="云平台")
    raw_params: Dict[str, Any] = Field(default_factory=dict, description="原始参数")


class MetricResult(BaseModel):
    """指标查询结果"""
    # 查询信息
    metric_namespace: str = Field(..., description="指标命名空间")
    metric_name: str = Field(..., description="指标名称")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="维度")

    # 数据点
    datapoints: List[MetricDataPoint] = Field(default_factory=list, description="数据点列表")

    # 元数据
    unit: MetricUnit = Field(MetricUnit.NONE, description="单位")
    cloud_provider: str = Field(..., description="数据来源云平台")
    query_time: datetime = Field(default_factory=datetime.utcnow, description="查询时间")

    # 统计摘要
    summary: Optional["MetricSummary"] = Field(None, description="统计摘要")

    # 原始数据
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="云平台原始响应")


class MetricSummary(BaseModel):
    """指标统计摘要"""
    min_value: float = Field(..., description="最小值")
    max_value: float = Field(..., description="最大值")
    avg_value: float = Field(..., description="平均值")
    latest_value: float = Field(..., description="最新值")
    data_points_count: int = Field(..., description="数据点数量")


# 云平台指标名称映射
METRIC_NAME_MAPPING = {
    # CPU使用率映射
    "compute.cpu.utilization": {
        "aws": "CPUUtilization",
        "aliyun": "cpu_total",
        "tencent": "CpuUsage",
        "huawei": "cpu_util",
        "volc": "cpu_util",
    },

    # 内存使用率映射
    "compute.memory.utilization": {
        "aws": "MemoryUtilization",
        "aliyun": "memory_usedutilization",
        "tencent": "MemUsage",
        "huawei": "mem_util",
        "volc": "mem_util",
    },

    # 网络入流量映射
    "compute.network.in": {
        "aws": "NetworkIn",
        "aliyun": "networkin_rate",
        "tencent": "LanIntraffic",
        "huawei": "network_incoming_bytes_rate_inband",
        "volc": "net_recv_bytes",
    },

    # CDN缓存命中率映射
    "cdn.cache_hit_rate": {
        "aws": "CacheHitRate",
        "aliyun": "hit_rate",
        "tencent": "CacheHitRate",
        "huawei": "cache_hit_ratio",
    },

    # CDN请求延迟映射
    "cdn.latency": {
        "aws": "OriginLatency",
        "aliyun": "origin_rt",
        "tencent": "OriginDelay",
    },
}


# 云平台命名空间映射
NAMESPACE_MAPPING = {
    "compute": {
        "aws": "AWS/EC2",
        "aliyun": "acs_ecs_dashboard",
        "tencent": "QCE/CVM",
        "huawei": "SYS.ECS",
        "volc": "ecs",
    },
    "cdn": {
        "aws": "AWS/CloudFront",
        "aliyun": "acs_cdn",
        "tencent": "QCE/CDN",
        "huawei": "SYS.CDN",
    },
    "container": {
        "aws": "ContainerInsights",
        "aliyun": "acs_kubernetes",
        "tencent": "QCE/TKE",
    },
}


MetricResult.model_rebuild()
