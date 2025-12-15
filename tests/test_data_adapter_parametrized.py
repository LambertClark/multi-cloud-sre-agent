"""
DataAdapterAgent 参数化测试
使用 pytest.mark.parametrize 实现数据驱动测试
"""
import pytest
from agents.data_adapter_agent import DataAdapterAgent


# ==================== 参数化测试 - 多云平台资源转换 ====================

@pytest.mark.parametrize("cloud_provider,fixture_name,expected_method", [
    ("aws", "aws_ec2_data", "fast_rule"),
    ("azure", "azure_vm_data", "fast_rule"),
    ("gcp", "gcp_instance_data", "fast_rule"),
    ("volc", "volc_ecs_data", "fast_rule"),
])
@pytest.mark.unit
async def test_compute_resource_conversion(cloud_provider, fixture_name, expected_method, request):
    """
    参数化测试：多云平台计算资源转换
    覆盖 AWS/Azure/GCP/火山云 的 ComputeResource 转换
    """
    # 通过 fixture_name 动态获取测试数据
    raw_data = request.getfixturevalue(fixture_name)

    adapter = DataAdapterAgent()

    result = await adapter.safe_process({
        "raw_data": raw_data,
        "cloud_provider": cloud_provider,
        "resource_type": "compute" if cloud_provider != "volc" else "ecs",
        "target_schema": "ComputeResource",
    })

    # 断言
    assert result.success, f"{cloud_provider} 转换失败: {result.error}"
    assert result.metadata.get("conversion_method") == expected_method
    assert result.data.cloud_provider == cloud_provider
    assert result.data.resource_id is not None
    assert result.data.state is not None

    print(f"✅ {cloud_provider.upper()} ComputeResource 转换成功 - {result.data.resource_id}")


@pytest.mark.parametrize("cloud_provider,fixture_name", [
    ("aws", "aws_cloudwatch_metric_data"),
    ("azure", "azure_monitor_metric_data"),
    pytest.param("gcp", "gcp_metric_data", marks=pytest.mark.skip(reason="GCP metric 需要规则引擎支持")),
    ("volc", "volc_monitor_metric_data"),
])
@pytest.mark.unit
async def test_metric_conversion(cloud_provider, fixture_name, request):
    """
    参数化测试：多云平台监控指标转换
    覆盖 AWS/Azure/GCP/火山云 的 MetricResult 转换
    """
    raw_data = request.getfixturevalue(fixture_name)

    adapter = DataAdapterAgent()

    result = await adapter.safe_process({
        "raw_data": raw_data,
        "cloud_provider": cloud_provider,
        "resource_type": "metric",
        "target_schema": "MetricResult",
    })

    # 断言
    assert result.success, f"{cloud_provider} 指标转换失败: {result.error}"
    assert result.data.metric_name is not None
    assert len(result.data.datapoints) > 0

    # 验证数据点格式
    for dp in result.data.datapoints:
        assert dp.value is not None
        assert dp.timestamp is not None

    print(f"✅ {cloud_provider.upper()} MetricResult 转换成功 - {len(result.data.datapoints)} 个数据点")


# ==================== 参数化测试 - 数据完整性验证 ====================

@pytest.mark.parametrize("cloud_provider,raw_data,expected_fields", [
    ("aws", {
        "InstanceId": "i-test123",
        "InstanceType": "t3.micro",
        "State": {"Name": "running"},
        "PrivateIpAddress": "10.0.0.1",
    }, ["resource_id", "instance_type", "state", "private_ip"]),

    ("azure", {
        "vmId": "vm-test123",
        "name": "test-vm",
        "hardwareProfile": {"vmSize": "Standard_B1s"},
        "instanceView": {"statuses": [{"code": "PowerState/running"}]},
    }, ["resource_id", "resource_name", "instance_type", "state"]),
])
@pytest.mark.unit
async def test_required_fields_present(cloud_provider, raw_data, expected_fields):
    """
    参数化测试：验证转换后的必需字段是否存在
    """
    adapter = DataAdapterAgent()

    result = await adapter.safe_process({
        "raw_data": raw_data,
        "cloud_provider": cloud_provider,
        "target_schema": "ComputeResource",
    })

    assert result.success

    # 验证所有必需字段都存在
    for field in expected_fields:
        assert hasattr(result.data, field), f"缺少字段: {field}"
        assert getattr(result.data, field) is not None, f"字段 {field} 为空"

    print(f"✅ {cloud_provider.upper()} 必需字段验证通过")


# ==================== 参数化测试 - 边界条件 ====================

