"""
文档系统集成测试
测试SpecDocAgent + DocumentCache + RAG的完整流程
"""
import asyncio
import sys
import io
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.doc_cache import DocumentCache
from agents.spec_doc_agent import SpecDocAgent
from agents.base_agent import AgentResponse


async def test_full_document_flow():
    """测试1：完整文档获取流程"""
    print("\n=== 测试1：完整文档获取流程 ===")

    # 创建真实的SpecDocAgent（但mock网络请求）
    spec_agent = SpecDocAgent()

    # Mock网络请求
    mock_html_content = """
    <html>
    <body>
        <h1>Kubernetes API</h1>
        <div class="operation">
            <h2>list_pods</h2>
            <p>List all pods in a namespace</p>
            <div class="parameter">
                <span class="name">namespace</span>
                <span class="type">string</span>
                <span class="required">required</span>
            </div>
        </div>
    </body>
    </html>
    """

    # Mock SpecDocAgent的_get_doc_urls方法
    def mock_get_doc_urls(cloud_provider, service, doc_type):
        return [f"https://example.com/{cloud_provider}/{service}/api"]

    # Mock SpecDocAgent的_fetch_specifications方法
    async def mock_fetch_specs(doc_urls, cloud_provider, service):
        return {
            "operations": [
                {
                    "name": "list_pods",
                    "description": "List all pods in a namespace",
                    "parameters": [
                        {
                            "name": "namespace",
                            "type": "string",
                            "required": True,
                            "description": "The namespace to list pods from"
                        }
                    ],
                    "path": "/api/v1/namespaces/{namespace}/pods",
                    "method": "GET"
                }
            ],
            "examples": [
                {
                    "operation": "list_pods",
                    "code": "kubectl get pods -n default"
                }
            ]
        }

    with patch.object(spec_agent, '_get_doc_urls', side_effect=mock_get_doc_urls), \
         patch.object(spec_agent, '_fetch_specifications', side_effect=mock_fetch_specs):
        # 创建DocumentCache
        cache = DocumentCache(
            rag_system=None,  # 暂不测试RAG
            spec_doc_agent=spec_agent,
            default_max_age_hours=24
        )

        # 第一次请求：应该拉取新文档
        print("\n1️⃣ 第一次请求（应该拉取新文档）")
        result1 = await cache.get_or_fetch("kubernetes", "core", "list_pods")

        print(f"   成功: {result1['success']}")
        print(f"   来源: {result1['source']}")
        print(f"   文档数: {len(result1.get('documents', []))}")

        assert result1["success"], "第一次请求应该成功"
        assert result1["source"] == "fresh_fetch", "应该是新拉取"
        assert len(result1["documents"]) == 1, "应该有1个API操作"
        assert result1["documents"][0]["operation_name"] == "list_pods"
        assert result1["documents"][0]["cloud_provider"] == "kubernetes"

        # 第二次请求：应该命中内存缓存
        print("\n2️⃣ 第二次请求（应该命中缓存）")
        result2 = await cache.get_or_fetch("kubernetes", "core", "list_pods")

        print(f"   成功: {result2['success']}")
        print(f"   来源: {result2['source']}")

        assert result2["success"], "第二次请求应该成功"
        assert result2["source"] == "memory_cache", "应该命中内存缓存"
        assert result2["documents"] == result1["documents"], "文档内容应该一致"

        # 验证缓存统计
        stats = cache.get_cache_stats()
        print(f"\n📊 缓存统计: {stats}")
        assert stats["total_cached"] == 1, "应该有1个缓存条目"
        assert stats["by_provider"]["kubernetes"] == 1

    print("✅ 测试1通过：完整流程工作正常")


async def test_multi_provider_caching():
    """测试2：多云平台缓存管理"""
    print("\n=== 测试2：多云平台缓存管理 ===")

    spec_agent = SpecDocAgent()

    # Mock文档URL获取
    def mock_get_doc_urls(cloud_provider, service, doc_type):
        return [f"https://example.com/{cloud_provider}/{service}/api"]

    # Mock不同云平台的文档
    async def mock_fetch_different_specs(doc_urls, cloud_provider, service):
        specs = {
            "kubernetes": {
                "operations": [{"name": "list_pods", "description": "K8s pods"}],
                "examples": []
            },
            "aws": {
                "operations": [{"name": "describe_instances", "description": "EC2 instances"}],
                "examples": []
            },
            "gcp": {
                "operations": [{"name": "list_instances", "description": "GCE instances"}],
                "examples": []
            }
        }
        return specs.get(cloud_provider, {"operations": [], "examples": []})

    with patch.object(spec_agent, '_get_doc_urls', side_effect=mock_get_doc_urls), \
         patch.object(spec_agent, '_fetch_specifications', side_effect=mock_fetch_different_specs):
        cache = DocumentCache(
            rag_system=None,
            spec_doc_agent=spec_agent
        )

        # 缓存3个不同云平台的文档
        print("\n1️⃣ 缓存3个云平台的文档")
        await cache.get_or_fetch("kubernetes", "core", "list_pods")
        await cache.get_or_fetch("aws", "ec2", "describe_instances")
        await cache.get_or_fetch("gcp", "compute", "list_instances")

        stats = cache.get_cache_stats()
        print(f"   缓存统计: {stats}")
        assert stats["total_cached"] == 3, "应该有3个缓存"
        assert len(stats["by_provider"]) == 3, "应该有3个云平台"

        # 清除kubernetes缓存
        print("\n2️⃣ 清除kubernetes缓存")
        cache.clear_cache("kubernetes")

        stats2 = cache.get_cache_stats()
        print(f"   剩余缓存: {stats2}")
        assert stats2["total_cached"] == 2, "应该剩2个缓存"
        assert "kubernetes" not in stats2["by_provider"], "kubernetes应该被清除"

        # 验证kubernetes需要重新拉取
        print("\n3️⃣ 验证kubernetes需要重新拉取")
        result = await cache.get_or_fetch("kubernetes", "core", "list_pods")
        assert result["source"] == "fresh_fetch", "应该重新拉取"

        # AWS和GCP仍然命中缓存
        result_aws = await cache.get_or_fetch("aws", "ec2", "describe_instances")
        result_gcp = await cache.get_or_fetch("gcp", "compute", "list_instances")
        assert result_aws["source"] == "memory_cache", "AWS应该命中缓存"
        assert result_gcp["source"] == "memory_cache", "GCP应该命中缓存"

    print("✅ 测试2通过：多云平台缓存管理正常")


