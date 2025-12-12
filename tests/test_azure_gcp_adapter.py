"""
测试Azure和GCP数据适配功能
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


async def test_azure_vm():
    """测试Azure VM转换"""
    print("\n=== 测试Azure VM → ComputeResource ===")

    adapter = DataAdapterAgent()

    # 模拟Azure VM响应
    azure_vm_data = {
        "id": "/subscriptions/xxx/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/web-vm-01",
        "name": "web-vm-01",
        "location": "eastus",
        "vmId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "hardwareProfile": {
            "vmSize": "Standard_D2s_v3"
        },
        "networkProfile": {
            "networkInterfaces": [
                {
                    "id": "/subscriptions/xxx/resourceGroups/rg-prod/providers/Microsoft.Network/networkInterfaces/web-vm-01-nic",
                    "privateIPAddress": "10.0.1.10"
                }
            ]
        },
        "instanceView": {
            "statuses": [
                {
                    "code": "ProvisioningState/succeeded",
                    "level": "Info",
                    "displayStatus": "Provisioning succeeded"
                },
                {
                    "code": "PowerState/running",
                    "level": "Info",
                    "displayStatus": "VM running"
                }
            ]
        },
        "tags": {
            "Environment": "Production",
            "业务": "电商平台",
            "Owner": "DevOps Team"
        }
    }

    result = await adapter.safe_process({
        "raw_data": azure_vm_data,
        "cloud_provider": "azure",
        "resource_type": "vm",
        "target_schema": "ComputeResource"
    })

    if result.success:
        vm = result.data
        print(f"✅ 转换成功 (方法: {result.metadata.get('conversion_method')})")
        print(f"   资源ID: {vm.resource_id}")
        print(f"   资源名称: {vm.resource_name}")
        print(f"   资源类型: {vm.resource_type.value}")
        print(f"   云平台: {vm.cloud_provider}")
        print(f"   状态: {vm.state.value}")
        print(f"   区域: {vm.region}")
        print(f"   实例类型: {vm.instance_type}")
        print(f"   业务标签: {vm.tags.get('业务')}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_azure_metric():
    """测试Azure Monitor Metric转换"""
    print("\n=== 测试Azure Monitor Metric → MetricResult ===")

    adapter = DataAdapterAgent()

    # 模拟Azure Monitor响应
    azure_metric_data = {
        "namespace": "Microsoft.Compute/virtualMachines",
        "resourceregion": "eastus",
        "value": [
            {
                "id": "/subscriptions/xxx/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/web-vm-01/providers/Microsoft.Insights/metrics/Percentage CPU",
                "type": "Microsoft.Insights/metrics",
                "name": {
                    "value": "Percentage CPU",
                    "localizedValue": "Percentage CPU"
                },
                "unit": "Percent",
                "timeseries": [
                    {
                        "metadatavalues": [],
                        "data": [
                            {
                                "timeStamp": "2025-01-10T10:00:00Z",
                                "average": 65.2
                            },
                            {
                                "timeStamp": "2025-01-10T10:05:00Z",
                                "average": 72.8
                            },
                            {
                                "timeStamp": "2025-01-10T10:10:00Z",
                                "average": 88.5
                            }
                        ]
                    }
                ]
            }
        ]
    }

    result = await adapter.safe_process({
        "raw_data": azure_metric_data,
        "cloud_provider": "azure",
        "target_schema": "MetricResult"
    })

    if result.success:
        metric = result.data
        print(f"✅ 转换成功 (方法: {result.metadata.get('conversion_method')})")
        print(f"   指标名称: {metric.metric_name}")
        print(f"   数据点数量: {len(metric.datapoints)}")
        if metric.datapoints:
            print(f"   最新值: {metric.datapoints[-1].value}")
            print(f"   最早值: {metric.datapoints[0].value}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_gcp_gce():
    """测试GCP Compute Engine转换"""
    print("\n=== 测试GCP GCE → ComputeResource ===")

    adapter = DataAdapterAgent()

    # 模拟GCP GCE响应
    gcp_gce_data = {
        "id": "123456789012345678",
        "name": "web-instance-01",
        "description": "Production web server",
        "machineType": "https://www.googleapis.com/compute/v1/projects/my-project/zones/us-central1-a/machineTypes/n1-standard-2",
        "status": "RUNNING",
        "zone": "https://www.googleapis.com/compute/v1/projects/my-project/zones/us-central1-a",
        "networkInterfaces": [
            {
                "network": "https://www.googleapis.com/compute/v1/projects/my-project/global/networks/default",
                "networkIP": "10.128.0.2",
                "name": "nic0",
                "accessConfigs": [
                    {
                        "type": "ONE_TO_ONE_NAT",
                        "name": "External NAT",
                        "natIP": "35.123.45.67"
                    }
                ]
            }
        ],
        "creationTimestamp": "2025-01-10T10:00:00.000-08:00",
        "labels": {
            "environment": "production",
            "业务": "电商平台",
            "team": "backend"
        },
        "tags": {
            "items": ["http-server", "https-server"]
        }
    }

    result = await adapter.safe_process({
        "raw_data": gcp_gce_data,
        "cloud_provider": "gcp",
        "resource_type": "gce",
        "target_schema": "ComputeResource"
    })

    if result.success:
        gce = result.data
        print(f"✅ 转换成功 (方法: {result.metadata.get('conversion_method')})")
        print(f"   资源ID: {gce.resource_id}")
        print(f"   资源名称: {gce.resource_name}")
        print(f"   资源类型: {gce.resource_type.value}")
        print(f"   云平台: {gce.cloud_provider}")
        print(f"   状态: {gce.state.value}")
        print(f"   区域: {gce.region}")
        print(f"   可用区: {gce.availability_zone}")
        print(f"   实例类型: {gce.instance_type}")
        print(f"   内网IP: {gce.private_ip}")
        print(f"   公网IP: {gce.public_ip}")
        print(f"   业务标签: {gce.tags.get('业务')}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def test_gcp_metric():
    """测试GCP Cloud Monitoring Metric转换"""
    print("\n=== 测试GCP Cloud Monitoring Metric → MetricResult ===")

    adapter = DataAdapterAgent()

    # 模拟GCP Cloud Monitoring响应
    gcp_metric_data = {
        "timeSeries": [
            {
                "metric": {
                    "labels": {
                        "instance_name": "web-instance-01"
                    },
                    "type": "compute.googleapis.com/instance/cpu/utilization"
                },
                "resource": {
                    "type": "gce_instance",
                    "labels": {
                        "project_id": "my-project",
                        "instance_id": "123456789012345678",
                        "zone": "us-central1-a"
                    }
                },
                "metricKind": "GAUGE",
                "valueType": "DOUBLE",
                "points": [
                    {
                        "interval": {
                            "startTime": "2025-01-10T10:00:00Z",
                            "endTime": "2025-01-10T10:00:00Z"
                        },
                        "value": {
                            "doubleValue": 0.68
                        }
                    },
                    {
                        "interval": {
                            "startTime": "2025-01-10T10:01:00Z",
                            "endTime": "2025-01-10T10:01:00Z"
                        },
                        "value": {
                            "doubleValue": 0.75
                        }
                    },
                    {
                        "interval": {
                            "startTime": "2025-01-10T10:02:00Z",
                            "endTime": "2025-01-10T10:02:00Z"
                        },
                        "value": {
                            "doubleValue": 0.82
                        }
                    }
                ]
            }
        ]
    }

    result = await adapter.safe_process({
        "raw_data": gcp_metric_data,
        "cloud_provider": "gcp",
        "target_schema": "MetricResult"
    })

    if result.success:
        metric = result.data
        print(f"✅ 转换成功 (方法: {result.metadata.get('conversion_method')})")
        print(f"   指标名称: {metric.metric_name}")
        print(f"   数据点数量: {len(metric.datapoints)}")
        if metric.datapoints:
            print(f"   最新值: {metric.datapoints[-1].value}")
            print(f"   值范围: {metric.datapoints[0].value:.2f} - {metric.datapoints[-1].value:.2f}")
    else:
        print(f"❌ 转换失败: {result.error}")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("Azure & GCP 数据适配测试")
    print("=" * 70)

    await test_azure_vm()
    await test_azure_metric()
    await test_gcp_gce()
    await test_gcp_metric()

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
