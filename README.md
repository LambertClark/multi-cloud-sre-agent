# 多云SRE Agent系统

基于LangChain的智能多云SRE管理系统，通过统一Schema实现跨云平台的可观测性数据标准化。

## 🌟 核心特性

### 1. 多云数据统一适配
- **DataAdapterAgent**: 混合架构（规则引擎 + LLM智能转换）
- **统一Schema体系**: 跨云平台的标准化数据模型
- **零代码扩展**: 未知云平台自动通过LLM适配

### 2. 支持的云平台
| 云平台 | 计算资源 | 监控指标 | 日志/追踪 | 状态 |
|--------|---------|---------|-----------|------|
| **AWS** | EC2 | CloudWatch | X-Ray, CloudWatch Logs | ✅ 完整支持 |
| **Azure** | Virtual Machine | Azure Monitor | Application Insights | ✅ 数据适配 |
| **GCP** | Compute Engine | Cloud Monitoring | Cloud Trace | ✅ 数据适配 |
| **火山云** | ECS | VeMonitor | TLS Logs | ✅ 数据适配 |
| **Kubernetes** | Pod | - | - | ✅ 数据适配 |

### 3. 智能代码生成
- **动态工作流**: API规格拉取 → RAG检索 → 代码生成 → WASM测试
- **ManagerAgent**: 自动识别意图、编排任务
- **CodeGeneratorAgent**: 支持Python/JavaScript/TypeScript/Go

### 4. 统一Schema体系
```python
# 健康检查Schema
HealthSchema: MetricHealth, LogHealth, TraceHealth, ResourceHealth

# 资源Schema
ResourceSchema: ComputeResource, ContainerResource, NetworkResource, CDNResource

# 指标Schema
MetricSchema: MetricResult, MetricDataPoint
```

## 🚀 快速开始

### 安装
```bash
# 克隆项目
git clone https://github.com/LambertClark/multi-cloud-sre-agent.git
cd multi-cloud-sre-agent

# 安装依赖（使用uv）
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM API 密钥和云平台凭证
```

### 配置说明
在 `.env` 文件中配置：
```bash
# LLM配置
LLM_MODEL=gpt-4
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1

# AWS凭证（可选）
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Azure凭证（可选）
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
AZURE_SUBSCRIPTION_ID=your_subscription_id

# GCP凭证（可选）
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

### 运行
```bash
# 交互模式
python main.py --mode interactive

# 单次查询
python main.py -m query -q "查询AWS EC2的CPU使用率"

# 健康检查模式
python main.py --mode health
```

## 📖 使用指南

### 1. DataAdapterAgent - 多云数据转换

DataAdapterAgent是本系统的核心组件，负责将各云平台的原始数据转换为统一Schema。

#### 工作原理
```
原始数据 → 规则引擎(快速) → 统一Schema ✅
   ↓
 规则不匹配
   ↓
LLM智能转换(兜底) → 统一Schema ✅
```

#### 使用示例

**AWS EC2 → ComputeResource**
```python
import asyncio
from agents.data_adapter_agent import DataAdapterAgent

async def convert_ec2_data():
    agent = DataAdapterAgent()

    # AWS EC2原始数据
    aws_ec2_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t3.medium",
        "State": {"Name": "running"},
        "PrivateIpAddress": "172.31.0.10",
        "PublicIpAddress": "54.123.45.67",
        "Tags": [{"Key": "Environment", "Value": "Production"}]
    }

    # 转换为统一Schema
    result = await agent.safe_process({
        "raw_data": aws_ec2_data,
        "cloud_provider": "aws",
        "target_schema": "ComputeResource"
    })

    if result.success:
        resource = result.data
        print(f"资源ID: {resource.resource_id}")
        print(f"状态: {resource.state}")
        print(f"实例类型: {resource.instance_type}")
        print(f"转换方法: {result.metadata['conversion_method']}")  # fast_rule

asyncio.run(convert_ec2_data())
```

**Azure VM → ComputeResource**
```python
# Azure虚拟机数据
azure_vm_data = {
    "vmId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "web-vm-01",
    "location": "eastus",
    "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
    "instanceView": {
        "statuses": [
            {"code": "PowerState/running"}
        ]
    }
}

