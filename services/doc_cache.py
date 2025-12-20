"""
Document Cache Service - 智能文档缓存服务
管理API文档的获取、缓存和过期刷新
"""
from typing import Dict, Any, List, Optional
import logging
import asyncio
from datetime import datetime, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)


class DocumentCache:
    """
    文档缓存服务

    功能：
    1. 检查RAG缓存中是否有文档
    2. 判断文档是否过期（默认24小时）
    3. 过期时调用SpecDocAgent重新拉取
    4. 更新RAG索引
    5. 返回最新文档
    """

    def __init__(
        self,
        rag_system=None,
        spec_doc_agent=None,
        default_max_age_hours: int = 24
    ):
        """
        初始化文档缓存

        Args:
            rag_system: RAG系统实例
            spec_doc_agent: SpecDocAgent实例
            default_max_age_hours: 默认缓存有效期（小时）
        """
        self.rag_system = rag_system
        self.spec_doc_agent = spec_doc_agent
        self.default_max_age_hours = default_max_age_hours

        # 内存缓存（辅助）
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _generate_cache_key(
        self,
        cloud_provider: str,
        service: str,
        operation: str = ""
    ) -> str:
        """生成缓存键"""
        key_str = f"{cloud_provider}:{service}:{operation}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get_or_fetch(
        self,
        cloud_provider: str,
        service: str,
        operation: str = "",
        max_age_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取或拉取文档

        工作流程：
        1. 检查内存缓存
        2. 检查RAG缓存
        3. 判断是否过期
        4. 过期则重新拉取并更新
        5. 返回文档

        Args:
            cloud_provider: 云平台
            service: 服务名
            operation: 操作名（可选）
            max_age_hours: 缓存有效期（小时），None使用默认值

        Returns:
            {
                "success": True/False,
                "documents": [...],
                "cached": True/False,
                "fetched_at": "ISO时间戳",
                "source": "memory_cache / rag_cache / fresh_fetch"
            }
        """
        if max_age_hours is None:
            max_age_hours = self.default_max_age_hours

        cache_key = self._generate_cache_key(cloud_provider, service, operation)

        # 1. 检查内存缓存
        memory_cached = self._check_memory_cache(cache_key, max_age_hours)
        if memory_cached:
            logger.info(f"✅ Memory cache hit: {cloud_provider}/{service}/{operation}")
            return memory_cached

        # 2. 检查RAG缓存
        rag_cached = await self._check_rag_cache(
            cloud_provider, service, operation, max_age_hours
        )
        if rag_cached:
            logger.info(f"✅ RAG cache hit: {cloud_provider}/{service}/{operation}")

            # 更新内存缓存
            self._update_memory_cache(cache_key, rag_cached)

            return rag_cached

        # 3. 缓存未命中或过期，重新拉取
        logger.info(f"⚠️  Cache miss, fetching fresh docs: {cloud_provider}/{service}/{operation}")

        fresh_docs = await self._fetch_fresh_documents(
            cloud_provider, service, operation
        )

        if not fresh_docs.get("success"):
            logger.error(f"Failed to fetch documents: {fresh_docs.get('error')}")
            return fresh_docs

        # 4. 更新RAG索引
        await self._update_rag_index(
            cloud_provider, service, operation, fresh_docs["documents"]
        )

        # 5. 更新内存缓存
        self._update_memory_cache(cache_key, fresh_docs)

        return fresh_docs

    def _check_memory_cache(
        self,
        cache_key: str,
        max_age_hours: int
    ) -> Optional[Dict[str, Any]]:
        """检查内存缓存"""
        cached = self._memory_cache.get(cache_key)

        if not cached:
            return None

        # 检查是否过期
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        age = datetime.now() - fetched_at

        if age > timedelta(hours=max_age_hours):
            logger.info(f"Memory cache expired (age: {age})")
            del self._memory_cache[cache_key]
            return None

        cached["source"] = "memory_cache"
        cached["cached"] = True
        return cached

    async def _check_rag_cache(
        self,
        cloud_provider: str,
        service: str,
        operation: str,
        max_age_hours: int
    ) -> Optional[Dict[str, Any]]:
        """检查RAG缓存"""
        if not self.rag_system:
            logger.warning("RAG system not available")
            return None

        try:
            # 构建查询
            query_text = f"{cloud_provider} {service}"
            if operation:
                query_text += f" {operation}"
            query_text += " API documentation"

            # 查询RAG
            rag_result = await self.rag_system.query(
                query_text=query_text,
                cloud_provider=cloud_provider,
                service=service,
                top_k=5
            )

            if not rag_result.get("success") or not rag_result.get("results"):
                return None

            # 检查元数据中的时间戳
            results = rag_result["results"]

            # 提取最新的文档
            latest_doc = None
            latest_time = None

            for result in results:
                metadata = result.get("metadata", {})
                fetched_at_str = metadata.get("fetched_at")

                if not fetched_at_str:
                    continue

                try:
                    fetched_at = datetime.fromisoformat(fetched_at_str)

                    if latest_time is None or fetched_at > latest_time:
                        latest_time = fetched_at
                        latest_doc = result
                except:
                    continue

            if not latest_doc or not latest_time:
                logger.info("No timestamped documents found in RAG")
                return None

            # 检查是否过期
            age = datetime.now() - latest_time

            if age > timedelta(hours=max_age_hours):
                logger.info(f"RAG cache expired (age: {age})")
                return None

            # 返回缓存结果
            return {
                "success": True,
                "documents": results,
                "cloud_provider": cloud_provider,
                "service": service,
                "operation": operation,
                "fetched_at": latest_time.isoformat(),
                "source": "rag_cache",
                "cached": True
            }

        except Exception as e:
            logger.error(f"Error checking RAG cache: {str(e)}")
            return None

    async def _fetch_fresh_documents(
        self,
        cloud_provider: str,
        service: str,
        operation: str
    ) -> Dict[str, Any]:
        """拉取新文档"""
        if not self.spec_doc_agent:
            return {
                "success": False,
                "error": "SpecDocAgent not available"
            }

        try:
            # 调用SpecDocAgent拉取文档
            result = await self.spec_doc_agent.process({
                "cloud_provider": cloud_provider,
                "service": service,
                "operation": operation
            })

            if not result.success:
                return {
                    "success": False,
                    "error": result.error
                }

            # 转换为统一格式
            specifications = result.data.get("specifications", {})
            operations = specifications.get("operations", [])
            examples = specifications.get("examples", [])

            # 合并为文档列表
            documents = []

            for op in operations:
                doc = {
                    "type": "api_operation",
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "operation_name": op.get("name", ""),
                    "description": op.get("description", ""),
                    "parameters": op.get("parameters", []),
                    "path": op.get("path", ""),
                    "method": op.get("method", ""),
                    "examples": []
                }

                # 关联示例代码
                for example in examples:
                    if example.get("operation") == op.get("name"):
                        doc["examples"].append(example.get("code", ""))

                documents.append(doc)

            return {
                "success": True,
                "documents": documents,
                "cloud_provider": cloud_provider,
                "service": service,
                "operation": operation,
                "fetched_at": datetime.now().isoformat(),
                "source": "fresh_fetch",
                "cached": False
            }

        except Exception as e:
            logger.error(f"Error fetching fresh documents: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }

    async def _update_rag_index(
        self,
        cloud_provider: str,
        service: str,
        operation: str,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """更新RAG索引"""
        if not self.rag_system:
            logger.warning("RAG system not available, skipping index update")
            return False

        try:
            # 准备文档用于索引
            texts = []
            metadatas = []

            for doc in documents:
                # 构建文档文本
                text_parts = []

                text_parts.append(f"Cloud Provider: {cloud_provider}")
                text_parts.append(f"Service: {service}")
                text_parts.append(f"Operation: {doc.get('operation_name', '')}")
                text_parts.append(f"Description: {doc.get('description', '')}")

                # 添加参数信息
                params = doc.get("parameters", [])
                if params:
                    text_parts.append("Parameters:")
                    for param in params:
                        param_str = f"  - {param.get('name', '')}: {param.get('type', '')} - {param.get('description', '')}"
                        if param.get("required"):
                            param_str += " (required)"
                        text_parts.append(param_str)

                # 添加示例代码
                examples = doc.get("examples", [])
                if examples:
                    text_parts.append("Examples:")
                    for example in examples[:2]:  # 最多2个示例
                        text_parts.append(f"```\n{example}\n```")

                text = "\n".join(text_parts)
                texts.append(text)

                # 元数据
                metadata = {
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "operation": doc.get("operation_name", ""),
                    "fetched_at": datetime.now().isoformat(),
                    "doc_type": "api_specification"
                }
                metadatas.append(metadata)

            # 索引到RAG（这里假设RAG系统有add_documents方法）
            # 实际实现需要根据RAG系统的接口调整
            logger.info(f"Indexing {len(texts)} documents to RAG")

            # TODO: 实现实际的RAG索引逻辑
            # await self.rag_system.add_documents(texts, metadatas)

            return True

        except Exception as e:
            logger.error(f"Error updating RAG index: {str(e)}")
            return False

    def _update_memory_cache(
        self,
        cache_key: str,
        data: Dict[str, Any]
    ):
        """更新内存缓存"""
        self._memory_cache[cache_key] = data.copy()

        # 限制缓存大小
        if len(self._memory_cache) > 100:
            # 删除最旧的条目
            oldest_key = min(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k].get("fetched_at", "")
            )
            del self._memory_cache[oldest_key]

    def clear_cache(self, cloud_provider: Optional[str] = None):
        """
        清除缓存

        Args:
            cloud_provider: 如果指定，只清除该云平台的缓存
        """
        if cloud_provider:
            # 清除特定云平台的缓存
            keys_to_delete = []
            for key, data in self._memory_cache.items():
                if data.get("cloud_provider") == cloud_provider:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._memory_cache[key]

            logger.info(f"Cleared {len(keys_to_delete)} cached documents for {cloud_provider}")
        else:
            # 清除所有缓存
            count = len(self._memory_cache)
            self._memory_cache.clear()
            logger.info(f"Cleared all {count} cached documents")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = {
            "total_cached": len(self._memory_cache),
            "by_provider": {}
        }

        for data in self._memory_cache.values():
            provider = data.get("cloud_provider", "unknown")
            stats["by_provider"][provider] = stats["by_provider"].get(provider, 0) + 1

        return stats


# 全局实例（延迟初始化）
_doc_cache_instance: Optional[DocumentCache] = None


def get_doc_cache(
    rag_system=None,
    spec_doc_agent=None
) -> DocumentCache:
    """获取DocumentCache单例"""
    global _doc_cache_instance

    if _doc_cache_instance is None:
        _doc_cache_instance = DocumentCache(
            rag_system=rag_system,
            spec_doc_agent=spec_doc_agent
        )

    return _doc_cache_instance
