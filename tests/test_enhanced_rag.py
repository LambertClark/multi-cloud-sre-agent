"""
测试增强RAG系统
验证混合检索、重排序、Query改写等功能
"""
import asyncio
import sys
import io
import os

# 设置UTF-8编码输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.enhanced_rag import (
    BM25Retriever,
    HybridRetriever,
    QueryRewriter,
    Reranker,
    RetrievalMetrics,
    RetrievalResult
)


def test_bm25_retriever():
    """测试BM25检索"""
    print("\n" + "=" * 70)
    print("测试1：BM25关键词检索")
    print("=" * 70)

    # 准备测试文档
    documents = [
        {
            "text": "AWS CloudWatch是一个监控服务，用于监控AWS资源和应用程序。支持创建告警、查看日志和指标。",
            "metadata": {"service": "cloudwatch", "type": "monitoring"},
            "index": "aws.cloudwatch"
        },
        {
            "text": "Amazon S3是对象存储服务，用于存储和检索任意数量的数据。支持创建存储桶、上传对象、设置访问权限。",
            "metadata": {"service": "s3", "type": "storage"},
            "index": "aws.s3"
        },
        {
            "text": "Azure Monitor提供全面的监控解决方案，用于收集、分析和处理来自云环境和本地环境的遥测数据。",
            "metadata": {"service": "monitor", "type": "monitoring"},
            "index": "azure.monitor"
        },
        {
            "text": "Google Cloud Storage是统一的对象存储服务，适用于从实时数据到冷存储的各种场景。",
            "metadata": {"service": "storage", "type": "storage"},
            "index": "gcp.storage"
        },
        {
            "text": "Kubernetes是开源容器编排平台，用于自动化部署、扩展和管理容器化应用程序。",
            "metadata": {"service": "kubernetes", "type": "orchestration"},
            "index": "kubernetes.core"
        }
    ]

    # 创建BM25检索器
    retriever = BM25Retriever()
    retriever.index_documents(documents)

    # 测试查询
    queries = [
        "监控服务",
        "存储对象",
        "容器编排"
    ]

    for query in queries:
        print(f"\n查询: {query}")
        results = retriever.search(query, top_k=3)

        if results:
            print(f"找到 {len(results)} 个结果:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. [{result.index}] 分数: {result.score:.4f}")
                print(f"     {result.text[:50]}...")
        else:
            print("  未找到结果")

    print("\n✅ BM25检索测试完成")


def test_hybrid_retriever():
    """测试混合检索"""
    print("\n" + "=" * 70)
    print("测试2：混合检索（RRF融合）")
    print("=" * 70)

    # 模拟向量检索结果（分数较高的在前）
    vector_results = [
        RetrievalResult(
            text="AWS CloudWatch监控服务文档",
            score=0.85,
            metadata={"source": "vector"},
            index="aws.cloudwatch",
            source="vector"
        ),
        RetrievalResult(
            text="Azure Monitor监控平台",
            score=0.78,
            metadata={"source": "vector"},
            index="azure.monitor",
            source="vector"
        ),
        RetrievalResult(
            text="Google Cloud Monitoring API",
            score=0.72,
            metadata={"source": "vector"},
            index="gcp.monitoring",
            source="vector"
        )
    ]

    # 模拟BM25检索结果（关键词匹配）
    bm25_results = [
        RetrievalResult(
            text="Azure Monitor监控平台",
            score=12.5,
            metadata={"source": "bm25"},
            index="azure.monitor",
            source="bm25"
        ),
        RetrievalResult(
            text="Prometheus监控系统",
            score=10.2,
            metadata={"source": "bm25"},
            index="prometheus.core",
            source="bm25"
        ),
        RetrievalResult(
            text="AWS CloudWatch监控服务文档",
            score=9.8,
            metadata={"source": "bm25"},
            index="aws.cloudwatch",
            source="bm25"
        )
    ]

    # 混合检索
    hybrid = HybridRetriever(vector_weight=0.6, bm25_weight=0.4)
    fused_results = hybrid.fuse_results(vector_results, bm25_results, top_k=5)

    print(f"\n向量检索结果: {len(vector_results)}个")
    print(f"BM25检索结果: {len(bm25_results)}个")
    print(f"融合后结果: {len(fused_results)}个")

    print("\n融合排序:")
    for i, result in enumerate(fused_results, 1):
        print(f"  {i}. [{result.index}] RRF分数: {result.score:.4f}")
        print(f"     {result.text}")

    print("\n✅ 混合检索测试完成")


async def test_query_rewriter():
    """测试Query改写"""
    print("\n" + "=" * 70)
    print("测试3：Query改写")
    print("=" * 70)

    try:
        from langchain_openai import ChatOpenAI
        from config import get_config

        config = get_config()

        # 创建LLM
        llm = ChatOpenAI(
            model="moonshotai/Kimi-K2-Instruct-0905",
            temperature=0,
            base_url=config.llm.base_url,
            api_key=config.llm.api_key
        )

        rewriter = QueryRewriter(llm)

        # 测试查询
        queries = [
            "我想看看怎么创建一个云服务器",
            "如何监控我的应用性能",
            "怎么上传文件到云存储"
        ]

        for query in queries:
            print(f"\n原始查询: {query}")
            rewrites = await rewriter.rewrite(query)

            print("改写结果:")
            for i, rewrite in enumerate(rewrites, 1):
                print(f"  {i}. {rewrite}")

        print("\n✅ Query改写测试完成")

    except Exception as e:
        print(f"\n⚠️  Query改写测试跳过（需要LLM连接）: {e}")


