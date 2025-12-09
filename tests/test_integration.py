"""
集成测试 - 测试组员文档整合
"""
import asyncio
import logging
from rag_system import get_rag_system
from orchestrator import get_orchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_cloud_docs_loading():
    """测试云文档加载"""
    print("\n" + "="*60)
    print("🧪 测试1: 云文档加载")
    print("="*60)

    rag = get_rag_system()

    # 加载文档
    result = await rag.load_cloud_docs()

    if result.get("success"):
        print(f"✅ 成功加载 {result['loaded_count']}/{result['total_files']} 个文档")
        if result.get("errors"):
            print(f"⚠️ {len(result['errors'])} 个文件加载失败")
            for error in result['errors'][:3]:  # 只显示前3个错误
                print(f"   - {error}")
        return True
    else:
        print(f"❌ 加载失败: {result.get('error')}")
        return False


async def test_rag_query():
    """测试RAG查询"""
    print("\n" + "="*60)
    print("🧪 测试2: RAG查询")
    print("="*60)

    rag = get_rag_system()

    # 测试查询AWS文档
    test_queries = [
        "AWS EC2 CPU使用率",
        "阿里云SLB负载均衡指标",
        "腾讯云CVM监控",
        "华为云ECS指标"
    ]

    passed = 0
    for query in test_queries:
        print(f"\n查询: {query}")
        result = await rag.query(query, top_k=3)

        if result.get("success"):
            results_count = len(result.get("results", []))
            print(f"  ✅ 找到 {results_count} 个相关文档")
            passed += 1
        else:
            print(f"  ❌ 查询失败: {result.get('error')}")

    print(f"\n通过: {passed}/{len(test_queries)}")
    return passed == len(test_queries)


async def test_orchestrator_integration():
    """测试Orchestrator集成"""
    print("\n" + "="*60)
    print("🧪 测试3: Orchestrator集成")
    print("="*60)

    orchestrator = get_orchestrator()

    # 测试查询
    test_query = "查询AWS EC2的CPU使用率"
    print(f"\n查询: {test_query}")

    result = await orchestrator.process_request(test_query)

    if result.get("success"):
        print(f"✅ 查询成功")
        print(f"   耗时: {result.get('duration', 0):.2f}s")
        print(f"   步骤数: {len(result.get('execution_log', []))}")
        return True
    else:
        print(f"❌ 查询失败: {result.get('error')}")
        return False


async def test_chromadb():
    """测试ChromaDB"""
    print("\n" + "="*60)
    print("🧪 测试4: ChromaDB向量存储")
    print("="*60)

    rag = get_rag_system()

    if rag.chroma_client:
        print("✅ ChromaDB客户端已初始化")

        # 列出collections
        try:
            collections = rag.chroma_client.list_collections()
            print(f"✅ Collections数量: {len(collections)}")
            for col in collections[:5]:  # 显示前5个
                print(f"   - {col.name}")
            return True
        except Exception as e:
            print(f"❌ ChromaDB错误: {e}")
            return False
    else:
        print("⚠️ ChromaDB未启用")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🚀 组员文档整合 - 集成测试")
    print("="*60)

    tests = [
        ("云文档加载", test_cloud_docs_loading),
        ("RAG查询", test_rag_query),
        ("Orchestrator集成", test_orchestrator_integration),
        ("ChromaDB", test_chromadb),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 出错: {e}")
            failed += 1

    # 总结
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    print(f"总计: {passed + failed}")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"通过率: {(passed/(passed+failed)*100):.1f}%")
    print("="*60 + "\n")

    if failed == 0:
        print("🎉 所有测试通过！组员文档已成功整合！")
    else:
        print("⚠️ 部分测试失败，请查看日志")


if __name__ == "__main__":
    asyncio.run(main())