result = await agent.safe_process({
    "raw_data": azure_vm_data,
    "cloud_provider": "azure",
    "target_schema": "ComputeResource"
})
# 输出相同的ComputeResource格式 ✅
```

**GCP GCE → ComputeResource**
```python
# GCP Compute Engine数据
gcp_gce_data = {
    "id": "123456789012345678",
    "name": "web-instance-01",
    "machineType": "https://www.googleapis.com/compute/v1/projects/my-project/zones/us-central1-a/machineTypes/n1-standard-2",
    "status": "RUNNING",
    "zone": "https://www.googleapis.com/compute/v1/projects/my-project/zones/us-central1-a",
    "networkInterfaces": [
        {"networkIP": "10.128.0.2"}
    ]
}

result = await agent.safe_process({
    "raw_data": gcp_gce_data,
    "cloud_provider": "gcp",
    "target_schema": "ComputeResource"
})
# 输出相同的ComputeResource格式 ✅
```

### 2. 健康判断标准

系统内置了统一的健康判断阈值：

```python
from schemas.health_schema import HealthThreshold

# 默认阈值
thresholds = HealthThreshold()
print(thresholds.cpu_warning_threshold)       # 80.0 (CPU警告阈值)
print(thresholds.cpu_critical_threshold)      # 95.0 (CPU严重阈值)
print(thresholds.log_error_rate_warning)      # 0.01 (1% 错误率警告)
print(thresholds.trace_error_rate_warning)    # 0.01 (1% trace错误率)
print(thresholds.trace_p95_latency_warning_ms) # 1000.0 (P95延迟1秒)
```

### 3. 监控指标转换

**AWS CloudWatch → MetricResult**
```python
cloudwatch_data = {
    "Datapoints": [
        {"Timestamp": "2024-01-01T00:00:00Z", "Average": 65.2},
        {"Timestamp": "2024-01-01T00:05:00Z", "Average": 72.8}
    ],
    "Label": "CPUUtilization"
}

result = await agent.safe_process({
    "raw_data": cloudwatch_data,
    "cloud_provider": "aws",
    "target_schema": "MetricResult"
})

metric = result.data
print(f"指标名称: {metric.metric_name}")
print(f"数据点数量: {len(metric.datapoints)}")
```

**火山云VeMonitor → MetricResult**
```python
volc_metric_data = {
    "MetricName": "CpuUtil",
    "Namespace": "VCM/ECS",
    "Data": [
        {"Timestamp": 1700000000, "Value": 45.2},
        {"Timestamp": 1700000060, "Value": 52.8}
    ]
}

result = await agent.safe_process({
    "raw_data": volc_metric_data,
    "cloud_provider": "volc",
    "target_schema": "MetricResult"
})
# 输出统一的MetricResult格式 ✅
```

### 4. 智能代码生成

对于没有现成工具的云平台/服务，系统会自动生成代码：

```python
from agents.manager_agent import ManagerAgent

async def query_gcp_metrics():
    manager = ManagerAgent()

    # 用户查询
    response = await manager.process({
        "query": "查询GCP Compute Engine实例的CPU使用率"
    })

    # ManagerAgent会自动：
    # 1. 识别: cloud_provider=gcp, service=monitoring
    # 2. 判断: 没有现成的GCPMonitoringTools
    # 3. 拉取: GCP Cloud Monitoring API规格
    # 4. 生成: Python调用代码
    # 5. 测试: WASM沙箱验证
    # 6. 执行: 获取数据
    # 7. 转换: 通过DataAdapterAgent转为MetricResult

    print(response.data)

asyncio.run(query_gcp_metrics())
```

## 🧪 测试

### 运行所有测试
```bash
# DataAdapterAgent测试
python tests/test_data_adapter_agent.py

# Azure/GCP适配测试
python tests/test_azure_gcp_adapter.py

# 火山云适配测试
python tests/test_volc_adapter.py

