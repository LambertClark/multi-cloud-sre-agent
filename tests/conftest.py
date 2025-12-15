"""
pytest 全局配置和 fixtures
提供测试数据工厂、Mock 对象、测试环境配置
"""
import pytest
import asyncio
import os
from typing import Dict, Any
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock


# ==================== 事件循环配置 ====================

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环供整个测试会话使用"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== 测试数据工厂 - AWS ====================

@pytest.fixture
def aws_ec2_data() -> Dict[str, Any]:
    """AWS EC2 测试数据"""
    return {
        "InstanceId": "i-1234567890abcdef0",
        "InstanceType": "t3.medium",
        "State": {"Code": 16, "Name": "running"},
        "LaunchTime": datetime.now(timezone.utc).isoformat(),
        "Placement": {"AvailabilityZone": "us-east-1a"},
        "PrivateIpAddress": "10.0.1.100",
        "PublicIpAddress": "54.123.45.67",
        "VpcId": "vpc-12345678",
        "SubnetId": "subnet-87654321",
        "Tags": [
            {"Key": "Name", "Value": "test-server"},
            {"Key": "Environment", "Value": "test"},
            {"Key": "业务", "Value": "测试业务"},
        ],
    }


@pytest.fixture
def aws_cloudwatch_metric_data() -> Dict[str, Any]:
    """AWS CloudWatch 指标测试数据"""
    return {
        "Label": "CPUUtilization",
        "Datapoints": [
            {
                "Timestamp": datetime.now(timezone.utc).isoformat(),
                "Average": 75.5,
                "Unit": "Percent",
            },
            {
                "Timestamp": datetime.now(timezone.utc).isoformat(),
                "Average": 82.3,
                "Unit": "Percent",
            },
        ],
        "metadata": {
            "namespace": "AWS/EC2",
            "metric_name": "CPUUtilization",
        },
    }


@pytest.fixture
def aws_xray_trace_data() -> Dict[str, Any]:
    """AWS X-Ray trace 测试数据"""
    return {
        "TraceSummaries": [
            {
                "Id": "1-5f8a1234-abcdef1234567890abcd",
                "Duration": 0.523,
                "ResponseTime": 0.523,
                "Http": {"HttpStatus": 200},
                "Annotations": {},
            }
        ]
    }


# ==================== 测试数据工厂 - Azure ====================

@pytest.fixture
def azure_vm_data() -> Dict[str, Any]:
    """Azure VM 测试数据"""
    return {
        "vmId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "test-vm-01",
        "location": "eastus",
        "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
        "instanceView": {
            "statuses": [{"code": "PowerState/running"}]
        },
        "networkProfile": {
            "networkInterfaces": [
                {"primary": True, "privateIpAddress": "10.0.1.10"}
            ]
        },
        "tags": {"Environment": "test", "业务": "测试业务"},
    }


@pytest.fixture
def azure_monitor_metric_data() -> Dict[str, Any]:
    """Azure Monitor 指标测试数据"""
    return {
        "value": [
            {
                "timeseries": [
                    {
                        "data": [
                            {"timeStamp": datetime.now(timezone.utc).isoformat(), "average": 78.2},
                            {"timeStamp": datetime.now(timezone.utc).isoformat(), "average": 85.6},
                        ]
                    }
                ]
            }
        ],
        "namespace": "Microsoft.Compute/virtualMachines",
        "resourceregion": "eastus",
    }


# ==================== 测试数据工厂 - GCP ====================

@pytest.fixture
def gcp_instance_data() -> Dict[str, Any]:
    """GCP Compute Engine 测试数据"""
    return {
        "id": "123456789012345678",
        "name": "test-instance-01",
        "machineType": "projects/my-project/zones/us-central1-a/machineTypes/n1-standard-2",
        "status": "RUNNING",
        "zone": "projects/my-project/zones/us-central1-a",
        "networkInterfaces": [{"networkIP": "10.128.0.2"}],
        "labels": {"env": "test", "业务": "测试业务"},
    }


@pytest.fixture
def gcp_metric_data() -> Dict[str, Any]:
    """GCP Cloud Monitoring 指标测试数据"""
    return {
        "metric": {
            "type": "compute.googleapis.com/instance/cpu/utilization",
            "labels": {}
        },
        "resource": {
            "type": "gce_instance",
            "labels": {"instance_id": "123456789", "zone": "us-central1-a"}
        },
        "metricKind": "GAUGE",
        "valueType": "DOUBLE",
        "points": [
            {
                "interval": {"endTime": datetime.now(timezone.utc).isoformat()},
                "value": {"doubleValue": 72.4}
            },
            {
                "interval": {"endTime": datetime.now(timezone.utc).isoformat()},
                "value": {"doubleValue": 80.1}
            },
        ],
    }


