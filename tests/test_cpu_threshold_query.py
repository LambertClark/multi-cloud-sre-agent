"""
测试EC2 CPU阈值查询功能
验证批量查询EC2实例CPU并过滤高CPU实例的能力
"""
import asyncio
import sys
import os
import io
from datetime import datetime, timedelta, timezone

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.aws_tools import AWSMonitoringTools


# ==================== Mock AWS Clients ====================

class MockCloudWatchClient:
    """Mock CloudWatch客户端"""

    def get_metric_statistics(self, **kwargs):
        """Mock获取指标统计"""
        instance_id = None
        if 'Dimensions' in kwargs:
            for dim in kwargs['Dimensions']:
                if dim['Name'] == 'InstanceId':
                    instance_id = dim['Value']

        # 模拟不同实例的CPU数据
        cpu_data = {
            "i-high-cpu-001": 85.5,  # 高CPU
            "i-high-cpu-002": 92.3,  # 高CPU
            "i-normal-001": 45.2,    # 正常
            "i-normal-002": 30.8,    # 正常
            "i-low-001": 15.3,       # 低CPU
        }

        base_cpu = cpu_data.get(instance_id, 50.0)

        # 生成12个数据点（过去1小时，5分钟间隔）
        now = datetime.now(timezone.utc)
        datapoints = []
        for i in range(12):
            timestamp = now - timedelta(minutes=5 * i)
            # 添加一些随机波动
            variance = (i % 3 - 1) * 5
            avg_value = base_cpu + variance
            max_value = avg_value + 10

            datapoints.append({
                'Timestamp': timestamp,
                'Average': avg_value,
                'Maximum': max_value,
                'Unit': 'Percent'
            })

        return {
            'Label': 'CPUUtilization',
            'Datapoints': datapoints
        }


class MockEC2Client:
    """Mock EC2客户端"""

    def describe_instances(self, **kwargs):
        """Mock描述实例"""
        # 模拟5个EC2实例
        mock_instances = [
            {
                "InstanceId": "i-high-cpu-001",
                "InstanceType": "t3.medium",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "Name", "Value": "web-server-01"},
                    {"Key": "业务", "Value": "电商平台"},
                    {"Key": "环境", "Value": "生产"}
                ]
            },
            {
                "InstanceId": "i-high-cpu-002",
                "InstanceType": "t3.large",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "Name", "Value": "api-server-01"},
                    {"Key": "业务", "Value": "电商平台"},
                    {"Key": "环境", "Value": "生产"}
                ]
            },
            {
                "InstanceId": "i-normal-001",
                "InstanceType": "t3.small",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "Name", "Value": "cache-server-01"},
                    {"Key": "业务", "Value": "电商平台"},
                    {"Key": "环境", "Value": "测试"}
                ]
            },
            {
                "InstanceId": "i-normal-002",
                "InstanceType": "t3.medium",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "Name", "Value": "db-server-01"},
                    {"Key": "业务", "Value": "数据分析"},
                    {"Key": "环境", "Value": "生产"}
                ]
            },
            {
                "InstanceId": "i-low-001",
                "InstanceType": "t3.micro",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "Name", "Value": "test-server-01"},
                    {"Key": "业务", "Value": "测试"},
                    {"Key": "环境", "Value": "开发"}
                ]
            }
        ]

        # 处理Tag过滤
        if 'Filters' in kwargs:
            filtered_instances = []
            for instance in mock_instances:
                match = True
                for filter_item in kwargs['Filters']:
                    if filter_item['Name'].startswith('tag:'):
                        tag_key = filter_item['Name'][4:]
                        tag_values = filter_item['Values']

                        instance_tags = {tag['Key']: tag['Value'] for tag in instance['Tags']}
                        if instance_tags.get(tag_key) not in tag_values:
                            match = False
                            break

                if match:
                    filtered_instances.append(instance)

            mock_instances = filtered_instances

        # 处理InstanceIds过滤
        if 'InstanceIds' in kwargs:
            instance_ids = set(kwargs['InstanceIds'])
            mock_instances = [
                inst for inst in mock_instances
                if inst['InstanceId'] in instance_ids
            ]

        return {
            'Reservations': [{
                'Instances': mock_instances
            }]
        }