# 系统集成测试
python test_system.py
```

### 测试覆盖范围
✅ AWS数据转换（EC2, CloudWatch, X-Ray, Logs）
✅ Azure数据转换（VM, Monitor, AppInsights）
✅ GCP数据转换（GCE, CloudMonitoring, CloudTrace）
✅ 火山云数据转换（ECS, VeMonitor, TLS）
✅ Kubernetes数据转换（Pod）
✅ 健康判断标准验证

## 📁 项目结构

```
multi-cloud-sre-agent/
├── agents/                          # Agent模块
│   ├── __init__.py
│   ├── base_agent.py               # Agent基类
│   ├── manager_agent.py            # 任务编排Agent
│   ├── code_generator_agent.py     # 代码生成Agent
│   └── data_adapter_agent.py       # ⭐ 数据适配Agent（核心）
│
├── schemas/                         # ⭐ 统一Schema定义
│   ├── __init__.py
│   ├── health_schema.py            # 健康检查Schema
│   ├── resource_schema.py          # 资源Schema
│   └── metric_schema.py            # 指标Schema
│
├── tools/                           # 云平台工具
│   ├── __init__.py
│   ├── cloud_tools.py              # 工具注册中心
│   ├── aws_tools.py                # AWS监控工具
│   └── azure_tools.py              # Azure监控工具
│
├── tests/                           # 测试文件
│   ├── test_data_adapter_agent.py  # DataAdapter测试
│   ├── test_azure_gcp_adapter.py   # Azure/GCP测试
│   └── test_volc_adapter.py        # 火山云测试
│
├── docs/                            # 文档
│   ├── TODO.md                     # 任务列表
│   └── data_adapter_agent.md       # DataAdapter文档
│
├── rag_system/                      # RAG系统
│   └── chroma_rag.py               # ChromaDB向量存储
│
├── config.py                        # 配置管理
├── main.py                          # 主入口
├── orchestrator.py                  # 编排器
├── test_system.py                   # 系统测试
├── pyproject.toml                   # 项目配置
└── README.md                        # 本文档
```

## 🔧 核心组件详解

### DataAdapterAgent

**混合架构设计**
```python
# 快速路径：规则引擎
FAST_RULES = {
    "aws": {
        "ec2_to_compute": {...},      # AWS EC2 → ComputeResource
        "cloudwatch_metric": {...},   # CloudWatch → MetricResult
    },
    "azure": {
        "vm_to_compute": {...},       # Azure VM → ComputeResource
        "monitor_metric": {...},      # Azure Monitor → MetricResult
    },
    "gcp": {...},
    "volc": {...},
    "kubernetes": {...}
}

# 智能路径：LLM + RAG
# 当规则不匹配时，自动使用LLM进行智能转换
# 可查询RAG系统获取API文档辅助理解
```

**支持的转换**
- ✅ 计算资源: EC2/VM/GCE/ECS → `ComputeResource`
- ✅ 容器资源: Pod → `ContainerResource`
- ✅ 监控指标: CloudWatch/AzureMonitor/CloudMonitoring/VeMonitor → `MetricResult`
- ✅ 日志健康: CloudWatchLogs/TLS → `LogHealth`
- ✅ 链路追踪: X-Ray/AppInsights/CloudTrace → `TraceHealth`

### 统一Schema

**ResourceSchema**
```python
class ComputeResource(CloudResource):
    resource_id: str              # 统一资源ID
    resource_type: ResourceType   # ec2/vm_azure/gce/ecs_volc
    cloud_provider: str           # aws/azure/gcp/volc
    state: ResourceState          # running/stopped/pending
    instance_type: str            # t3.medium/Standard_D2s_v3/n1-standard-2
    private_ip: str
    public_ip: str
    tags: Dict[str, str]
    # ... 更多统一字段
```

**HealthSchema**
```python
class MetricHealth(BaseModel):
    metric_name: str
    current_value: float
    threshold_warning: float
    threshold_critical: float
    status: HealthStatus          # healthy/degraded/unhealthy/critical
    health_score: float           # 0-100
```

## 🎯 使用场景

### 场景1: 多云资源统一监控
```python
# 一次性获取AWS、Azure、GCP的所有VM，统一格式
resources = []

# AWS EC2
aws_instances = get_aws_ec2_instances()
for instance in aws_instances:
    resource = await adapter.convert(instance, "aws", "ComputeResource")
    resources.append(resource)

# Azure VM
azure_vms = get_azure_vms()
for vm in azure_vms:
    resource = await adapter.convert(vm, "azure", "ComputeResource")
    resources.append(resource)

# GCP GCE
gcp_instances = get_gcp_instances()
for instance in gcp_instances:
    resource = await adapter.convert(instance, "gcp", "ComputeResource")
    resources.append(resource)

