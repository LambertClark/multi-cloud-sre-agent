"""
增强RAG系统 - 混合检索、重排序、Query改写
提供比基础向量检索更强的检索能力
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from dataclasses import dataclass
import numpy as np
from rank_bm25 import BM25Okapi
import jieba
import re

logger = logging.getLogger(__name__)


class Reranker:
    """
    重排序模型 - 使用Cross-Encoder对检索结果重新打分
    比向量检索的双编码器（Bi-Encoder）更准确，但速度较慢
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Args:
            model_name: Cross-Encoder模型名称
                推荐模型：
                - cross-encoder/ms-marco-MiniLM-L-6-v2 (轻量级，英文)
                - BAAI/bge-reranker-base (中文支持更好)
        """
        self.model_name = model_name
        self._model = None
        self._model_initialized = False

    def _lazy_init_model(self):
        """延迟初始化模型"""
        if self._model_initialized:
            return

        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"正在初始化Reranker模型: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            self._model_initialized = True
            logger.info("Reranker模型初始化完成")

        except Exception as e:
            logger.error(f"Reranker模型初始化失败: {e}")
            self._model = None
            self._model_initialized = True

    def rerank(
        self,
        query: str,
        results: List["RetrievalResult"],
        top_k: Optional[int] = None
    ) -> List["RetrievalResult"]:
        """
        对检索结果重新排序

        Args:
            query: 查询文本
            results: 检索结果列表
            top_k: 返回top-k结果（None表示全部）

        Returns:
            重排序后的结果
        """
        if not results:
            return []

        self._lazy_init_model()

        if self._model is None:
            logger.warning("Reranker模型未初始化，返回原始排序")
            return results[:top_k] if top_k else results

        try:
            # 构建query-document对
            pairs = [(query, result.text) for result in results]

            # 计算相关性分数
            scores = self._model.predict(pairs)

            # 更新结果分数
            reranked_results = []
            for result, score in zip(results, scores):
                result.score = float(score)
                result.source = "reranked"
                reranked_results.append(result)

            # 按新分数排序
            reranked_results.sort(key=lambda x: x.score, reverse=True)

            logger.info(f"Reranker完成：{len(results)}个结果重排序")

            return reranked_results[:top_k] if top_k else reranked_results

        except Exception as e:
            logger.error(f"Reranker失败: {e}")
            return results[:top_k] if top_k else results


@dataclass
class RetrievalResult:
    """检索结果数据类"""
    text: str
    score: float
    metadata: Dict[str, Any]
    index: str
    source: str  # "vector", "bm25", "hybrid", "reranked"


class BM25Retriever:
    """
    BM25关键词检索器
    基于词频和逆文档频率的经典检索算法
    """

    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

    def _tokenize(self, text: str) -> List[str]:
        """
        分词：支持中英文
        """
        # 移除特殊字符
        text = re.sub(r'[^\w\s]', ' ', text)

        # 中文分词 + 英文按空格分割
        tokens = []

        # 使用jieba分词（会自动识别中英文）
        words = jieba.cut(text.lower())
        tokens = [w.strip() for w in words if w.strip() and len(w.strip()) > 1]

        return tokens

    def index_documents(self, documents: List[Dict[str, Any]]):
        """
        索引文档

        Args:
            documents: 文档列表，每个文档包含text和metadata
        """
        self.documents = documents
        self.tokenized_corpus = [self._tokenize(doc["text"]) for doc in documents]

        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            logger.info(f"BM25索引创建完成，文档数: {len(documents)}")
        else:
            logger.warning("没有文档可索引")

    def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """
        搜索相关文档

        Args:
            query: 查询文本
            top_k: 返回top-k结果

        Returns:
            检索结果列表
        """
        if not self.bm25:
            logger.warning("BM25索引未初始化")
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # 获取top-k索引
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 过滤0分结果
                doc = self.documents[idx]
                results.append(RetrievalResult(
                    text=doc["text"],
                    score=float(scores[idx]),
                    metadata=doc.get("metadata", {}),
                    index=doc.get("index", "unknown"),
                    source="bm25"
                ))

        return results


class HybridRetriever:
    """
    混合检索器 - 融合向量检索和BM25检索
    使用Reciprocal Rank Fusion (RRF)算法
    """

    def __init__(self, vector_weight: float = 0.5, bm25_weight: float = 0.5, k: int = 60):
        """
        Args:
            vector_weight: 向量检索权重
            bm25_weight: BM25检索权重
            k: RRF参数，控制排名的平滑度
        """
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.k = k

    def fuse_results(
        self,
        vector_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        融合两种检索结果

        使用Reciprocal Rank Fusion (RRF):
        RRF_score(d) = Σ 1/(k + rank(d))

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25检索结果
            top_k: 返回top-k结果

        Returns:
            融合后的结果
        """
        # 构建文档ID映射（使用text作为唯一标识）
        doc_scores: Dict[str, Dict[str, Any]] = {}

        # 处理向量检索结果
        for rank, result in enumerate(vector_results, 1):
            doc_id = result.text[:100]  # 使用前100字符作为ID
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "result": result,
                    "vector_rank": rank,
                    "bm25_rank": None,
                    "rrf_score": 0.0
                }
            doc_scores[doc_id]["vector_rank"] = rank

        # 处理BM25检索结果
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result.text[:100]
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "result": result,
                    "vector_rank": None,
                    "bm25_rank": rank,
                    "rrf_score": 0.0
                }
            else:
                doc_scores[doc_id]["bm25_rank"] = rank

        # 计算RRF分数
        for doc_id, info in doc_scores.items():
            rrf_score = 0.0

            if info["vector_rank"] is not None:
                rrf_score += self.vector_weight * (1.0 / (self.k + info["vector_rank"]))

            if info["bm25_rank"] is not None:
                rrf_score += self.bm25_weight * (1.0 / (self.k + info["bm25_rank"]))

            info["rrf_score"] = rrf_score

        # 按RRF分数排序
        sorted_docs = sorted(
            doc_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )

        # 构建融合结果
        fused_results = []
        for doc_info in sorted_docs[:top_k]:
            result = doc_info["result"]
            # 更新分数和来源
            result.score = doc_info["rrf_score"]
            result.source = "hybrid"
            fused_results.append(result)

        logger.info(f"混合检索完成，融合{len(vector_results)}个向量结果和{len(bm25_results)}个BM25结果")
        return fused_results