# ==================== 测试函数 ====================

async def test_batch_get_all_high_cpu():
    """测试1：查询所有高CPU实例（阈值80%）"""
    print("\n=== 测试1：查询所有高CPU实例 ===")

    # 创建工具实例并注入mock客户端
    tools = AWSMonitoringTools()
    tools._cloudwatch_client = MockCloudWatchClient()
    tools._ec2_client = MockEC2Client()

    # 查询CPU > 80%的实例
    result = await tools._batch_get_ec2_cpu_with_threshold_impl(
        threshold=80.0
    )

    print(f"查询结果:")
    print(f"  成功: {result['success']}")
    print(f"  检查实例总数: {result['total_instances_checked']}")
    print(f"  高CPU实例数: {result['count']}")
    print(f"  阈值: {result['threshold']}%")

    # 验证结果
    assert result['success'] is True
    assert result['total_instances_checked'] == 5
    assert result['count'] == 2  # 应该找到2个高CPU实例

    # 打印详细信息
    print(f"\n高CPU实例详情:")
    for inst in result['high_cpu_instances']:
        print(f"  - {inst['instance_id']} ({inst['instance_type']})")
        print(f"    名称: {inst['tags'].get('Name', 'N/A')}")
        print(f"    业务: {inst['tags'].get('业务', 'N/A')}")
        print(f"    平均CPU: {inst['avg_cpu_utilization']}%")
        print(f"    最大CPU: {inst['max_cpu_utilization']}%")
        print(f"    状态: {inst['state']}")

    # 验证排序（按平均CPU降序）
    cpus = [inst['avg_cpu_utilization'] for inst in result['high_cpu_instances']]
    assert cpus == sorted(cpus, reverse=True), "实例应按CPU降序排列"

    print("✅ 测试1通过")


async def test_batch_get_with_tag_filter():
    """测试2：按业务标签过滤 + CPU阈值"""
    print("\n=== 测试2：按业务标签过滤 ===")

    tools = AWSMonitoringTools()
    tools._cloudwatch_client = MockCloudWatchClient()
    tools._ec2_client = MockEC2Client()

    # 只查询"电商平台"业务的高CPU实例
    result = await tools._batch_get_ec2_cpu_with_threshold_impl(
        threshold=80.0,
        tags={"业务": "电商平台"}
    )

    print(f"查询结果:")
    print(f"  成功: {result['success']}")
    print(f"  检查实例总数: {result['total_instances_checked']}")
    print(f"  高CPU实例数: {result['count']}")

    # 验证结果
    assert result['success'] is True
    assert result['total_instances_checked'] == 3  # 电商平台有3个实例
    assert result['count'] == 2  # 其中2个高CPU

    # 验证所有结果都是电商平台业务
    for inst in result['high_cpu_instances']:
        assert inst['tags'].get('业务') == '电商平台'
        print(f"  - {inst['instance_id']}: 平均CPU {inst['avg_cpu_utilization']}%")

    print("✅ 测试2通过")


async def test_batch_get_lower_threshold():
    """测试3：较低阈值（40%）"""
    print("\n=== 测试3：较低阈值查询 ===")

    tools = AWSMonitoringTools()
    tools._cloudwatch_client = MockCloudWatchClient()
    tools._ec2_client = MockEC2Client()

    # 阈值设为40%，应该找到更多实例
    result = await tools._batch_get_ec2_cpu_with_threshold_impl(
        threshold=40.0
    )

    print(f"查询结果:")
    print(f"  阈值: {result['threshold']}%")
    print(f"  检查实例总数: {result['total_instances_checked']}")
    print(f"  高CPU实例数: {result['count']}")

    # 验证结果
    assert result['success'] is True
    assert result['count'] >= 3  # 至少3个实例应该超过40%

    print(f"\n超过{result['threshold']}%的实例:")
    for inst in result['high_cpu_instances']:
        print(f"  - {inst['instance_id']}: 平均 {inst['avg_cpu_utilization']}%, 最大 {inst['max_cpu_utilization']}%")

    print("✅ 测试3通过")