@pytest.mark.parametrize("state_input,expected_state", [
    ({"Name": "running"}, "running"),
    ({"Name": "stopped"}, "stopped"),
    ({"Name": "pending"}, "pending"),
    ({"Name": "terminated"}, "terminated"),
])
@pytest.mark.unit
async def test_aws_state_mapping(state_input, expected_state):
    """
    参数化测试：AWS 状态映射
    """
    adapter = DataAdapterAgent()

    raw_data = {
        "InstanceId": "i-test",
        "InstanceType": "t3.micro",
        "State": state_input,
    }

    result = await adapter.safe_process({
        "raw_data": raw_data,
        "cloud_provider": "aws",
        "target_schema": "ComputeResource",
    })

    assert result.success
    assert result.data.state.value == expected_state

    print(f"✅ AWS 状态 {state_input['Name']} → {expected_state}")


# ==================== 参数化测试 - 标签处理 ====================

@pytest.mark.parametrize("cloud_provider,tags_input,expected_tags", [
    ("aws", [
        {"Key": "Name", "Value": "test-server"},
        {"Key": "业务", "Value": "电商平台"},
    ], {"Name": "test-server", "业务": "电商平台"}),

    ("azure", {
        "Environment": "prod",
        "业务": "电商平台",
    }, {"Environment": "prod", "业务": "电商平台"}),

    ("gcp", {
        "env": "prod",
        "业务": "电商平台",
    }, {"env": "prod", "业务": "电商平台"}),
])
@pytest.mark.unit
async def test_tags_processing(cloud_provider, tags_input, expected_tags):
    """
    参数化测试：不同云平台的标签处理
    """
    adapter = DataAdapterAgent()

    # 构造测试数据
    if cloud_provider == "aws":
        raw_data = {
            "InstanceId": "i-test",
            "InstanceType": "t3.micro",
            "State": {"Name": "running"},
            "Tags": tags_input,
        }
    elif cloud_provider == "azure":
        raw_data = {
            "vmId": "vm-test",
            "name": "test-vm",
            "hardwareProfile": {"vmSize": "Standard_B1s"},
            "instanceView": {"statuses": [{"code": "PowerState/running"}]},
            "tags": tags_input,
        }
    else:  # gcp
        raw_data = {
            "id": "123456",
            "name": "test-instance",
            "machineType": "projects/my-project/zones/us-central1-a/machineTypes/n1-standard-1",
            "status": "RUNNING",
            "zone": "projects/my-project/zones/us-central1-a",
            "labels": tags_input,
        }

    result = await adapter.safe_process({
        "raw_data": raw_data,
        "cloud_provider": cloud_provider,
        "resource_type": "compute" if cloud_provider != "gcp" else "gce",
        "target_schema": "ComputeResource",
    })

    assert result.success
    assert result.data.tags is not None

    # 验证业务标签
    if "业务" in expected_tags:
        assert result.data.tags.get("业务") == expected_tags["业务"]

    print(f"✅ {cloud_provider.upper()} 标签处理成功 - {result.data.tags}")


# ==================== 参数化测试 - 容器资源 ====================

@pytest.mark.parametrize("pod_phase,expected_state", [
    ("Running", "running"),
    ("Pending", "pending"),
    ("Succeeded", "terminated"),  # K8s Succeeded 映射到 terminated
    ("Failed", "error"),           # K8s Failed 映射到 error
])
@pytest.mark.unit
@pytest.mark.k8s
async def test_k8s_pod_state_conversion(pod_phase, expected_state, k8s_pod_data):
    """
    参数化测试：Kubernetes Pod 状态转换
    """
    adapter = DataAdapterAgent()

    # 修改测试数据的状态
    k8s_pod_data["status"]["phase"] = pod_phase

    result = await adapter.safe_process({
        "raw_data": k8s_pod_data,
        "cloud_provider": "kubernetes",
        "resource_type": "pod",
        "target_schema": "ContainerResource",
    })

    assert result.success
    assert result.data.state.value == expected_state

    print(f"✅ K8s Pod 状态 {pod_phase} → {expected_state}")


# ==================== 参数化测试 - 错误处理 ====================

@pytest.mark.parametrize("invalid_data,cloud_provider", [
    ({}, "aws"),  # 空数据
    ({"invalid_field": "value"}, "aws"),  # 无效字段
    (None, "aws"),  # None
])
@pytest.mark.unit
async def test_invalid_data_handling(invalid_data, cloud_provider):
    """
    参数化测试：无效数据处理
    测试系统对异常输入的容错能力
    """
    adapter = DataAdapterAgent()

    result = await adapter.safe_process({
        "raw_data": invalid_data,
        "cloud_provider": cloud_provider,
        "target_schema": "ComputeResource",
    })

    # 应该优雅地失败，不应该抛出异常
    # 可以失败，但必须返回有意义的错误信息
    if not result.success:
        assert result.error is not None
        assert len(result.error) > 0
        print(f"✅ 无效数据被正确处理 - {result.error[:50]}")
    else:
        print(f"⚠️ 无效数据被转换成功（可能使用了 LLM 兜底）")
