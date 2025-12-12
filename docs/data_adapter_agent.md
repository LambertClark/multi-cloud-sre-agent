# DataAdapterAgent - 多云数据适配Agent

## 概述

DataAdapterAgent是多云SRE系统中的核心数据转换组件，负责将不同云平台的原始API响应转换为统一的Schema格式。

## 架构设计

采用**混合架构**：规则引擎（快速路径）+ LLM引擎（智能路径）

```
┌─────────────────────────────────────────┐
│       DataAdapterAgent.process()        │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │  验证输入数据   │
         └────────┬───────┘
                  │
                  ▼
    ┌─────────────────────────┐
    │   尝试快速路径转换       │
    │  (预定义规则引擎)        │
    └─────────┬───────────────┘
              │
        ┌─────┴─────┐
        │           │
    成功 │           │ 失败
        │           │
        ▼           ▼
   ┌────────┐  ┌──────────────────┐
   │ 返回结果│  │  LLM智能转换      │
   └────────┘  │  1. 查询RAG文档   │
              │  2. LLM理解格式   │
              │  3. 生成Schema    │
              │  4. 验证返回      │
              └─────────┬─────────┘
                        │
                        ▼
                   ┌────────┐
                   │ 返回结果│
                   └────────┘
```

## 核心特性

### 1. 规则引擎（快速路径）

已预定义的转换规则，覆盖常见场景：

**AWS支持：**
- ✅ EC2实例 → ComputeResource
- ✅ CloudWatch指标 → MetricResult
- ✅ X-Ray追踪 → TraceHealth
- ✅ CloudWatch日志 → LogHealth

**Kubernetes支持：**
- ✅ Pod对象 → ContainerResource

**性能：** 毫秒级转换，无需调用LLM

### 2. LLM智能转换（智能路径）

当规则引擎不适用时自动启用：

**能力：**
- 理解任意云平台的JSON响应格式
- 自动映射字段到统一Schema
- 处理嵌套结构和数组
- 时间格式标准化
- 状态枚举转换
- 可选RAG文档辅助理解

**适用场景：**
- 新云平台（阿里云、腾讯云、华为云、火山云）
- API格式变化
- 非标准响应
- 异常数据格式

## 使用方法

### 基础用法

```python
from agents import DataAdapterAgent

adapter = DataAdapterAgent()

# 转换AWS EC2实例
result = await adapter.safe_process({
    "raw_data": {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t3.medium",
        "State": {"Name": "running"},
        "Tags": [
            {"Key": "Name", "Value": "web-server-01"},
            {"Key": "业务", "Value": "电商平台"}
        ],
        # ... 更多字段
    },
    "cloud_provider": "aws",
    "resource_type": "ec2",
    "target_schema": "ComputeResource"
})

if result.success:
    compute_resource = result.data  # ComputeResource对象
    print(f"资源ID: {compute_resource.resource_id}")
    print(f"业务标签: {compute_resource.tags.get('业务')}")
    print(f"转换方法: {result.metadata['conversion_method']}")
```

### 支持的目标Schema

| Schema名称 | 用途 | 适用资源 |
|-----------|------|---------|
| `ComputeResource` | 计算资源 | EC2, ECS, CVM, VM |
| `ContainerResource` | 容器资源 | Pod, Container, ECS Task |
| `NetworkResource` | 网络资源 | ALB, SLB, CLB |
| `CDNResource` | CDN资源 | CloudFront, CDN |
| `MetricResult` | 指标数据 | CloudWatch, 阿里云监控 |
| `TraceHealth` | 链路健康 | X-Ray, APM |
| `LogHealth` | 日志健康 | CloudWatch Logs, 日志服务 |
| `MetricHealth` | 指标健康 | 单个指标健康判断 |
| `ResourceHealth` | 资源健康 | 综合健康状态 |

### 转换AWS CloudWatch指标

```python
result = await adapter.safe_process({
    "raw_data": {
        "Label": "CPUUtilization",
        "Datapoints": [
            {"Timestamp": "2025-01-10T10:00:00Z", "Average": 85.5, "Unit": "Percent"},
            {"Timestamp": "2025-01-10T10:05:00Z", "Average": 92.3, "Unit": "Percent"},
        ],
        "metadata": {
            "namespace": "AWS/EC2",
            "metric_name": "CPUUtilization",
            "dimensions": {"InstanceId": "i-1234567890abcdef0"}
        }
    },
    "cloud_provider": "aws",
    "resource_type": "cloudwatch_metric",
    "target_schema": "MetricResult"
})

metric_result = result.data
print(f"最新CPU: {metric_result.datapoints[-1].value}%")
```

### 转换Kubernetes Pod