async def test_batch_get_specific_instances():
    """测试4：指定实例ID查询"""
    print("\n=== 测试4：指定实例ID查询 ===")

    tools = AWSMonitoringTools()
    tools._cloudwatch_client = MockCloudWatchClient()
    tools._ec2_client = MockEC2Client()

    # 只查询特定实例
    result = await tools._batch_get_ec2_cpu_with_threshold_impl(
        threshold=80.0,
        instance_ids=["i-high-cpu-001", "i-normal-001"]
    )

    print(f"查询结果:")
    print(f"  检查实例总数: {result['total_instances_checked']}")
    print(f"  高CPU实例数: {result['count']}")

    # 验证结果
    assert result['success'] is True
    assert result['total_instances_checked'] == 2
    assert result['count'] == 1  # 只有i-high-cpu-001超过80%

    assert result['high_cpu_instances'][0]['instance_id'] == 'i-high-cpu-001'

    print(f"  找到高CPU实例: {result['high_cpu_instances'][0]['instance_id']}")
    print("✅ 测试4通过")


async def test_batch_get_no_results():
    """测试5：无匹配结果（阈值150%）"""
    print("\n=== 测试5：极高阈值查询（无结果） ===")

    tools = AWSMonitoringTools()
    tools._cloudwatch_client = MockCloudWatchClient()
    tools._ec2_client = MockEC2Client()

    # 阈值设为150%，应该找不到实例（mock数据最高只到107%）
    result = await tools._batch_get_ec2_cpu_with_threshold_impl(
        threshold=150.0
    )

    print(f"查询结果:")
    print(f"  阈值: {result['threshold']}%")
    print(f"  检查实例总数: {result['total_instances_checked']}")
    print(f"  高CPU实例数: {result['count']}")

    # 验证结果
    assert result['success'] is True
    assert result['count'] == 0
    assert len(result['high_cpu_instances']) == 0

    print("  正确：未找到任何超过150%的实例")
    print("✅ 测试5通过")


async def test_response_format():
    """测试6：验证返回格式"""
    print("\n=== 测试6：验证返回数据格式 ===")

    tools = AWSMonitoringTools()
    tools._cloudwatch_client = MockCloudWatchClient()
    tools._ec2_client = MockEC2Client()

    result = await tools._batch_get_ec2_cpu_with_threshold_impl(
        threshold=80.0
    )

    # 验证顶层字段
    assert 'success' in result
    assert 'high_cpu_instances' in result
    assert 'count' in result
    assert 'total_instances_checked' in result
    assert 'threshold' in result
    assert 'query_metadata' in result

    print("✓ 顶层字段完整")

    # 验证实例对象格式
    if result['high_cpu_instances']:
        inst = result['high_cpu_instances'][0]
        required_fields = [
            'instance_id', 'instance_type', 'state', 'tags',
            'avg_cpu_utilization', 'max_cpu_utilization',
            'datapoints_count', 'cpu_datapoints'
        ]

        for field in required_fields:
            assert field in inst, f"缺少字段: {field}"

        print("✓ 实例对象字段完整")

        # 验证CPU值是浮点数
        assert isinstance(inst['avg_cpu_utilization'], (int, float))
        assert isinstance(inst['max_cpu_utilization'], (int, float))
        print("✓ CPU值类型正确")

        # 验证tags是字典
        assert isinstance(inst['tags'], dict)
        print("✓ Tags格式正确")

    print("✅ 测试6通过")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("EC2 CPU阈值查询功能测试")
    print("=" * 70)

    await test_batch_get_all_high_cpu()
    await test_batch_get_with_tag_filter()
    await test_batch_get_lower_threshold()
    await test_batch_get_specific_instances()
    await test_batch_get_no_results()
    await test_response_format()

    print("\n" + "=" * 70)
    print("✅ 所有测试通过！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
