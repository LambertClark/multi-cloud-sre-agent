"""
测试业务标签映射服务
"""
import asyncio
import sys
import os
import io

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.tag_mapping_service import TagMappingService, TaggedResource


# ==================== Mock AWS Tools ====================

class MockAWSTools:
    """Mock AWS工具类用于测试"""

    async def _list_ec2_instances_impl(self, tags=None, **kwargs):
        """Mock EC2实例列表"""
        # 模拟返回的EC2实例数据
        mock_instances = [
            {
                "InstanceId": "i-test001",
                "InstanceType": "t3.medium",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "业务", "Value": "电商平台"},
                    {"Key": "环境", "Value": "生产"},
                    {"Key": "Name", "Value": "web-server-01"}
                ]
            },
            {
                "InstanceId": "i-test002",
                "InstanceType": "t3.large",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "Business", "Value": "电商平台"},  # 英文标签
                    {"Key": "Environment", "Value": "production"},
                    {"Key": "Name", "Value": "api-server-01"}
                ]
            },
            {
                "InstanceId": "i-test003",
                "InstanceType": "t3.small",
                "State": {"Name": "stopped"},
                "Tags": [
                    {"Key": "业务", "Value": "数据分析"},  # 不同业务
                    {"Key": "环境", "Value": "测试"}
                ]
            }
        ]

        # 根据tags过滤
        if tags:
            filtered = []
            for instance in mock_instances:
                instance_tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
                match = True
                for key, value in tags.items():
                    if instance_tags.get(key) != value:
                        match = False
                        break
                if match:
                    filtered.append(instance)

            return {
                "success": True,
                "instances": filtered,
                "count": len(filtered)
            }

        return {
            "success": True,
            "instances": mock_instances,
            "count": len(mock_instances)
        }


# ==================== Mock K8s Tools ====================

class MockK8sTools:
    """Mock K8s工具类用于测试"""

    async def list_pods(self, label_selector=None, **kwargs):
        """Mock Pod列表"""
        mock_pods = [
            {
                "metadata": {
                    "name": "web-app-pod-1",
                    "namespace": "production",
                    "labels": {
                        "app": "电商平台",
                        "component": "web",
                        "环境": "生产"
                    }
                },
                "status": {"phase": "Running"}
            },
            {
                "metadata": {
                    "name": "api-pod-1",
                    "namespace": "production",
                    "labels": {
                        "业务": "电商平台",
                        "component": "api",
                        "环境": "生产"
                    }
                },
                "status": {"phase": "Running"}
            },
            {
                "metadata": {
                    "name": "data-pod-1",
                    "namespace": "analytics",
                    "labels": {
                        "业务": "数据分析",
                        "component": "processor"
                    }
                },
                "status": {"phase": "Running"}
            }
        ]

        # 根据label_selector过滤
        if label_selector:
            # 简单解析 key=value 格式
            key, value = label_selector.split("=")
            filtered = []
            for pod in mock_pods:
                labels = pod.get("metadata", {}).get("labels", {})
                if labels.get(key) == value:
                    filtered.append(pod)

            return {
                "success": True,
                "pods": filtered
            }

        return {
            "success": True,
            "pods": mock_pods
        }


# ==================== 测试函数 ====================

async def test_tag_key_normalization():
    """测试标签键标准化"""
    print("\n=== 测试1：标签键标准化 ===")

    service = TagMappingService()

    # 测试中文标签
    keys = service._normalize_tag_key("业务")
    print(f"标签键 '业务' 标准化为: {keys}")
    assert "业务" in keys
    assert "Business" in keys
    assert "business" in keys

    # 测试英文标签
    keys = service._normalize_tag_key("Environment")
    print(f"标签键 'Environment' 标准化为: {keys}")
    assert "环境" in keys
    assert "Environment" in keys

    print("✅ 标签键标准化测试通过")