# 所有资源现在是统一格式，可以统一处理
for resource in resources:
    if resource.state == ResourceState.RUNNING:
        print(f"{resource.cloud_provider}: {resource.resource_name} is running")
```

### 场景2: 跨云CPU监控告警
```python
# 统一查询所有云平台的CPU指标
metrics = []

# AWS CloudWatch
aws_metrics = get_aws_cloudwatch_metrics()
for m in aws_metrics:
    metric = await adapter.convert(m, "aws", "MetricResult")
    metrics.append(metric)

# Azure Monitor
azure_metrics = get_azure_monitor_metrics()
for m in azure_metrics:
    metric = await adapter.convert(m, "azure", "MetricResult")
    metrics.append(metric)

# 统一判断：CPU > 80%
for metric in metrics:
    if metric.datapoints:
        latest = metric.datapoints[-1].value
        if latest > 80:
            print(f"⚠️ {metric.metric_name} 过高: {latest}%")
```

### 场景3: 自动化健康检查
```python
from schemas.health_schema import HealthThreshold

thresholds = HealthThreshold()

# 检查日志健康
log_data = get_cloudwatch_logs()  # 或 get_azure_logs() / get_volc_logs()
log_health = await adapter.convert(log_data, "aws", "LogHealth")

if log_health.error_rate > thresholds.log_error_rate_warning:
    alert(f"日志错误率过高: {log_health.error_rate:.2%}")

# 检查链路健康
trace_data = get_xray_traces()  # 或 get_app_insights_traces()
trace_health = await adapter.convert(trace_data, "aws", "TraceHealth")

if trace_health.p95_duration_ms > thresholds.trace_p95_latency_warning_ms:
    alert(f"P95延迟过高: {trace_health.p95_duration_ms}ms")
```

## 🔌 扩展新云平台

### 方案1: 添加快速规则（推荐）
```python
# 在 data_adapter_agent.py 的 FAST_RULES 中添加
"aliyun": {
    "ecs_to_compute": {
        "applicable": lambda data: "InstanceId" in data and "Status" in data,
        "converter": "_convert_aliyun_ecs_fast"
    }
}

# 实现转换方法
def _convert_aliyun_ecs_fast(self, raw_data, target_schema):
    return ComputeResource(
        resource_id=raw_data["InstanceId"],
        resource_type=ResourceType.ECS,
        cloud_provider="aliyun",
        state=self._map_aliyun_state(raw_data["Status"]),
        # ...
    )
```

### 方案2: 零配置（LLM自动适配）
```python
# 直接使用，无需配置
unknown_cloud_data = {...}  # 任意云平台数据

result = await adapter.safe_process({
    "raw_data": unknown_cloud_data,
    "cloud_provider": "unknown_cloud",
    "target_schema": "ComputeResource"
})

# DataAdapterAgent会自动：
# 1. 尝试规则引擎（失败）
# 2. 使用LLM智能理解数据格式
# 3. 查询RAG获取Schema定义
# 4. 生成正确的转换结果
```

## 🛠️ 开发指南

### 添加新的Schema
```python
# 在 schemas/ 目录下创建新文件
from pydantic import BaseModel, Field

class DatabaseHealth(BaseModel):
    """数据库健康检查Schema"""
    db_instance_id: str = Field(..., description="数据库实例ID")
    connection_count: int = Field(..., description="连接数")
    slow_query_count: int = Field(..., description="慢查询数")
    # ...
```

### 自定义健康阈值
```python
from schemas.health_schema import HealthThreshold

# 自定义阈值
custom_threshold = HealthThreshold(
    cpu_warning_threshold=70.0,      # 降低CPU警告阈值到70%
    trace_p95_latency_warning_ms=500.0  # P95延迟500ms警告
)
```

## 📊 性能特点

- **规则引擎**: 毫秒级转换速度
- **LLM兜底**: 3-5秒智能转换（未知格式）
- **RAG检索**: 向量化文档，精准匹配
- **并发处理**: 支持批量数据转换

## ⚠️ 注意事项

1. **LLM API密钥**: 必须配置才能使用智能转换和代码生成
2. **云平台凭证**: 仅在实际调用云API时需要
3. **数据适配**: 可以完全离线使用（使用规则引擎）
4. **成本控制**: 优先使用规则引擎，减少LLM调用
