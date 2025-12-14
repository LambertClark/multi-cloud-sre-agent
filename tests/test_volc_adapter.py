"""
测试火山云数据适配功能
"""
import asyncio
import sys
import os
from datetime import datetime
import io

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.data_adapter_agent import DataAdapterAgent


# ==================== Mock数据 ====================

# 火山云ECS实例数据
VOLC_ECS_DATA = {
    "InstanceId": "i-volc-abc123",
    "InstanceName": "web-server-01",
    "InstanceType": "ecs.g2i.large",
    "Status": "RUNNING",
    "ZoneId": "cn-beijing-a",
    "Cpus": 4,
    "MemorySize": 8.0,
    "VpcId": "vpc-xyz789",
    "NetworkInterfaces": [
        {
            "PrimaryIpAddress": "172.16.0.10",
            "PublicIpAddress": "101.200.100.50"
        }
    ],
    "Tags": {
        "Environment": "Production",
        "Team": "Platform"
    }
}

# 火山云监控指标数据
VOLC_METRIC_DATA = {
    "MetricName": "CpuUtil",
    "Namespace": "VCM/ECS",
    "Dimensions": {
        "InstanceId": "i-volc-abc123"
    },
    "Data": [
        {
            "Timestamp": 1700000000,
            "Value": 45.2
        },
        {
            "Timestamp": 1700000060,
            "Value": 52.8
        },
        {
            "Timestamp": 1700000120,
            "Value": 48.5
        }
    ]
}

# 火山云TLS日志数据
VOLC_TLS_DATA = {
    "TopicId": "topic-app-logs",
    "start_time": datetime(2024, 1, 1, 0, 0, 0),
    "end_time": datetime(2024, 1, 1, 1, 0, 0),
    "LogItems": [
        {
            "Level": "INFO",
            "Message": "Request processed successfully"
        },
        {
            "Level": "INFO",
            "Message": "Cache hit"
        },
        {
            "Level": "WARN",
            "Message": "Slow query detected"
        },
        {
            "Level": "ERROR",
            "Message": "Connection timeout"
        },
        {
            "Level": "INFO",
            "Message": "Response sent"
        }
    ]
}


# ==================== 测试函数 ====================

async def test_volc_ecs():
    """测试火山云ECS → ComputeResource转换"""
    print("\n=== 测试火山云ECS → ComputeResource ===")

    agent = DataAdapterAgent()

    result = await agent.safe_process({
        "raw_data": VOLC_ECS_DATA,
        "cloud_provider": "volc",
        "target_schema": "ComputeResource"
    })

    if result.success:
        resource = result.data
        print(f"✅ 转换成功 (方法: {result.metadata.get('conversion_method')})")
        print(f"   资源ID: {resource.resource_id}")
        print(f"   资源名称: {resource.resource_name}")
        print(f"   资源类型: {resource.resource_type}")
        print(f"   云平台: {resource.cloud_provider}")
        print(f"   状态: {resource.state}")
        print(f"   区域: {resource.region}")
        print(f"   可用区: {resource.availability_zone}")
        print(f"   实例类型: {resource.instance_type}")
        print(f"   CPU核心数: {resource.cpu_cores}")
        print(f"   内存GB: {resource.memory_gb}")
        print(f"   内网IP: {resource.private_ip}")
        print(f"   公网IP: {resource.public_ip}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_volc_metric():
    """测试火山云Monitor Metric → MetricResult转换"""
    print("\n=== 测试火山云Monitor Metric → MetricResult ===")

    agent = DataAdapterAgent()

    result = await agent.safe_process({
        "raw_data": VOLC_METRIC_DATA,
        "cloud_provider": "volc",
        "target_schema": "MetricResult"
    })

    if result.success:
        metric = result.data
        print(f"✅ 转换成功 (方法: {result.metadata.get('conversion_method')})")
        print(f"   指标名称: {metric.metric_name}")
        print(f"   命名空间: {metric.metric_namespace}")
        print(f"   数据点数量: {len(metric.datapoints)}")
        if metric.datapoints:
            print(f"   最新值: {metric.datapoints[-1].value}")
            print(f"   最早值: {metric.datapoints[0].value}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_volc_logs():
    """测试火山云TLS Logs → LogHealth转换"""
    print("\n=== 测试火山云TLS Logs → LogHealth ===")

    agent = DataAdapterAgent()

    result = await agent.safe_process({
        "raw_data": VOLC_TLS_DATA,
        "cloud_provider": "volc",
        "target_schema": "LogHealth"
    })

    if result.success:
        log_health = result.data
        print(f"✅ 转换成功 (方法: {result.metadata.get('conversion_method')})")
        print(f"   日志源: {log_health.log_source}")
        print(f"   总日志数: {log_health.total_logs}")
        print(f"   错误数: {log_health.error_count}")
        print(f"   警告数: {log_health.warning_count}")
        print(f"   严重错误数: {log_health.critical_count}")
        print(f"   错误率: {log_health.error_rate:.2%}")
        print(f"   是否健康: {log_health.is_healthy}")
        print(f"   健康分数: {log_health.health_score:.1f}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("火山云数据适配测试")
    print("=" * 70)

    await test_volc_ecs()
    await test_volc_metric()
    await test_volc_logs()

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
