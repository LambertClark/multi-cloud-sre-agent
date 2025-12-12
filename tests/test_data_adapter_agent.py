"""
DataAdapterAgent测试用例
验证多云数据转换功能
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.data_adapter_agent import DataAdapterAgent
from datetime import datetime


async def test_aws_ec2_fast_path():
    """测试AWS EC2快速路径转换"""
    print("\n=== 测试AWS EC2快速路径转换 ===")

    adapter = DataAdapterAgent()

    # 模拟AWS EC2 describe_instances响应
    aws_ec2_data = {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t3.medium",
        "State": {"Code": 16, "Name": "running"},
        "LaunchTime": datetime.utcnow().isoformat(),
        "Placement": {"AvailabilityZone": "us-east-1a"},
        "PrivateIpAddress": "10.0.1.100",
        "PublicIpAddress": "54.123.45.67",
        "VpcId": "vpc-12345678",
        "SubnetId": "subnet-87654321",
        "Tags": [
            {"Key": "Name", "Value": "web-server-01"},
            {"Key": "Environment", "Value": "production"},
            {"Key": "业务", "Value": "电商平台"},
        ],
    }

    result = await adapter.safe_process(
        {
            "raw_data": aws_ec2_data,
            "cloud_provider": "aws",
            "resource_type": "ec2",
            "target_schema": "ComputeResource",
        }
    )

    if result.success:
        print(f"✅ 转换成功")
        print(f"转换方法: {result.metadata.get('conversion_method')}")
        print(f"资源ID: {result.data.resource_id}")
        print(f"资源名称: {result.data.resource_name}")
        print(f"状态: {result.data.state}")
        print(f"实例类型: {result.data.instance_type}")
        print(f"业务标签: {result.data.tags.get('业务')}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_aws_cloudwatch_metric_fast_path():
    """测试AWS CloudWatch Metric快速路径转换"""
    print("\n=== 测试AWS CloudWatch Metric快速路径转换 ===")

    adapter = DataAdapterAgent()

    # 模拟CloudWatch get_metric_statistics响应
    cloudwatch_data = {
        "Label": "CPUUtilization",
        "Datapoints": [
            {
                "Timestamp": datetime.utcnow().isoformat(),
                "Average": 85.5,
                "Unit": "Percent",
            },
            {
                "Timestamp": datetime.utcnow().isoformat(),
                "Average": 92.3,
                "Unit": "Percent",
            },
        ],
        "metadata": {
            "namespace": "AWS/EC2",
            "metric_name": "CPUUtilization",
            "dimensions": {"InstanceId": "i-1234567890abcdef0"},
        },
    }

    result = await adapter.safe_process(
        {
            "raw_data": cloudwatch_data,
            "cloud_provider": "aws",
            "resource_type": "cloudwatch_metric",
            "target_schema": "MetricResult",
        }
    )

    if result.success:
        print(f"✅ 转换成功")
        print(f"转换方法: {result.metadata.get('conversion_method')}")
        print(f"指标名称: {result.data.metric_name}")
        print(f"数据点数量: {len(result.data.datapoints)}")
        if result.data.datapoints:
            print(f"最新值: {result.data.datapoints[-1].value}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_k8s_pod_fast_path():
    """测试Kubernetes Pod快速路径转换"""
    print("\n=== 测试Kubernetes Pod快速路径转换 ===")

    adapter = DataAdapterAgent()

    # 模拟K8s Pod对象
    k8s_pod_data = {
        "kind": "Pod",
        "metadata": {
            "name": "web-app-5d7c8b9f4-xyz12",
            "namespace": "production",
            "labels": {"app": "web-app", "业务": "电商平台", "version": "v1.2.3"},
            "creationTimestamp": "2025-01-10T10:00:00Z",
        },
        "spec": {
            "nodeName": "node-01",
            "containers": [
                {
                    "name": "web-app",
                    "image": "nginx:1.21",
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    },
                }
            ],
        },
        "status": {
            "phase": "Running",
            "podIP": "10.244.1.15",
            "containerStatuses": [{"restartCount": 2, "ready": True}],
            "conditions": [
                {"type": "Ready", "status": "True"},
                {"type": "ContainersReady", "status": "True"},
            ],
        },
    }

    result = await adapter.safe_process(
        {
            "raw_data": k8s_pod_data,
            "cloud_provider": "kubernetes",
            "resource_type": "pod",
            "target_schema": "ContainerResource",
        }
    )

    if result.success:
        print(f"✅ 转换成功")
        print(f"转换方法: {result.metadata.get('conversion_method')}")
        print(f"资源ID: {result.data.resource_id}")
        print(f"Pod名称: {result.data.resource_name}")
        print(f"命名空间: {result.data.namespace}")
        print(f"状态: {result.data.state}")
        print(f"重启次数: {result.data.restart_count}")
        print(f"业务标签: {result.data.tags.get('业务')}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_llm_fallback():
    """测试LLM智能转换（快速路径不适用时）"""
    print("\n=== 测试LLM智能转换（未知格式） ===")

    adapter = DataAdapterAgent()

    # 模拟一个阿里云ECS响应（没有预定义规则）
    aliyun_ecs_data = {
        "InstanceId": "i-bp1234567890abcde",
        "InstanceName": "aliyun-web-server",
        "Status": "Running",
        "InstanceType": "ecs.t5-lc1m2.small",
        "VpcAttributes": {
            "PrivateIpAddress": {"IpAddress": ["172.16.0.100"]},
            "VpcId": "vpc-bp123456",
        },
        "PublicIpAddress": {"IpAddress": ["47.88.12.34"]},
        "CreationTime": "2025-01-10T10:00:00Z",
        "ZoneId": "cn-hangzhou-h",
        "Tags": {"Tag": [{"TagKey": "业务", "TagValue": "电商平台"}]},
    }

    result = await adapter.safe_process(
        {
            "raw_data": aliyun_ecs_data,
            "cloud_provider": "aliyun",
            "resource_type": "ecs",
            "target_schema": "ComputeResource",
        }
    )

    if result.success:
        print(f"✅ 转换成功")
        print(f"转换方法: {result.metadata.get('conversion_method')}")
        print(f"是否使用RAG: {result.metadata.get('rag_used')}")
        print(f"资源ID: {result.data.resource_id}")
        print(f"资源名称: {result.data.resource_name}")
        print(f"状态: {result.data.state}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("DataAdapterAgent 功能测试")
    print("=" * 60)

    # 快速路径测试
    await test_aws_ec2_fast_path()
    await test_aws_cloudwatch_metric_fast_path()
    await test_k8s_pod_fast_path()

    # LLM智能转换测试（需要配置LLM才能运行）
    print("\n⚠️  LLM智能转换测试需要配置OpenAI API，跳过")
    # await test_llm_fallback()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