async def test_cache_expiration_refetch():
    """测试3：缓存过期自动重新拉取"""
    print("\n=== 测试3：缓存过期自动重新拉取 ===")

    spec_agent = SpecDocAgent()

    # Mock文档URL获取
    def mock_get_doc_urls(cloud_provider, service, doc_type):
        return [f"https://example.com/{cloud_provider}/{service}/api"]

    fetch_count = {"count": 0}

    async def mock_fetch_with_counter(doc_urls, cloud_provider, service):
        fetch_count["count"] += 1
        return {
            "operations": [
                {
                    "name": f"operation_v{fetch_count['count']}",
                    "description": f"Version {fetch_count['count']}"
                }
            ],
            "examples": []
        }

    with patch.object(spec_agent, '_get_doc_urls', side_effect=mock_get_doc_urls), \
         patch.object(spec_agent, '_fetch_specifications', side_effect=mock_fetch_with_counter):
        # 设置很短的过期时间（0.002小时 ≈ 7秒）
        cache = DocumentCache(
            rag_system=None,
            spec_doc_agent=spec_agent,
            default_max_age_hours=0.002
        )

        # 第一次拉取
        print("\n1️⃣ 第一次拉取")
        result1 = await cache.get_or_fetch("aws", "s3", "list_buckets")
        print(f"   拉取次数: {fetch_count['count']}")
        print(f"   操作名: {result1['documents'][0]['operation_name']}")
        assert fetch_count["count"] == 1, "应该拉取1次"
        assert result1["source"] == "fresh_fetch"

        # 立即第二次请求（应该命中缓存）
        print("\n2️⃣ 立即第二次请求（缓存命中）")
        result2 = await cache.get_or_fetch("aws", "s3", "list_buckets")
        print(f"   拉取次数: {fetch_count['count']}")
        print(f"   来源: {result2['source']}")
        assert fetch_count["count"] == 1, "不应该再次拉取"
        assert result2["source"] == "memory_cache"

        # 等待过期
        print("\n3️⃣ 等待缓存过期（8秒）...")
        await asyncio.sleep(8)

        # 第三次请求（缓存已过期，应该重新拉取）
        print("\n4️⃣ 过期后请求（应该重新拉取）")
        result3 = await cache.get_or_fetch("aws", "s3", "list_buckets")
        print(f"   拉取次数: {fetch_count['count']}")
        print(f"   来源: {result3['source']}")
        print(f"   操作名: {result3['documents'][0]['operation_name']}")
        assert fetch_count["count"] == 2, "应该拉取2次"
        assert result3["source"] == "fresh_fetch", "应该重新拉取"
        assert result3["documents"][0]["operation_name"] == "operation_v2", "应该是新版本"

    print("✅ 测试3通过：缓存过期自动重新拉取正常")


async def test_spec_agent_error_handling():
    """测试4：SpecDocAgent失败时的错误处理"""
    print("\n=== 测试4：错误处理 ===")

    spec_agent = SpecDocAgent()

    # Mock文档URL获取
    def mock_get_doc_urls(cloud_provider, service, doc_type):
        return [f"https://example.com/{cloud_provider}/{service}/api"]

    # Mock网络错误
    async def mock_fetch_error(doc_urls, cloud_provider, service):
        raise Exception("Network connection failed")

    with patch.object(spec_agent, '_get_doc_urls', side_effect=mock_get_doc_urls), \
         patch.object(spec_agent, '_fetch_specifications', side_effect=mock_fetch_error):
        cache = DocumentCache(
            rag_system=None,
            spec_doc_agent=spec_agent
        )

        result = await cache.get_or_fetch("azure", "vm", "list")

        print(f"   成功: {result['success']}")
        print(f"   错误: {result.get('error', 'N/A')}")

        assert not result["success"], "应该失败"
        assert "error" in result, "应该包含错误信息"

        # 验证不会缓存失败的结果
        stats = cache.get_cache_stats()
        assert stats["total_cached"] == 0, "不应该缓存失败结果"

    print("✅ 测试4通过：错误处理正常")


async def main():
    """运行所有集成测试"""
    print("=" * 70)
    print("文档系统集成测试")
    print("=" * 70)
    print("\n🔗 测试 SpecDocAgent + DocumentCache 集成")

    tests = [
        ("完整文档流程", test_full_document_flow),
        ("多云平台缓存", test_multi_provider_caching),
        ("缓存过期重拉取", test_cache_expiration_refetch),
        ("错误处理", test_spec_agent_error_handling),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ 测试失败: {name}")
            print(f"   原因: {str(e)}")
            failed += 1
        except Exception as e:
            print(f"❌ 测试异常: {name}")
            print(f"   错误: {str(e)}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("🎉 所有集成测试通过！文档系统工作正常")
    else:
        print(f"⚠️  有 {failed} 个测试失败")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
