"""
资源统一Schema
适配多云平台的计算、容器、网络资源
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ResourceType(str, Enum):
    """资源类型"""
    # 计算资源
    EC2 = "ec2"              # AWS EC2
    VM_AZURE = "vm_azure"    # Azure Virtual Machine
    GCE = "gce"              # GCP Compute Engine
    ECS = "ecs"              # 阿里云ECS
    CVM = "cvm"              # 腾讯云CVM
    ECS_HUAWEI = "ecs_hw"    # 华为云ECS
    ECS_VOLC = "ecs_volc"    # 火山云ECS

    # 容器资源
    POD = "pod"              # Kubernetes Pod
    CONTAINER = "container"  # Docker容器
    ECS_TASK = "ecs_task"    # AWS ECS Task
    ACI = "aci"              # Azure Container Instance
    GKE_POD = "gke_pod"      # GKE Pod

    # 网络资源
    ALB = "alb"              # AWS ALB
    APP_GATEWAY = "app_gateway"  # Azure Application Gateway
    CLOUD_LOAD_BALANCER = "cloud_lb"  # GCP Cloud Load Balancer
    SLB = "slb"              # 阿里云SLB
    CLB = "clb"              # 腾讯云CLB
    CLB_VOLC = "clb_volc"    # 火山云CLB

    # CDN资源
    CLOUDFRONT = "cloudfront"     # AWS CloudFront
    AZURE_CDN = "azure_cdn"       # Azure CDN
    CLOUD_CDN = "cloud_cdn"       # GCP Cloud CDN
    CDN_ALIYUN = "cdn_aliyun"     # 阿里云CDN
    CDN_TENCENT = "cdn_tencent"   # 腾讯云CDN
    CDN_VOLC = "cdn_volc"         # 火山云CDN


class ResourceState(str, Enum):
    """统一的资源状态"""
    RUNNING = "running"
    STOPPED = "stopped"
    PENDING = "pending"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    ERROR = "error"
    UNKNOWN = "unknown"


class CloudResource(BaseModel):
    """云资源基础模型"""
    resource_id: str = Field(..., description="资源唯一标识")
    resource_name: Optional[str] = Field(None, description="资源名称")
    resource_type: ResourceType = Field(..., description="资源类型")
    cloud_provider: str = Field(..., description="云平台")

    # 状态信息
    state: ResourceState = Field(..., description="资源状态")
    created_at: Optional[datetime] = Field(None, description="创建时间")

    # 位置信息
    region: Optional[str] = Field(None, description="区域")
    availability_zone: Optional[str] = Field(None, description="可用区")

    # 标签（用于业务分类）
    tags: Dict[str, str] = Field(default_factory=dict, description="资源标签")

    # 原始数据
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="云平台原始数据")


class ComputeResource(CloudResource):
    """计算资源（VM/EC2/ECS等）"""
    # 规格信息
    instance_type: Optional[str] = Field(None, description="实例类型")
    cpu_cores: Optional[int] = Field(None, description="CPU核心数")
    memory_gb: Optional[float] = Field(None, description="内存GB")

    # 网络信息
    private_ip: Optional[str] = Field(None, description="内网IP")
    public_ip: Optional[str] = Field(None, description="公网IP")
    vpc_id: Optional[str] = Field(None, description="VPC ID")
    subnet_id: Optional[str] = Field(None, description="子网ID")

    # 存储信息
    root_volume_size_gb: Optional[int] = Field(None, description="根卷大小GB")
    data_volumes: List[Dict[str, Any]] = Field(default_factory=list, description="数据卷列表")


class ContainerResource(CloudResource):
    """容器资源（Pod/Container等）"""
    # 容器信息
    namespace: Optional[str] = Field(None, description="命名空间")
    container_image: Optional[str] = Field(None, description="镜像")
    container_count: int = Field(1, description="容器数量")

    # 资源请求和限制
    cpu_request: Optional[str] = Field(None, description="CPU请求")
    cpu_limit: Optional[str] = Field(None, description="CPU限制")
    memory_request: Optional[str] = Field(None, description="内存请求")
    memory_limit: Optional[str] = Field(None, description="内存限制")

    # Pod特有
    pod_ip: Optional[str] = Field(None, description="Pod IP")
    node_name: Optional[str] = Field(None, description="所在节点")
    restart_count: int = Field(0, description="重启次数")

    # 状态原因（用于诊断）
    state_reason: Optional[str] = Field(None, description="状态原因")
    state_message: Optional[str] = Field(None, description="状态消息")


class NetworkResource(CloudResource):
    """网络资源（负载均衡器等）"""
    # 基础信息
    dns_name: Optional[str] = Field(None, description="DNS名称")
    scheme: Optional[str] = Field(None, description="网络方案：internet-facing/internal")

    # 监听器配置
    listeners: List[Dict[str, Any]] = Field(default_factory=list, description="监听器列表")

    # 后端目标
    target_groups: List[Dict[str, Any]] = Field(default_factory=list, description="目标组列表")
    healthy_targets: int = Field(0, description="健康目标数")
    unhealthy_targets: int = Field(0, description="不健康目标数")


class CDNResource(CloudResource):
    """CDN资源"""
    # 域名配置
    domain_name: str = Field(..., description="加速域名")
    cname: Optional[str] = Field(None, description="CNAME记录")

    # 源站配置
    origin_domain: Optional[str] = Field(None, description="源站域名")
    origin_type: Optional[str] = Field(None, description="源站类型")

    # 缓存配置
    cache_behaviors: List[Dict[str, Any]] = Field(default_factory=list, description="缓存行为")

    # 状态
    enabled: bool = Field(True, description="是否启用")
    deployment_status: Optional[str] = Field(None, description="部署状态")
