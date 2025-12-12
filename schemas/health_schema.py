"""
健康检查统一Schema
适配AWS CloudWatch、阿里云监控、腾讯云监控、华为云等
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """统一的健康状态枚举"""
    HEALTHY = "healthy"              # 健康
    DEGRADED = "degraded"            # 降级（警告）
    UNHEALTHY = "unhealthy"          # 不健康
    UNKNOWN = "unknown"              # 未知
    CRITICAL = "critical"            # 严重


class SeverityLevel(str, Enum):
    """严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthCheckResult(BaseModel):
    """健康检查结果 - 顶层统一格式"""
    status: HealthStatus = Field(..., description="健康状态")
    score: float = Field(..., ge=0, le=100, description="健康分数 0-100")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="检查时间")

    # 详细信息
    summary: str = Field(..., description="健康检查摘要")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细信息")
    issues: List["HealthIssue"] = Field(default_factory=list, description="发现的问题列表")

    # 元数据
    cloud_provider: str = Field(..., description="云平台：aws/aliyun/tencent/huawei/volc")
    resource_type: str = Field(..., description="资源类型：compute/container/network/storage")
    resource_id: Optional[str] = Field(None, description="资源ID")
    tags: Dict[str, str] = Field(default_factory=dict, description="业务标签")


class HealthIssue(BaseModel):
    """健康问题详情"""
    severity: SeverityLevel = Field(..., description="严重程度")
    category: str = Field(..., description="问题类别：metric/log/trace/resource")
    message: str = Field(..., description="问题描述")
    metric_name: Optional[str] = Field(None, description="相关指标名称")
    current_value: Optional[float] = Field(None, description="当前值")
    threshold: Optional[float] = Field(None, description="阈值")
    recommendation: Optional[str] = Field(None, description="修复建议")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MetricHealth(BaseModel):
    """指标健康检查结果"""
    metric_name: str = Field(..., description="指标名称（统一命名）")
    current_value: float = Field(..., description="当前值")
    threshold: float = Field(..., description="阈值")
    threshold_type: str = Field(..., description="阈值类型：greater_than/less_than")
    is_healthy: bool = Field(..., description="是否健康")

    # 统一的指标维度
    dimensions: Dict[str, str] = Field(default_factory=dict, description="维度信息")
    unit: str = Field(..., description="单位：Percent/Count/Seconds/Bytes等")

    # 原始数据（保留云平台原始格式）
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="原始云平台数据")
    cloud_provider: str = Field(..., description="数据来源云平台")


class LogHealth(BaseModel):
    """日志健康检查结果"""
    log_source: str = Field(..., description="日志来源：log_group/日志库名称")
    time_range: Dict[str, datetime] = Field(..., description="时间范围 {start, end}")

    # 统计信息
    total_logs: int = Field(..., description="总日志数")
    error_count: int = Field(0, description="ERROR级别数量")
    warning_count: int = Field(0, description="WARN级别数量")
    critical_count: int = Field(0, description="CRITICAL级别数量")

    # 健康判断
    error_rate: float = Field(..., description="错误率 0-1")
    is_healthy: bool = Field(..., description="是否健康")
    health_score: float = Field(..., ge=0, le=100, description="健康分数")

    # 关键错误日志样本
    critical_samples: List[Dict[str, Any]] = Field(default_factory=list, description="关键错误样本")

    # 原始数据
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    cloud_provider: str = Field(...)


class TraceHealth(BaseModel):
    """链路追踪健康检查结果"""
    service_name: str = Field(..., description="服务名称")
    time_range: Dict[str, datetime] = Field(..., description="时间范围")

    # 统计指标
    total_traces: int = Field(..., description="总追踪数")
    error_traces: int = Field(0, description="错误追踪数")
    error_rate: float = Field(..., description="错误率")

    # 性能指标（统一单位：毫秒）
    avg_duration_ms: float = Field(..., description="平均响应时间（毫秒）")
    p50_duration_ms: float = Field(..., description="P50响应时间")
    p95_duration_ms: float = Field(..., description="P95响应时间")
    p99_duration_ms: float = Field(..., description="P99响应时间")

    # 健康判断
    is_healthy: bool = Field(..., description="是否健康")
    health_score: float = Field(..., ge=0, le=100)

    # 异常trace样本
    error_trace_samples: List[Dict[str, Any]] = Field(default_factory=list)

    # 服务依赖图（可选）
    dependency_graph: Optional[Dict[str, Any]] = Field(None, description="服务依赖关系")

    raw_data: Dict[str, Any] = Field(default_factory=dict)
    cloud_provider: str = Field(...)


class ResourceHealth(BaseModel):
    """资源健康检查结果（计算、容器、网络等）"""
    resource_id: str = Field(..., description="资源ID")
    resource_name: Optional[str] = Field(None, description="资源名称")
    resource_type: str = Field(..., description="资源类型：ec2/pod/ecs/vm等")

    # 资源状态（统一状态）
    state: str = Field(..., description="运行状态：running/stopped/pending/terminating等")
    is_healthy: bool = Field(..., description="是否健康")

    # 资源使用率
    cpu_utilization: Optional[float] = Field(None, description="CPU使用率 0-100")
    memory_utilization: Optional[float] = Field(None, description="内存使用率 0-100")
    disk_utilization: Optional[float] = Field(None, description="磁盘使用率 0-100")
    network_in_mbps: Optional[float] = Field(None, description="网络入带宽 Mbps")
    network_out_mbps: Optional[float] = Field(None, description="网络出带宽 Mbps")

    # 标签和元数据
    tags: Dict[str, str] = Field(default_factory=dict)
    region: Optional[str] = Field(None, description="区域")
    availability_zone: Optional[str] = Field(None, description="可用区")

    # 问题诊断
    issues: List[HealthIssue] = Field(default_factory=list)

    raw_data: Dict[str, Any] = Field(default_factory=dict)
    cloud_provider: str = Field(...)


# 健康判断标准配置
class HealthThreshold(BaseModel):
    """健康判断阈值配置"""

    # Metric阈值
    cpu_warning_threshold: float = Field(80.0, description="CPU警告阈值 %")
    cpu_critical_threshold: float = Field(95.0, description="CPU严重阈值 %")
    memory_warning_threshold: float = Field(80.0, description="内存警告阈值 %")
    memory_critical_threshold: float = Field(95.0, description="内存严重阈值 %")

    # Log阈值
    log_error_rate_warning: float = Field(0.01, description="日志错误率警告阈值 1%")
    log_error_rate_critical: float = Field(0.05, description="日志错误率严重阈值 5%")
    log_critical_count_threshold: int = Field(10, description="Critical日志数量阈值")

    # Trace阈值
    trace_error_rate_warning: float = Field(0.01, description="追踪错误率警告阈值 1%")
    trace_error_rate_critical: float = Field(0.05, description="追踪错误率严重阈值 5%")
    trace_p95_latency_warning_ms: float = Field(1000.0, description="P95延迟警告阈值 1s")
    trace_p95_latency_critical_ms: float = Field(3000.0, description="P95延迟严重阈值 3s")

    # CDN阈值
    cdn_cache_hit_rate_warning: float = Field(0.10, description="CDN缓存命中率低于10%警告")
    cdn_latency_warning_ms: float = Field(1000.0, description="CDN延迟警告阈值 1s")

    # 资源利用率阈值（用于优化推荐）
    resource_low_utilization_threshold: float = Field(20.0, description="低利用率阈值 20%")
    resource_waste_days_threshold: int = Field(7, description="持续低利用天数阈值")


# 更新前面的类引用
HealthCheckResult.model_rebuild()
