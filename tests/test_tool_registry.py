"""
工具注册表测试
验证工具注册、查询、指标更新等功能
"""
import sys
import io
import os
import shutil
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.tool_registry import (
    ToolRegistry,
    GeneratedTool,
    ToolParameter,
    ToolMetrics,
    ToolStatus
)


def test_tool_registration():
    """测试工具注册"""
    print("\n" + "=" * 70)
    print("测试1：工具注册")
    print("=" * 70)

    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry(registry_dir=tmpdir)

        # 创建测试工具
        tool = GeneratedTool(
            name="list_ec2_instances",
            description="列出所有EC2实例",
            code="""
import boto3

def list_ec2_instances(region='us-east-1'):
    ec2 = boto3.client('ec2', region_name=region)
    response = ec2.describe_instances()
    return response['Reservations']
""",
            test_code="""
def test_list_ec2_instances():
    result = list_ec2_instances()
    assert isinstance(result, list)
""",
            parameters=[
                ToolParameter(
                    name="region",
                    type="str",
                    description="AWS区域",
                    required=False,
                    default="us-east-1"
                )
            ],
            return_type="List[Dict]",
            cloud_provider="aws",
            service="ec2",
            category="query",
            tags=["ec2", "instances", "list"]
        )

        # 注册工具
        print("\n【用例1】注册新工具")
        result = registry.register(tool)

        print(f"注册成功: {result['success']}")
        print(f"工具ID: {result['tool_id']}")
        print(f"工具名称: {result['tool_name']}")
        print(f"版本: {result['version']}")

        assert result['success'], "工具注册应该成功"
        assert result['tool_name'] == "list_ec2_instances"
        print("✅ 通过")

        # 尝试注册相同工具
        print("\n【用例2】注册相同工具（代码相同）")
        result2 = registry.register(tool)

        print(f"注册成功: {result2['success']}")
        print(f"原因: {result2.get('reason', 'N/A')}")

        assert not result2['success'], "相同工具不应重复注册"
        print("✅ 通过 - 正确拒绝重复注册")

        # 创建更新版本的工具（代码不同）
        print("\n【用例3】注册升级版本（代码不同）")
        updated_tool = GeneratedTool(
            name="list_ec2_instances",
            description="列出所有EC2实例（升级版）",
            code="""
import boto3

def list_ec2_instances(region='us-east-1', filters=None):
    \"\"\"升级版：支持过滤器\"\"\"
    ec2 = boto3.client('ec2', region_name=region)
    response = ec2.describe_instances(Filters=filters or [])
    return response['Reservations']
""",
            test_code="""
def test_list_ec2_instances():
    result = list_ec2_instances()
    assert isinstance(result, list)
""",
            parameters=[
                ToolParameter(
                    name="region",
                    type="str",
                    description="AWS区域",
                    required=False,
                    default="us-east-1"
                ),
                ToolParameter(
                    name="filters",
                    type="List[Dict]",
                    description="过滤器",
                    required=False,
                    default=None
                )
            ],
            return_type="List[Dict]",
            cloud_provider="aws",
            service="ec2",
            category="query",
            tags=["ec2", "instances", "list"]
        )

        result3 = registry.register(updated_tool)

        print(f"注册成功: {result3['success']}")
        print(f"新版本: {result3['version']}")
        print(f"是否更新: {result3.get('is_update', False)}")

        assert result3['success'], "代码变化应该创建新版本"
        assert result3['version'] == "1.0.1", "版本号应该递增"
        assert result3.get('is_update') == True, "should be an update"
        print("✅ 通过 - 成功创建新版本")

    print("\n✅ 工具注册测试完成")