class QueryRewriter:
    """
    Query改写器 - 使用LLM优化查询
    """

    def __init__(self, llm):
        """
        Args:
            llm: LangChain LLM实例
        """
        self.llm = llm

    async def rewrite(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        改写查询，生成多个变体

        Args:
            query: 原始查询
            context: 上下文信息（云平台、服务等）

        Returns:
            改写后的查询列表（包含原始查询）
        """
        prompt = f"""你是一个API文档检索助手。用户想要查询云服务API文档。

用户查询：{query}

请将用户的自然语言查询改写为3个更适合检索API文档的查询变体。
要求：
1. 提取关键API操作名称（如：创建、删除、列出、更新等）
2. 识别资源类型（如：虚拟机、存储桶、监控指标等）
3. 使用技术术语替换口语化表达
4. 保持语义不变，只调整措辞

直接输出3个改写后的查询，每行一个，不要编号，不要解释。

示例：
用户查询：我想看看怎么创建一个云服务器
改写1：创建虚拟机实例
改写2：EC2 RunInstances API
改写3：启动计算实例操作

现在请改写："""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # 解析改写结果
            rewrites = [line.strip() for line in content.strip().split('\n') if line.strip()]

            # 过滤掉明显是标题或序号的行
            rewrites = [r for r in rewrites if not r.startswith('改写') and len(r) > 3]

            # 添加原始查询
            all_queries = [query] + rewrites[:3]

            logger.info(f"Query改写完成：{query} -> {len(all_queries)}个变体")
            return all_queries

        except Exception as e:
            logger.error(f"Query改写失败: {e}")
            return [query]  # 失败时返回原始查询


class RetrievalMetrics:
    """
    检索评估指标
    """

    @staticmethod
    def precision_at_k(retrieved: List[str], relevant: List[str], k: int) -> float:
        """
        计算P@K (Precision at K)

        Args:
            retrieved: 检索到的文档ID列表（按排序）
            relevant: 相关文档ID列表
            k: Top-K

        Returns:
            P@K分数
        """
        if k == 0 or len(retrieved) == 0:
            return 0.0

        top_k = retrieved[:k]
        relevant_set = set(relevant)

        hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
        return hits / k

    @staticmethod
    def recall_at_k(retrieved: List[str], relevant: List[str], k: int) -> float:
        """
        计算R@K (Recall at K)
        """
        if len(relevant) == 0:
            return 0.0

        top_k = retrieved[:k]
        relevant_set = set(relevant)

        hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
        return hits / len(relevant)

    @staticmethod
    def mean_reciprocal_rank(retrieved_lists: List[List[str]], relevant_lists: List[List[str]]) -> float:
        """
        计算MRR (Mean Reciprocal Rank)

        Args:
            retrieved_lists: 多个查询的检索结果列表
            relevant_lists: 多个查询的相关文档列表

        Returns:
            MRR分数
        """
        if len(retrieved_lists) != len(relevant_lists):
            raise ValueError("检索结果和相关文档列表长度不匹配")

        reciprocal_ranks = []

        for retrieved, relevant in zip(retrieved_lists, relevant_lists):
            relevant_set = set(relevant)

            # 找到第一个相关文档的位置
            for rank, doc_id in enumerate(retrieved, 1):
                if doc_id in relevant_set:
                    reciprocal_ranks.append(1.0 / rank)
                    break
            else:
                reciprocal_ranks.append(0.0)

        return sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0

    @staticmethod
    def ndcg_at_k(retrieved: List[str], relevant: List[str], k: int) -> float:
        """
        计算NDCG@K (Normalized Discounted Cumulative Gain)

        假设相关文档的相关性分数为1，其他为0
        """
        if k == 0 or len(relevant) == 0:
            return 0.0

        top_k = retrieved[:k]
        relevant_set = set(relevant)

        # 计算DCG
        dcg = 0.0
        for i, doc_id in enumerate(top_k, 1):
            if doc_id in relevant_set:
                dcg += 1.0 / np.log2(i + 1)

        # 计算IDCG（理想情况下的DCG）
        idcg = 0.0
        for i in range(min(len(relevant), k)):
            idcg += 1.0 / np.log2(i + 2)

        return dcg / idcg if idcg > 0 else 0.0


class EnhancedRAG:
    """
    增强RAG系统 - 整合所有优化功能
    """

    def __init__(self, base_rag_system, llm=None, reranker_model: Optional[str] = None):
        """
        Args:
            base_rag_system: 基础RAG系统实例（提供向量检索）
            llm: LLM实例（用于Query改写）
            reranker_model: Reranker模型名称（None表示不使用）
        """
        self.base_rag = base_rag_system
        self.llm = llm

        self.bm25_retriever = BM25Retriever()
        self.hybrid_retriever = HybridRetriever(
            vector_weight=0.6,  # 向量检索权重更高
            bm25_weight=0.4,
            k=60
        )
        self.query_rewriter = QueryRewriter(llm) if llm else None
        self.reranker = Reranker(reranker_model) if reranker_model else None
        self.metrics = RetrievalMetrics()

        # 文档缓存（用于BM25索引）
        self.indexed_documents: Dict[str, List[Dict[str, Any]]] = {}

    async def index_documents(
        self,
        spec_data: Dict[str, Any],
        index_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        索引文档到向量存储和BM25

        Args:
            spec_data: 规格文档数据
            index_name: 索引名称

        Returns:
            索引结果
        """
        # 调用基础RAG系统索引到向量数据库
        vector_result = await self.base_rag.index_documents(spec_data, index_name)

        if not vector_result.get("success"):
            return vector_result

        # 提取文档用于BM25索引
        cloud_provider = spec_data.get("cloud_provider", "unknown")
        service = spec_data.get("service", "unknown")

        if index_name is None:
            index_name = f"{cloud_provider}.{service}"

        # 转换为文档列表
        documents = []
        specifications = spec_data.get("specifications", {})

        for op in specifications.get("operations", []):
            text = self.base_rag._format_operation_text(op, cloud_provider, service)
            documents.append({
                "text": text,
                "metadata": {
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "operation_name": op.get("name", ""),
                    "type": "operation"
                },
                "index": index_name
            })

        # 索引到BM25
        self.indexed_documents[index_name] = documents
        self.bm25_retriever.index_documents(documents)

        logger.info(f"增强索引完成：{index_name}，文档数：{len(documents)}")

        return {
            "success": True,
            "index_name": index_name,
            "documents_indexed": len(documents),
            "vector_indexed": vector_result.get("documents_indexed", 0),
            "bm25_indexed": len(documents)
        }

    async def query(
        self,
        query_text: str,
        index_name: Optional[str] = None,
        cloud_provider: Optional[str] = None,
        service: Optional[str] = None,
        top_k: Optional[int] = 10,
        use_hybrid: bool = True,
        use_rewrite: bool = False,
        use_reranker: bool = False
    ) -> Dict[str, Any]:
        """
        增强查询

        Args:
            query_text: 查询文本
            index_name: 索引名称
            cloud_provider: 云平台
            service: 服务
            top_k: 返回结果数
            use_hybrid: 是否使用混合检索
            use_rewrite: 是否使用Query改写
            use_reranker: 是否使用Reranker重排序

        Returns:
            查询结果
        """
        try:
            # Query改写
            queries = [query_text]
            if use_rewrite and self.query_rewriter:
                queries = await self.query_rewriter.rewrite(query_text)
                logger.info(f"Query改写：{len(queries)}个查询变体")

            all_results = []

            for query in queries:
                if use_hybrid:
                    # 混合检索
                    results = await self._hybrid_search(
                        query,
                        index_name,
                        cloud_provider,
                        service,
                        top_k * 3  # 获取更多候选，供reranker选择
                    )
                else:
                    # 仅向量检索
                    results = await self._vector_search(
                        query,
                        index_name,
                        cloud_provider,
                        service,
                        top_k * 3
                    )

                all_results.extend(results)

            # 去重
            unique_results = self._deduplicate_results(all_results)

            # Reranker重排序
            if use_reranker and self.reranker:
                final_results = self.reranker.rerank(query_text, unique_results, top_k)
                strategy = "hybrid+reranker" if use_hybrid else "vector+reranker"
            else:
                final_results = sorted(unique_results, key=lambda x: x.score, reverse=True)[:top_k]
                strategy = "hybrid" if use_hybrid else "vector"

            return {
                "success": True,
                "results": [self._result_to_dict(r) for r in final_results],
                "total_found": len(all_results),
                "queries_used": len(queries),
                "strategy": strategy
            }

        except Exception as e:
            logger.error(f"增强查询失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _vector_search(
        self,
        query: str,
        index_name: Optional[str],
        cloud_provider: Optional[str],
        service: Optional[str],
        top_k: int
    ) -> List[RetrievalResult]:
        """向量检索"""
        vector_result = await self.base_rag.query(
            query,
            index_name,
            cloud_provider,
            service,
            top_k
        )

        if not vector_result.get("success"):
            return []

        results = []
        for item in vector_result.get("results", []):
            results.append(RetrievalResult(
                text=item["text"],
                score=item["score"],
                metadata=item["metadata"],
                index=item["index"],
                source="vector"
            ))

        return results

    async def _hybrid_search(
        self,
        query: str,
        index_name: Optional[str],
        cloud_provider: Optional[str],
        service: Optional[str],
        top_k: int
    ) -> List[RetrievalResult]:
        """混合检索（向量 + BM25）"""
        # 向量检索
        vector_results = await self._vector_search(
            query, index_name, cloud_provider, service, top_k * 2
        )

        # BM25检索
        bm25_results = self.bm25_retriever.search(query, top_k * 2)

        # 融合结果
        hybrid_results = self.hybrid_retriever.fuse_results(
            vector_results,
            bm25_results,
            top_k
        )

        return hybrid_results

    def _deduplicate_results(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """去重检索结果"""
        seen = set()
        unique = []

        for result in results:
            # 使用文本前100字符作为唯一标识
            doc_id = result.text[:100]
            if doc_id not in seen:
                seen.add(doc_id)
                unique.append(result)

        return unique

    def _result_to_dict(self, result: RetrievalResult) -> Dict[str, Any]:
        """将RetrievalResult转换为字典"""
        return {
            "text": result.text,
            "score": result.score,
            "metadata": result.metadata,
            "index": result.index,
            "source": result.source
        }