```python
result = await adapter.safe_process({
    "raw_data": {
        "kind": "Pod",
        "metadata": {
            "name": "web-app-5d7c8b9f4-xyz12",
            "namespace": "production",
            "labels": {"app": "web-app", "业务": "电商平台"}
        },
        "spec": {
            "nodeName": "node-01",
            "containers": [...]
        },
        "status": {
            "phase": "Running",
            "podIP": "10.244.1.15",
            "containerStatuses": [{"restartCount": 2}]
        }
    },
    "cloud_provider": "kubernetes",
    "resource_type": "pod",
    "target_schema": "ContainerResource"
})

pod = result.data
print(f"Pod重启次数: {pod.restart_count}")
```

### LLM智能转换（未知格式）

```python
# 阿里云ECS（没有预定义规则，自动使用LLM）
result = await adapter.safe_process({
    "raw_data": {
        "InstanceId": "i-bp1234567890abcde",
        "InstanceName": "aliyun-web-server",
        "Status": "Running",
        "InstanceType": "ecs.t5-lc1m2.small",
        "VpcAttributes": {
            "PrivateIpAddress": {"IpAddress": ["172.16.0.100"]}
        },
        "Tags": {"Tag": [{"TagKey": "业务", "TagValue": "电商平台"}]}
    },
    "cloud_provider": "aliyun",
    "resource_type": "ecs",
    "target_schema": "ComputeResource"
})

# 检查转换方法
if result.metadata['conversion_method'] == 'llm_intelligent':
    print("✨ 使用LLM智能转换")
    print(f"RAG辅助: {result.metadata.get('rag_used')}")
```

## 扩展新云平台

### 方法1：添加快速规则（推荐）

在 `data_adapter_agent.py` 的 `FAST_RULES` 中添加：

```python
FAST_RULES = {
    "tencent": {
        "cvm_to_compute": {
            "applicable": lambda data: "InstanceId" in data and "InstanceState" in data,
            "converter": "_convert_tencent_cvm_fast",
        }
    }
}

def _convert_tencent_cvm_fast(self, raw_data, target_schema):
    """腾讯云CVM快速转换"""
    state_mapping = {
        "RUNNING": ResourceState.RUNNING,
        "STOPPED": ResourceState.STOPPED,
        # ...
    }

    return ComputeResource(
        resource_id=raw_data.get("InstanceId"),
        state=state_mapping.get(raw_data.get("InstanceState")),
        # ...
    )
```

### 方法2：依赖LLM（零代码）

直接使用，LLM会自动适配：

```python
# 无需写代码，直接转换华为云ECS
result = await adapter.safe_process({
    "raw_data": huawei_ecs_response,
    "cloud_provider": "huawei",
    "resource_type": "ecs",
    "target_schema": "ComputeResource"
})
```

## 性能优化

### 快速路径优先级

1. **首选快速规则** - 毫秒级响应
2. **LLM作为兜底** - 秒级响应，但覆盖所有场景

### 缓存策略（未来优化）

- 相同格式的转换结果可缓存
- LLM生成的映射规则可保存为快速规则

## 错误处理

```python
result = await adapter.safe_process({...})

if not result.success:
    print(f"转换失败: {result.error}")

    # 常见错误：
    # - "Invalid input": 缺少必需字段
    # - "No applicable rule found": 快速路径失败
    # - "LLM转换失败：返回格式错误": LLM返回非JSON
    # - "Unknown schema: XXX": 不支持的目标Schema
```

## 测试

运行测试用例：

```bash
python tests/test_data_adapter_agent.py
```

测试覆盖：
- ✅ AWS EC2快速转换
- ✅ AWS CloudWatch Metric快速转换
- ✅ Kubernetes Pod快速转换
- ⏳ LLM智能转换（需配置API）

## 与其他Agent集成

### 在Manager Agent中使用

```python
from agents import ManagerAgent, DataAdapterAgent

manager = ManagerAgent()
adapter = DataAdapterAgent()

# Manager查询AWS EC2列表
ec2_list = await aws_tools._list_ec2_instances_impl()

# 转换为统一格式
compute_resources = []
for instance in ec2_list["instances"]:
    result = await adapter.safe_process({
        "raw_data": instance,
        "cloud_provider": "aws",
        "target_schema": "ComputeResource"
    })
    if result.success:
        compute_resources.append(result.data)

# 现在可以统一处理多云资源
for resource in compute_resources:
    print(f"{resource.cloud_provider}: {resource.resource_id} - {resource.state}")
```

## 优势总结

| 传统Adapter | DataAdapterAgent |
|------------|------------------|
| 硬编码映射 | 规则+LLM混合 |
| 新厂商需写代码 | LLM自动适配 |
| API变化易失效 | LLM自动识别 |
| 维护成本高 | 零代码扩展 |
| 不支持异常格式 | 智能容错 |

## 下一步计划

- [ ] 增加更多快速规则（阿里云、腾讯云）
- [ ] LLM生成规则的自动保存
- [ ] 转换结果缓存
- [ ] 支持批量转换
- [ ] 性能监控和指标