def test_tool_search():
    """测试工具搜索"""
    print("\n" + "=" * 70)
    print("测试2：工具搜索")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry(registry_dir=tmpdir)

        # 注册多个工具
        tools = [
            GeneratedTool(
                name="list_ec2_instances",
                description="列出EC2实例",
                code="# code",
                test_code="# test",
                parameters=[],
                return_type="List",
                cloud_provider="aws",
                service="ec2",
                category="query",
                tags=["ec2", "instances"]
            ),
            GeneratedTool(
                name="list_s3_buckets",
                description="列出S3存储桶",
                code="# code",
                test_code="# test",
                parameters=[],
                return_type="List",
                cloud_provider="aws",
                service="s3",
                category="query",
                tags=["s3", "buckets"]
            ),
            GeneratedTool(
                name="get_cloudwatch_metrics",
                description="获取CloudWatch指标",
                code="# code",
                test_code="# test",
                parameters=[],
                return_type="Dict",
                cloud_provider="aws",
                service="cloudwatch",
                category="monitor",
                tags=["cloudwatch", "metrics"]
            ),
            GeneratedTool(
                name="list_k8s_pods",
                description="列出Kubernetes Pod",
                code="# code",
                test_code="# test",
                parameters=[],
                return_type="List",
                cloud_provider="kubernetes",
                service="core",
                category="query",
                tags=["kubernetes", "pods"]
            )
        ]

        for tool in tools:
            registry.register(tool)

        print(f"注册了 {len(tools)} 个工具\n")

        # 测试1：按云平台搜索
        print("【用例1】按云平台搜索（AWS）")
        aws_tools = registry.search_tools(cloud_provider="aws")

        print(f"找到 {len(aws_tools)} 个AWS工具:")
        for t in aws_tools:
            print(f"  - {t.name} ({t.service})")

        assert len(aws_tools) == 3, "应该找到3个AWS工具"
        print("✅ 通过")

        # 测试2：按服务搜索
        print("\n【用例2】按服务搜索（ec2）")
        ec2_tools = registry.search_tools(service="ec2")

        print(f"找到 {len(ec2_tools)} 个EC2工具:")
        for t in ec2_tools:
            print(f"  - {t.name}")

        assert len(ec2_tools) == 1, "应该找到1个EC2工具"
        print("✅ 通过")

        # 测试3：按查询文本搜索
        print("\n【用例3】按查询文本搜索（'list'）")
        list_tools = registry.search_tools(query="list")

        print(f"找到 {len(list_tools)} 个包含'list'的工具:")
        for t in list_tools:
            print(f"  - {t.name}")

        assert len(list_tools) == 3, "应该找到3个包含'list'的工具"
        print("✅ 通过")

        # 测试4：按标签搜索
        print("\n【用例4】按标签搜索（pods）")
        pod_tools = registry.search_tools(tags=["pods"])

        print(f"找到 {len(pod_tools)} 个带'pods'标签的工具:")
        for t in pod_tools:
            print(f"  - {t.name}")

        assert len(pod_tools) == 1, "应该找到1个带'pods'标签的工具"
        print("✅ 通过")

    print("\n✅ 工具搜索测试完成")


def test_metrics_update():
    """测试指标更新和质量评分"""
    print("\n" + "=" * 70)
    print("测试3：指标更新和质量评分")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry(registry_dir=tmpdir)

        # 注册工具
        tool = GeneratedTool(
            name="test_tool",
            description="测试工具",
            code="# code",
            test_code="# test",
            parameters=[],
            return_type="str",
            cloud_provider="aws",
            service="ec2",
            category="query"
        )

        registry.register(tool)

        print("\n【用例1】初始状态")
        registered_tool = registry.get_tool("test_tool")
        print(f"总调用次数: {registered_tool.metrics.total_calls}")
        print(f"成功率: {registered_tool.metrics.success_rate:.2%}")
        print(f"质量分数: {registered_tool.metrics.quality_score:.1f}")

        assert registered_tool.metrics.total_calls == 0
        print("✅ 通过")

        # 模拟成功调用
        print("\n【用例2】模拟10次成功调用")
        for i in range(10):
            registry.update_metrics("test_tool", success=True, execution_time=0.5)

        tool_after = registry.get_tool("test_tool")
        print(f"总调用次数: {tool_after.metrics.total_calls}")
        print(f"成功次数: {tool_after.metrics.successful_calls}")
        print(f"成功率: {tool_after.metrics.success_rate:.2%}")
        print(f"平均执行时间: {tool_after.metrics.average_execution_time:.3f}秒")
        print(f"质量分数: {tool_after.metrics.quality_score:.1f}")

        assert tool_after.metrics.total_calls == 10
        assert tool_after.metrics.success_rate == 1.0
        print("✅ 通过")

        # 模拟失败调用
        print("\n【用例3】模拟5次失败调用")
        for i in range(5):
            registry.update_metrics("test_tool", success=False, execution_time=2.0)

        tool_mixed = registry.get_tool("test_tool")
        print(f"总调用次数: {tool_mixed.metrics.total_calls}")
        print(f"成功次数: {tool_mixed.metrics.successful_calls}")
        print(f"失败次数: {tool_mixed.metrics.failed_calls}")
        print(f"成功率: {tool_mixed.metrics.success_rate:.2%}")
        print(f"质量分数: {tool_mixed.metrics.quality_score:.1f}")

        assert tool_mixed.metrics.total_calls == 15
        assert tool_mixed.metrics.successful_calls == 10
        assert tool_mixed.metrics.failed_calls == 5
        assert abs(tool_mixed.metrics.success_rate - 0.6667) < 0.01
        print("✅ 通过")

    print("\n✅ 指标更新测试完成")