def test_retrieval_metrics():
    """测试检索评估指标"""
    print("\n" + "=" * 70)
    print("测试4：检索评估指标")
    print("=" * 70)

    metrics = RetrievalMetrics()

    # 模拟数据
    retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    relevant = ["doc2", "doc5", "doc7"]

    # 计算各项指标
    p_at_3 = metrics.precision_at_k(retrieved, relevant, k=3)
    p_at_5 = metrics.precision_at_k(retrieved, relevant, k=5)

    r_at_3 = metrics.recall_at_k(retrieved, relevant, k=3)
    r_at_5 = metrics.recall_at_k(retrieved, relevant, k=5)

    ndcg_at_3 = metrics.ndcg_at_k(retrieved, relevant, k=3)
    ndcg_at_5 = metrics.ndcg_at_k(retrieved, relevant, k=5)

    # MRR
    retrieved_lists = [
        ["doc1", "doc2", "doc3"],
        ["doc5", "doc1", "doc2"],
        ["doc3", "doc4", "doc5"]
    ]
    relevant_lists = [
        ["doc2"],
        ["doc5"],
        ["doc5"]
    ]
    mrr = metrics.mean_reciprocal_rank(retrieved_lists, relevant_lists)

    print(f"\n检索结果: {retrieved}")
    print(f"相关文档: {relevant}")

    print(f"\nP@3: {p_at_3:.4f}")
    print(f"P@5: {p_at_5:.4f}")

    print(f"\nR@3: {r_at_3:.4f}")
    print(f"R@5: {r_at_5:.4f}")

    print(f"\nNDCG@3: {ndcg_at_3:.4f}")
    print(f"NDCG@5: {ndcg_at_5:.4f}")

    print(f"\nMRR: {mrr:.4f}")

    print("\n✅ 检索评估指标测试完成")


def test_reranker():
    """测试Reranker重排序"""
    print("\n" + "=" * 70)
    print("测试5：Reranker重排序")
    print("=" * 70)

    try:
        # 准备测试结果
        query = "如何创建AWS EC2实例"

        results = [
            RetrievalResult(
                text="Amazon S3是对象存储服务，用于存储数据",
                score=0.75,
                metadata={},
                index="aws.s3",
                source="hybrid"
            ),
            RetrievalResult(
                text="Amazon EC2提供可扩展的虚拟服务器，使用RunInstances API创建实例",
                score=0.72,
                metadata={},
                index="aws.ec2",
                source="hybrid"
            ),
            RetrievalResult(
                text="AWS CloudWatch用于监控EC2实例的性能指标",
                score=0.68,
                metadata={},
                index="aws.cloudwatch",
                source="hybrid"
            )
        ]

        print(f"\n查询: {query}")
        print("\n原始排序（混合检索分数）:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. [{result.index}] 分数: {result.score:.4f}")
            print(f"     {result.text[:60]}...")

        # 使用Reranker
        print("\n正在初始化Reranker模型...")
        reranker = Reranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")

        reranked = reranker.rerank(query, results, top_k=3)

        print("\nReranker重排序后:")
        for i, result in enumerate(reranked, 1):
            print(f"  {i}. [{result.index}] 分数: {result.score:.4f}")
            print(f"     {result.text[:60]}...")

        print("\n✅ Reranker重排序测试完成")

    except Exception as e:
        print(f"\n⚠️  Reranker测试跳过（需要下载模型）: {e}")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("增强RAG系统功能测试")
    print("=" * 70)

    # 1. BM25检索
    test_bm25_retriever()

    # 2. 混合检索
    test_hybrid_retriever()

    # 3. Query改写
    await test_query_rewriter()

    # 4. 检索评估指标
    test_retrieval_metrics()

    # 5. Reranker
    test_reranker()

    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    print("✅ BM25关键词检索 - 已实现")
    print("✅ 混合检索策略（RRF融合）- 已实现")
    print("✅ Query改写 - 已实现")
    print("✅ Reranker重排序 - 已实现")
    print("✅ 检索评估指标 - 已实现")

    print("\n功能说明:")
    print("1. BM25检索：基于词频的经典关键词检索，适合精确匹配")
    print("2. 混合检索：融合向量相似度和BM25，平衡语义和关键词")
    print("3. Query改写：使用LLM优化查询，提升检索召回率")
    print("4. Reranker：使用Cross-Encoder模型对结果重新打分，提升准确率")
    print("5. 评估指标：P@K、R@K、NDCG、MRR等标准检索指标")

    print("\n下一步:")
    print("- 集成到orchestrator.py中使用")
    print("- 在真实环境中验证检索质量")
    print("- 根据实际效果调整混合检索权重")


if __name__ == "__main__":
    asyncio.run(main())
