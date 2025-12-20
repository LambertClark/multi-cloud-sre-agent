"""
测试DocumentCache智能缓存系统
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


async def test_doc_cache_memory():
    """测试1：内存缓存功能"""
    print("\n=== 测试1：内存缓存 ===")

    # Mock SpecDocAgent
    mock_spec_agent = MagicMock()
    mock_spec_agent.process = AsyncMock(return_value=AgentResponse(
        success=True,
        data={
            "specifications": {
                "operations": [
                    {
                        "name": "list_pods",
                        "description": "List all pods",
                        "parameters": [{"name": "namespace", "type": "string"}]
                    }
                ],
                "examples": []
            }
        }
    ))

    cache = DocumentCache(
        rag_system=None,  # 不测试RAG
        spec_doc_agent=mock_spec_agent,
        default_max_age_hours=24
    )

    # 第一次调用：应该拉取新文档
    result1 = await cache.get_or_fetch("kubernetes", "core", "list_pod")

    print(f"第一次调用: success={result1['success']}, source={result1['source']}")
    assert result1["success"], "应该成功"
    assert result1["source"] == "fresh_fetch", "应该是fresh_fetch"
    assert mock_spec_agent.process.call_count == 1, "应该调用SpecDocAgent"

    # 第二次调用：应该命中内存缓存
    result2 = await cache.get_or_fetch("kubernetes", "core", "list_pod")

    print(f"第二次调用: success={result2['success']}, source={result2['source']}")
    assert result2["success"], "应该成功"
    assert result2["source"] == "memory_cache", "应该命中内存缓存"
    assert mock_spec_agent.process.call_count == 1, "不应再次调用SpecDocAgent"

    print("✅ 测试1通过：内存缓存正常工作")


async def test_doc_cache_expiration():
    """测试2：缓存过期"""
    print("\n=== 测试2：缓存过期 ===")

    mock_spec_agent = MagicMock()
    mock_spec_agent.process = AsyncMock(return_value=AgentResponse(
        success=True,
        data={"specifications": {"operations": [], "examples": []}}
    ))

    cache = DocumentCache(
        rag_system=None,
        spec_doc_agent=mock_spec_agent,
        default_max_age_hours=0.001  # 很短的过期时间（约3.6秒）
    )

    # 第一次调用
    result1 = await cache.get_or_fetch("aws", "cloudwatch", "get_metrics")
    print(f"第一次: source={result1['source']}")
    assert result1["source"] == "fresh_fetch"

    # 第二次调用（立即）
    result2 = await cache.get_or_fetch("aws", "cloudwatch", "get_metrics")
    print(f"第二次(立即): source={result2['source']}")
    assert result2["source"] == "memory_cache", "应该命中缓存"

    # 等待过期
    await asyncio.sleep(4)

    # 第三次调用（过期后）
    result3 = await cache.get_or_fetch("aws", "cloudwatch", "get_metrics")
    print(f"第三次(过期后): source={result3['source']}")
    assert result3["source"] == "fresh_fetch", "缓存过期，应该重新拉取"
    assert mock_spec_agent.process.call_count == 2, "应该调用2次"

    print("✅ 测试2通过：缓存过期机制正常")


async def test_doc_cache_stats():
    """测试3：缓存统计"""
    print("\n=== 测试3：缓存统计 ===")

    mock_spec_agent = MagicMock()
    mock_spec_agent.process = AsyncMock(return_value=AgentResponse(
        success=True,
        data={"specifications": {"operations": [], "examples": []}}
    ))

    cache = DocumentCache(
        rag_system=None,
        spec_doc_agent=mock_spec_agent
    )

    # 缓存多个文档
    await cache.get_or_fetch("kubernetes", "core", "list_pod")
    await cache.get_or_fetch("aws", "cloudwatch", "get_metrics")
    await cache.get_or_fetch("gcp", "monitoring", "list_timeseries")

    stats = cache.get_cache_stats()

    print(f"缓存统计: {stats}")
    assert stats["total_cached"] == 3, "应该有3个缓存条目"
    assert len(stats["by_provider"]) == 3, "应该有3个云平台"

    # 清除特定云平台
    cache.clear_cache("kubernetes")

    stats2 = cache.get_cache_stats()
    print(f"清除kubernetes后: {stats2}")
    assert stats2["total_cached"] == 2, "应该剩2个缓存"

    print("✅ 测试3通过：缓存统计正常")


async def test_doc_cache_failure_handling():
    """测试4：失败处理"""
    print("\n=== 测试4：失败处理 ===")

    mock_spec_agent = MagicMock()
    mock_spec_agent.process = AsyncMock(return_value=AgentResponse(
        success=False,
        error="Network error"
    ))

    cache = DocumentCache(
        rag_system=None,
        spec_doc_agent=mock_spec_agent
    )

    result = await cache.get_or_fetch("unknown", "service", "operation")

    print(f"结果: success={result['success']}, error={result.get('error')}")
    assert not result["success"], "应该失败"
    assert "error" in result, "应该包含错误信息"

    print("✅ 测试4通过：错误处理正常")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("DocumentCache 智能缓存系统测试")
    print("=" * 70)

    tests = [
        ("内存缓存", test_doc_cache_memory),
        ("缓存过期", test_doc_cache_expiration),
        ("缓存统计", test_doc_cache_stats),
        ("失败处理", test_doc_cache_failure_handling),
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
        print("🎉 所有测试通过！DocumentCache工作正常")
    else:
        print(f"⚠️  有 {failed} 个测试失败")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