def test_persistence():
    """测试持久化"""
    print("\n" + "=" * 70)
    print("测试4：持久化")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        print("\n【用例1】保存工具到磁盘")

        # 创建注册表并注册工具
        registry1 = ToolRegistry(registry_dir=tmpdir)

        tool = GeneratedTool(
            name="test_persistence",
            description="测试持久化",
            code="def test(): return 'hello'",
            test_code="def test_test(): assert test() == 'hello'",
            parameters=[],
            return_type="str",
            cloud_provider="aws",
            service="ec2",
            category="query"
        )

        registry1.register(tool)
        print(f"注册表1工具数: {len(registry1.tools)}")

        # 创建新注册表实例，应该加载现有工具
        print("\n【用例2】从磁盘加载工具")
        registry2 = ToolRegistry(registry_dir=tmpdir)

        print(f"注册表2工具数: {len(registry2.tools)}")
        loaded_tool = registry2.get_tool("test_persistence")

        assert loaded_tool is not None, "应该加载到工具"
        assert loaded_tool.name == "test_persistence"
        assert loaded_tool.code == tool.code
        print("✅ 通过 - 成功从磁盘加载")

        # 检查代码文件是否存在
        print("\n【用例3】检查代码文件")
        code_file = os.path.join(tmpdir, "aws", "ec2", "test_persistence.py")
        assert os.path.exists(code_file), "代码文件应该存在"

        with open(code_file, 'r', encoding='utf-8') as f:
            code_content = f.read()
            print(f"代码文件前80字符: {code_content[:80]}...")
            # 检查文件包含工具名和代码
            assert "测试持久化" in code_content or "test_persistence" in code_content
            assert "def test():" in code_content

        print("✅ 通过 - 代码文件正确保存")

    print("\n✅ 持久化测试完成")


def test_statistics():
    """测试统计信息"""
    print("\n" + "=" * 70)
    print("测试5：统计信息")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry(registry_dir=tmpdir)

        # 注册多个工具
        for i in range(5):
            tool = GeneratedTool(
                name=f"tool_{i}",
                description=f"工具{i}",
                code="# code",
                test_code="# test",
                parameters=[],
                return_type="str",
                cloud_provider="aws" if i < 3 else "azure",
                service="ec2" if i % 2 == 0 else "s3",
                category="query"
            )
            registry.register(tool)

            # 给一些工具添加指标
            for j in range(i + 1):
                registry.update_metrics(f"tool_{i}", success=True, execution_time=0.5)

        # 获取统计
        stats = registry.get_statistics()

        print(f"\n总工具数: {stats['total_tools']}")
        print(f"活跃工具数: {stats['active_tools']}")
        print(f"平均质量分数: {stats['average_quality_score']:.1f}")

        print(f"\n按云平台分布:")
        for provider, count in stats['by_provider'].items():
            print(f"  {provider}: {count}个工具")

        print(f"\nTop工具:")
        for i, tool_info in enumerate(stats['top_tools'][:3], 1):
            print(f"  {i}. {tool_info['name']} - 质量分数: {tool_info['quality_score']:.1f}")

        assert stats['total_tools'] == 5
        assert stats['active_tools'] == 5
        assert len(stats['top_tools']) > 0
        print("\n✅ 通过")

    print("\n✅ 统计信息测试完成")


def main():
    """运行所有测试"""
    print("=" * 70)
    print("工具注册表测试")
    print("=" * 70)

    try:
        # 1. 工具注册
        test_tool_registration()

        # 2. 工具搜索
        test_tool_search()

        # 3. 指标更新
        test_metrics_update()

        # 4. 持久化
        test_persistence()

        # 5. 统计信息
        test_statistics()

        print("\n" + "=" * 70)
        print("测试总结")
        print("=" * 70)
        print("✅ 所有测试通过！")

        print("\n功能验证:")
        print("1. ✅ 工具注册（新工具、重复工具、版本升级）")
        print("2. ✅ 工具搜索（云平台、服务、查询文本、标签）")
        print("3. ✅ 指标更新（调用次数、成功率、质量评分）")
        print("4. ✅ 持久化（保存/加载工具、代码文件）")
        print("5. ✅ 统计信息（总览、分布、Top工具）")

        print("\n工具注册表特性:")
        print("- 自动版本管理（代码变化时升级版本）")
        print("- 质量评分系统（成功率70% + 使用频率20% + 执行速度10%）")
        print("- 多维度搜索（云平台、服务、分类、标签、查询文本）")
        print("- 持久化存储（索引文件 + 独立代码文件）")
        print("- 统计分析（工具分布、Top工具推荐）")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
