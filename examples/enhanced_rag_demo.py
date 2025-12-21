"""
增强RAG系统使用示例
展示如何在实际系统中使用混合检索、重排序等高级功能
"""
import asyncio
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_system import get_rag_system
from services.enhanced_rag import EnhancedRAG
from langchain_openai import ChatOpenAI
from config import get_config


async def demo_basic_vs_enhanced():
    """
    对比基础检索和增强检索的效果
    """
    print("=" * 70)
    print("增强RAG系统 - 检索效果对比")
    print("=" * 70)

    config = get_config()

    # 初始化基础RAG系统
    base_rag = get_rag_system()

    # 初始化LLM（用于Query改写）
    llm = ChatOpenAI(
        model="moonshotai/Kimi-K2-Instruct-0905",
        temperature=0,
        base_url=config.llm.base_url,
        api_key=config.llm.api_key
    )

    # 创建增强RAG系统
    # reranker_model可以选择：
    # - "cross-encoder/ms-marco-MiniLM-L-6-v2" (英文，轻量级)
    # - "BAAI/bge-reranker-base" (中英文，效果更好)
    enhanced_rag = EnhancedRAG(
        base_rag_system=base_rag,
        llm=llm,
        reranker_model="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

    # 准备测试文档
    test_spec_data = {
        "cloud_provider": "aws",
        "service": "ec2",
        "specifications": {
            "operations": [
                {
                    "name": "RunInstances",
                    "service": "ec2",
                    "description": "启动一个或多个EC2实例。可以指定实例类型、AMI、安全组等参数。",
                    "parameters": [
                        {"name": "ImageId", "type": "string", "required": True, "description": "AMI镜像ID"},
                        {"name": "InstanceType", "type": "string", "required": True, "description": "实例类型"},
                        {"name": "MinCount", "type": "integer", "required": True, "description": "最小实例数量"},
                    ]
                },
                {
                    "name": "DescribeInstances",
                    "service": "ec2",
                    "description": "描述一个或多个EC2实例的详细信息，包括状态、IP地址、标签等。",
                    "parameters": [
                        {"name": "InstanceIds", "type": "list", "required": False, "description": "实例ID列表"},
                    ]
                },
                {
                    "name": "StopInstances",
                    "service": "ec2",
                    "description": "停止一个或多个运行中的EC2实例。停止后实例仍保留，可以重新启动。",
                    "parameters": [
                        {"name": "InstanceIds", "type": "list", "required": True, "description": "要停止的实例ID列表"},
                    ]
                },
                {
                    "name": "TerminateInstances",
                    "service": "ec2",
                    "description": "终止（删除）一个或多个EC2实例。终止后实例无法恢复。",
                    "parameters": [
                        {"name": "InstanceIds", "type": "list", "required": True, "description": "要终止的实例ID列表"},
                    ]
                }
            ],
            "examples": [],
            "schemas": {}
        }
    }

    # 索引文档
    print("\n正在索引文档...")
    index_result = await enhanced_rag.index_documents(test_spec_data)

    if index_result["success"]:
        print(f"✅ 索引成功")
        print(f"   向量索引: {index_result['vector_indexed']} 个文档")
        print(f"   BM25索引: {index_result['bm25_indexed']} 个文档")
    else:
        print(f"❌ 索引失败: {index_result.get('error')}")
        return

    # 测试查询
    test_query = "我想创建一个新的虚拟机"

    print(f"\n{'='*70}")
    print(f"查询: {test_query}")
    print(f"{'='*70}")

    # 1. 基础向量检索
    print("\n【方案1】基础向量检索")
    print("-" * 70)
    result1 = await enhanced_rag.query(
        test_query,
        index_name="aws.ec2",
        top_k=3,
        use_hybrid=False,
        use_rewrite=False,
        use_reranker=False
    )

    if result1["success"]:
        print(f"策略: {result1['strategy']}")
        for i, doc in enumerate(result1["results"], 1):
            op_name = doc["metadata"].get("operation_name", "unknown")
            print(f"{i}. {op_name} (分数: {doc['score']:.4f})")
    else:
        print(f"检索失败: {result1.get('error')}")

    # 2. 混合检索（向量 + BM25）
    print("\n【方案2】混合检索（向量 + BM25）")
    print("-" * 70)
    result2 = await enhanced_rag.query(
        test_query,
        index_name="aws.ec2",
        top_k=3,
        use_hybrid=True,
        use_rewrite=False,
        use_reranker=False
    )

    if result2["success"]:
        print(f"策略: {result2['strategy']}")
        for i, doc in enumerate(result2["results"], 1):
            op_name = doc["metadata"].get("operation_name", "unknown")
            print(f"{i}. {op_name} (分数: {doc['score']:.4f})")
    else:
        print(f"检索失败: {result2.get('error')}")

    # 3. 混合检索 + Reranker
    print("\n【方案3】混合检索 + Reranker重排序")
    print("-" * 70)
    result3 = await enhanced_rag.query(
        test_query,
        index_name="aws.ec2",
        top_k=3,
        use_hybrid=True,
        use_rewrite=False,
        use_reranker=True
    )

    if result3["success"]:
        print(f"策略: {result3['strategy']}")
        for i, doc in enumerate(result3["results"], 1):
            op_name = doc["metadata"].get("operation_name", "unknown")
            print(f"{i}. {op_name} (分数: {doc['score']:.4f})")
    else:
        print(f"检索失败: {result3.get('error')}")

    # 4. 完整增强（混合检索 + Query改写 + Reranker）
    print("\n【方案4】完整增强（混合 + Query改写 + Reranker）")
    print("-" * 70)
    try:
        result4 = await enhanced_rag.query(
            test_query,
            index_name="aws.ec2",
            top_k=3,
            use_hybrid=True,
            use_rewrite=True,
            use_reranker=True
        )

        if result4["success"]:
            print(f"策略: {result4['strategy']}")
            print(f"使用了 {result4.get('queries_used', 1)} 个查询变体")
            for i, doc in enumerate(result4["results"], 1):
                op_name = doc["metadata"].get("operation_name", "unknown")
                print(f"{i}. {op_name} (分数: {doc['score']:.4f})")
        else:
            print(f"检索失败: {result4.get('error')}")
    except Exception as e:
        print(f"⚠️  完整增强模式跳过（可能需要配置代理）: {e}")

    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    print("不同检索策略的选择建议：")
    print()
    print("1️⃣  仅向量检索")
    print("   适用场景：语义搜索，查询和文档措辞差异大")
    print("   优点：理解语义，召回率高")
    print("   缺点：可能返回不够精确的结果")
    print()
    print("2️⃣  混合检索（推荐）")
    print("   适用场景：大多数情况下的最佳选择")
    print("   优点：平衡语义理解和关键词精确匹配")
    print("   缺点：计算成本略高")
    print()
    print("3️⃣  混合 + Reranker")
    print("   适用场景：对准确率要求极高的场景")
    print("   优点：Top-K准确率最高")
    print("   缺点：速度较慢，需下载模型")
    print()
    print("4️⃣  完整增强")
    print("   适用场景：用户查询表达不清晰时")
    print("   优点：最大化召回和准确率")
    print("   缺点：延迟最高，需要LLM调用")


async def demo_performance_metrics():
    """
    展示如何使用评估指标
    """
    print("\n\n" + "=" * 70)
    print("检索质量评估示例")
    print("=" * 70)

    from services.enhanced_rag import RetrievalMetrics

    metrics = RetrievalMetrics()

    # 模拟检索场景
    print("\n场景：用户查询'创建EC2实例'")

    retrieved = ["RunInstances", "DescribeInstances", "StopInstances", "CreateVolume"]
    relevant = ["RunInstances", "CreateImage"]

    print(f"检索到的API: {retrieved}")
    print(f"真正相关的API: {relevant}")

    # 计算指标
    p_at_1 = metrics.precision_at_k(retrieved, relevant, 1)
    p_at_3 = metrics.precision_at_k(retrieved, relevant, 3)

    r_at_3 = metrics.recall_at_k(retrieved, relevant, 3)

    ndcg_at_3 = metrics.ndcg_at_k(retrieved, relevant, 3)

    print(f"\n评估结果:")
    print(f"  P@1 (首位准确率): {p_at_1:.2%}")
    print(f"  P@3 (前三准确率): {p_at_3:.2%}")
    print(f"  R@3 (前三召回率): {r_at_3:.2%}")
    print(f"  NDCG@3 (排序质量): {ndcg_at_3:.4f}")

    print("\n指标说明:")
    print("  - P@K: 检索结果中相关文档的比例（准确率）")
    print("  - R@K: 找到的相关文档占全部相关文档的比例（召回率）")
    print("  - NDCG: 考虑排序位置的综合质量指标（越高越好）")
    print("  - MRR: 第一个相关结果的平均排名（越高越好）")


if __name__ == "__main__":
    print("\n增强RAG系统使用示例\n")

    # 运行示例
    asyncio.run(demo_basic_vs_enhanced())

    # 运行评估示例
    asyncio.run(demo_performance_metrics())

    print("\n" + "=" * 70)
    print("示例运行完成！")
    print("=" * 70)