async def test_get_ec2_by_tag():
    """测试通过标签查询EC2实例"""
    print("\n=== 测试2：通过标签查询EC2实例 ===")

    mock_aws = MockAWSTools()
    service = TagMappingService(aws_tools=mock_aws)

    # 查询"电商平台"业务的所有EC2实例
    resources = await service.get_resources_by_tag(
        tag_key="业务",
        tag_value="电商平台",
        resource_types=["ec2"],
        cloud_providers=["aws"]
    )

    print(f"找到 {len(resources)} 个EC2实例:")
    for resource in resources:
        print(f"  - {resource.resource_id} (标签: {resource.tags})")

    # 验证结果
    assert len(resources) >= 1
    for resource in resources:
        assert resource.resource_type == "ec2"
        assert resource.cloud_provider == "aws"
        # 至少有一个标签匹配
        assert any(
            v == "电商平台"
            for k, v in resource.tags.items()
            if k in ["业务", "Business", "business"]
        )

    print("✅ EC2标签查询测试通过")


async def test_get_pods_by_label():
    """测试通过标签查询Kubernetes Pod"""
    print("\n=== 测试3：通过标签查询Kubernetes Pod ===")

    mock_k8s = MockK8sTools()
    service = TagMappingService(k8s_tools=mock_k8s)

    # 查询"电商平台"业务的所有Pod
    resources = await service.get_resources_by_tag(
        tag_key="业务",
        tag_value="电商平台",
        resource_types=["pod"],
        cloud_providers=["k8s"]
    )

    print(f"找到 {len(resources)} 个Pod:")
    for resource in resources:
        print(f"  - {resource.resource_id} (标签: {resource.tags})")

    # 验证结果
    assert len(resources) >= 1
    for resource in resources:
        assert resource.resource_type == "pod"
        assert resource.cloud_provider == "k8s"

    print("✅ Pod标签查询测试通过")


async def test_get_pods_by_business():
    """测试通过业务名称获取Pod列表"""
    print("\n=== 测试4：通过业务名称获取Pod列表 ===")

    mock_k8s = MockK8sTools()
    service = TagMappingService(k8s_tools=mock_k8s)

    # 查询"电商平台"业务的Pod
    pods = await service.get_pods_by_business("电商平台")

    print(f"电商平台业务包含 {len(pods)} 个Pod:")
    for pod in pods:
        print(f"  - {pod.resource_id}")
        if pod.resource_data:
            namespace = pod.resource_data.get("metadata", {}).get("namespace")
            phase = pod.resource_data.get("status", {}).get("phase")
            print(f"    命名空间: {namespace}, 状态: {phase}")

    # 验证结果
    assert len(pods) >= 1

    print("✅ 业务Pod查询测试通过")


async def test_multi_cloud_query():
    """测试多云统一查询"""
    print("\n=== 测试5：多云统一查询 ===")

    mock_aws = MockAWSTools()
    mock_k8s = MockK8sTools()
    service = TagMappingService(aws_tools=mock_aws, k8s_tools=mock_k8s)

    # 同时查询AWS和K8s的资源
    resources = await service.get_resources_by_tag(
        tag_key="业务",
        tag_value="电商平台",
        resource_types=["ec2", "pod"]
    )

    print(f"跨云查询找到 {len(resources)} 个资源:")

    # 按云平台分类统计
    by_provider = {}
    for resource in resources:
        provider = resource.cloud_provider
        by_provider[provider] = by_provider.get(provider, 0) + 1
        print(f"  - [{resource.cloud_provider}] {resource.resource_type}: {resource.resource_id}")

    print(f"\n统计:")
    for provider, count in by_provider.items():
        print(f"  {provider}: {count} 个资源")

    # 验证结果
    assert len(resources) >= 2
    assert "aws" in by_provider
    assert "k8s" in by_provider

    print("✅ 多云统一查询测试通过")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("业务标签映射服务测试")
    print("=" * 70)

    await test_tag_key_normalization()
    await test_get_ec2_by_tag()
    await test_get_pods_by_label()
    await test_get_pods_by_business()
    await test_multi_cloud_query()

    print("\n" + "=" * 70)
    print("✅ 所有测试通过！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