# ==================== 测试数据工厂 - 火山云 ====================

@pytest.fixture
def volc_ecs_data() -> Dict[str, Any]:
    """火山云 ECS 测试数据"""
    return {
        "InstanceId": "i-volc1234567890",
        "InstanceName": "test-ecs-01",
        "Status": "RUNNING",
        "InstanceType": "ecs.g1.large",
        "ZoneId": "cn-beijing-a",
        "VpcId": "vpc-abc123",
        "NetworkInterfaces": [
            {"PrimaryIpAddress": "172.16.0.10"}
        ],
        "Tags": {"业务": "测试业务"},  # 修改为字典格式
    }


@pytest.fixture
def volc_monitor_metric_data() -> Dict[str, Any]:
    """火山云 VeMonitor 指标测试数据"""
    return {
        "MetricName": "CpuUtil",
        "Namespace": "VCM/ECS",
        "Data": [
            {"Timestamp": int(datetime.now(timezone.utc).timestamp()), "Value": 68.5},
            {"Timestamp": int(datetime.now(timezone.utc).timestamp()), "Value": 75.2},
        ],
    }


# ==================== 测试数据工厂 - Kubernetes ====================

@pytest.fixture
def k8s_pod_data() -> Dict[str, Any]:
    """Kubernetes Pod 测试数据"""
    return {
        "kind": "Pod",
        "metadata": {
            "name": "test-pod",
            "namespace": "default",
            "labels": {"app": "test-app", "业务": "测试业务"},
            "creationTimestamp": "2025-01-10T10:00:00Z",
        },
        "spec": {
            "nodeName": "node-01",
            "containers": [
                {
                    "name": "test-container",
                    "image": "nginx:latest",
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    },
                }
            ],
        },
        "status": {
            "phase": "Running",
            "podIP": "10.244.1.10",
            "containerStatuses": [{"restartCount": 0, "ready": True}],
        },
    }


# ==================== Mock 对象 ====================

@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端"""
    mock = MagicMock()

    # Mock chat.completions.create 方法
    async_mock = AsyncMock()
    async_mock.return_value = Mock(
        choices=[
            Mock(
                message=Mock(
                    content='{"resource_id": "test-id", "state": "running", "resource_type": "ec2"}'
                )
            )
        ]
    )
    mock.chat.completions.create = async_mock

    return mock


@pytest.fixture
def mock_rag_system():
    """Mock RAG 系统"""
    mock = AsyncMock()
    mock.query.return_value = {
        "success": True,
        "documents": ["ComputeResource schema documentation..."],
        "relevance_score": 0.95,
    }
    mock.index_documents.return_value = {
        "success": True,
        "documents_indexed": 5,
    }
    return mock


@pytest.fixture
def mock_aws_client():
    """Mock AWS Boto3 客户端"""
    mock = MagicMock()
    # 可以根据需要添加具体的 mock 方法
    return mock


@pytest.fixture
def mock_azure_client():
    """Mock Azure 客户端"""
    mock = MagicMock()
    return mock


# ==================== pytest hooks ====================

def pytest_configure(config):
    """pytest 启动时的配置"""
    # 创建报告目录
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)

    # 设置测试环境变量
    os.environ["TESTING"] = "true"

    print("\n" + "="*60)
    print("多云SRE Agent 自动化测试框架")
    print("="*60)


def pytest_collection_modifyitems(config, items):
    """修改测试收集项"""
    for item in items:
        # 为所有异步测试添加 asyncio 标记
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)

        # 根据文件名自动添加标记
        if "aws" in item.nodeid.lower():
            item.add_marker(pytest.mark.aws)
        if "azure" in item.nodeid.lower():
            item.add_marker(pytest.mark.azure)
        if "gcp" in item.nodeid.lower():
            item.add_marker(pytest.mark.gcp)
        if "volc" in item.nodeid.lower():
            item.add_marker(pytest.mark.volc)
        if "k8s" in item.nodeid.lower() or "kubernetes" in item.nodeid.lower():
            item.add_marker(pytest.mark.k8s)


def pytest_html_report_title(report):
    """自定义 HTML 报告标题"""
    report.title = "多云SRE Agent 自动化测试报告"


@pytest.fixture(autouse=True)
def reset_environment():
    """每个测试前后重置环境"""
    # 测试前的设置
    yield
    # 测试后的清理（如果需要）
    pass
