"""
RAG系统 - 基于LlamaIndex的文档知识库
用于索引和检索API规格文档
支持ChromaDB和Markdown文档加载
"""
from typing import Dict, Any, List, Optional
from llama_index.core import (
    Document,
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb
import os
import json
import logging
from pathlib import Path
import re

from config import get_config

logger = logging.getLogger(__name__)


class RAGSystem:
    """
    RAG系统负责：
    1. 将API规格文档索引到向量数据库
    2. 基于语义搜索检索相关文档
    3. 为代码生成提供上下文
    """

    def __init__(self):
        self.config = get_config()
        self.indices: Dict[str, VectorStoreIndex] = {}
        self.chroma_client = None
        self._embed_model_initialized = False
        self._init_settings()
        if self.config.rag.use_chromadb:
            self._init_chromadb()

    def _init_settings(self):
        """初始化LlamaIndex全局设置"""
        # 禁用LLM - RAG检索不需要LLM，只需要embedding
        # 我们只做向量检索，不需要LLM生成响应
        Settings.llm = None

        # 配置Embedding模型 - 使用HuggingFace本地模型
        # 延迟加载，避免启动时下载大模型
        # Settings.embed_model = HuggingFaceEmbedding(
        #     model_name=self.config.rag.embedding_model
        # )

        # 配置文本分割器
        Settings.node_parser = SentenceSplitter(
            chunk_size=self.config.rag.chunk_size,
            chunk_overlap=self.config.rag.chunk_overlap
        )

        logger.info("RAG system settings initialized (LLM disabled, embedding only)")

    def _lazy_init_embedding(self):
        """延迟初始化Embedding模型"""
        if self._embed_model_initialized:
            return

        logger.info(f"Initializing embedding model: {self.config.rag.embedding_model}")
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=self.config.rag.embedding_model
        )
        self._embed_model_initialized = True
        logger.info("Embedding model initialized")

    def _init_chromadb(self):
        """初始化ChromaDB客户端"""
        try:
            chroma_path = os.path.join(self.config.rag.vector_store_path, "chroma")
            os.makedirs(chroma_path, exist_ok=True)

            self.chroma_client = chromadb.PersistentClient(path=chroma_path)
            logger.info(f"ChromaDB initialized at: {chroma_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.chroma_client = None

    async def index_documents(
        self,
        spec_data: Dict[str, Any],
        index_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        索引API规格文档

        Args:
            spec_data: 规格文档数据
            index_name: 索引名称（默认使用 cloud_provider.service）

        Returns:
            索引结果
        """
        try:
            self._lazy_init_embedding()
            
            cloud_provider = spec_data.get("cloud_provider", "unknown")
            service = spec_data.get("service", "unknown")

            if index_name is None:
                index_name = f"{cloud_provider}.{service}"

            # 转换规格数据为文档
            documents = self._convert_spec_to_documents(spec_data)

            if not documents:
                return {
                    "success": False,
                    "error": "No documents to index"
                }

            # 创建或更新索引
            persist_dir = None  # 初始化persist_dir
            if self.config.rag.use_chromadb and self.chroma_client:
                # 使用ChromaDB
                collection_name = index_name.replace(".", "_")
                chroma_collection = self.chroma_client.get_or_create_collection(
                    name=collection_name
                )
                vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
                storage_context = StorageContext.from_defaults(vector_store=vector_store)
                index = VectorStoreIndex.from_documents(
                    documents,
                    storage_context=storage_context
                )
                persist_dir = f"chromadb://{collection_name}"  # ChromaDB标识
                logger.info(f"Created/updated ChromaDB index: {index_name}")
            else:
                # 使用文件存储
                persist_dir = os.path.join(
                    self.config.rag.vector_store_path,
                    index_name
                )

                if os.path.exists(persist_dir):
                    # 加载现有索引并更新
                    storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
                    index = load_index_from_storage(storage_context)
                    # 添加新文档
                    for doc in documents:
                        index.insert(doc)
                    logger.info(f"Updated existing index: {index_name}")
                else:
                    # 创建新索引
                    index = VectorStoreIndex.from_documents(documents)
                    os.makedirs(persist_dir, exist_ok=True)
                    index.storage_context.persist(persist_dir=persist_dir)
                    logger.info(f"Created new index: {index_name}")

            # 缓存索引
            self.indices[index_name] = index

            return {
                "success": True,
                "index_name": index_name,
                "documents_indexed": len(documents),
                "persist_dir": persist_dir
            }

        except Exception as e:
            logger.error(f"Error indexing documents: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _convert_spec_to_documents(self, spec_data: Dict[str, Any]) -> List[Document]:
        """将规格数据转换为LlamaIndex文档"""
        documents = []

        cloud_provider = spec_data.get("cloud_provider", "unknown")
        service = spec_data.get("service", "unknown")
        specifications = spec_data.get("specifications", {})

        # 转换操作为文档
        operations = specifications.get("operations", [])
        for op in operations:
            # 构建文档文本
            text = self._format_operation_text(op, cloud_provider, service)

            # 创建文档
            doc = Document(
                text=text,
                metadata={
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "operation_name": op.get("name", ""),
                    "type": "operation"
                }
            )
            documents.append(doc)

        # 转换示例为文档
        examples = specifications.get("examples", [])
        for example in examples:
            text = f"Operation: {example.get('operation', '')}\n\n"
            text += f"Example Code:\n{example.get('code', '')}"

            doc = Document(
                text=text,
                metadata={
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "operation_name": example.get("operation", ""),
                    "type": "example"
                }
            )
            documents.append(doc)

        # 转换schemas为文档
        schemas = specifications.get("schemas", {})
        for schema_name, schema in schemas.items():
            text = f"Schema: {schema_name}\n\n"
            text += json.dumps(schema, indent=2)

            doc = Document(
                text=text,
                metadata={
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "schema_name": schema_name,
                    "type": "schema"
                }
            )
            documents.append(doc)

        return documents

    def _format_operation_text(
        self,
        operation: Dict[str, Any],
        cloud_provider: str,
        service: str
    ) -> str:
        """格式化操作信息为文本"""
        text = f"Cloud Provider: {cloud_provider}\n"
        text += f"Service: {service}\n"
        text += f"Operation: {operation.get('name', '')}\n\n"

        if operation.get("description"):
            text += f"Description: {operation['description']}\n\n"

        if operation.get("path"):
            text += f"Path: {operation.get('method', 'GET')} {operation['path']}\n\n"

        # 参数
        parameters = operation.get("parameters", [])
        if parameters:
            text += "Parameters:\n"
            for param in parameters:
                param_name = param.get("name", "")
                param_type = param.get("type", param.get("schema", {}).get("type", ""))
                param_desc = param.get("description", "")
                required = param.get("required", False)

                text += f"- {param_name} ({param_type})"
                if required:
                    text += " [Required]"
                if param_desc:
                    text += f": {param_desc}"
                text += "\n"
            text += "\n"

        # 请求体
        if operation.get("requestBody"):
            text += "Request Body:\n"
            text += json.dumps(operation["requestBody"], indent=2)
            text += "\n\n"

        # 响应
        if operation.get("responses"):
            text += "Responses:\n"
            text += json.dumps(operation["responses"], indent=2)
            text += "\n"

        return text

    async def query(
        self,
        query_text: str,
        index_name: Optional[str] = None,
        cloud_provider: Optional[str] = None,
        service: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        查询相关文档

        Args:
            query_text: 查询文本
            index_name: 索引名称
            cloud_provider: 过滤云平台
            service: 过滤服务
            top_k: 返回top-k结果

        Returns:
            查询结果
        """
        try:
            self._lazy_init_embedding()

            if top_k is None:
                top_k = self.config.rag.top_k

            # 确定使用哪个索引
            if index_name:
                indices_to_search = [index_name]
            elif cloud_provider and service:
                indices_to_search = [f"{cloud_provider}.{service}"]
            else:
                # 搜索所有索引
                indices_to_search = list(self.indices.keys())

            # 如果索引未加载，尝试从磁盘加载
            for idx_name in indices_to_search:
                if idx_name not in self.indices:
                    await self._load_index(idx_name)

            if not indices_to_search or not any(idx in self.indices for idx in indices_to_search):
                return {
                    "success": False,
                    "error": "No indices available for querying"
                }

            # 执行查询
            all_results = []

            for idx_name in indices_to_search:
                if idx_name not in self.indices:
                    continue

                index = self.indices[idx_name]
                query_engine = index.as_query_engine(
                    similarity_top_k=top_k
                )

                response = query_engine.query(query_text)

                # 提取相关节点
                for node in response.source_nodes:
                    all_results.append({
                        "text": node.node.text,
                        "score": node.score,
                        "metadata": node.node.metadata,
                        "index": idx_name
                    })

            # 按分数排序
            all_results.sort(key=lambda x: x["score"], reverse=True)

            # 过滤低分结果
            threshold = self.config.rag.similarity_threshold
            filtered_results = [r for r in all_results if r["score"] >= threshold]

            return {
                "success": True,
                "results": filtered_results[:top_k],
                "total_found": len(all_results),
                "filtered_count": len(filtered_results)
            }

        except Exception as e:
            logger.error(f"Error querying RAG system: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _load_index(self, index_name: str) -> bool:
        """从磁盘加载索引"""
        try:
            persist_dir = os.path.join(
                self.config.rag.vector_store_path,
                index_name
            )

            if not os.path.exists(persist_dir):
                logger.warning(f"Index directory not found: {persist_dir}")
                return False

            storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
            index = load_index_from_storage(storage_context)

            self.indices[index_name] = index
            logger.info(f"Loaded index from disk: {index_name}")
            return True

        except Exception as e:
            logger.error(f"Error loading index {index_name}: {str(e)}")
            return False

    def list_indices(self) -> List[str]:
        """列出所有可用的索引"""
        # 从内存获取
        memory_indices = list(self.indices.keys())

        # 从磁盘扫描
        disk_indices = []
        vector_store_path = Path(self.config.rag.vector_store_path)

        if vector_store_path.exists():
            for item in vector_store_path.iterdir():
                if item.is_dir():
                    disk_indices.append(item.name)

        # 合并去重
        all_indices = list(set(memory_indices + disk_indices))
        return all_indices

    async def load_cloud_docs(self, docs_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        加载组员整理的云服务Markdown文档

        Args:
            docs_dir: 文档目录路径，默认使用配置中的路径

        Returns:
            加载结果
        """
        if docs_dir is None:
            docs_dir = self.config.rag.cloud_docs_dir

        try:
            docs_path = Path(docs_dir)
            if not docs_path.exists():
                return {
                    "success": False,
                    "error": f"Docs directory not found: {docs_dir}"
                }

            md_files = list(docs_path.rglob("*.md"))
            loaded_count = 0
            errors = []

            for md_file in md_files:
                try:
                    # 解析文档路径获取云平台和服务信息
                    parts = md_file.parts
                    # 假设结构: docs/cloud_provider/service.md
                    cloud_provider = parts[-2] if len(parts) >= 2 else "unknown"
                    service_name = md_file.stem

                    # 读取Markdown内容
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 解析Markdown为结构化数据
                    parsed_data = self._parse_markdown_doc(content, cloud_provider, service_name)

                    # 索引文档
                    result = await self.index_documents(parsed_data)

                    if result.get("success"):
                        loaded_count += 1
                        logger.info(f"Loaded {cloud_provider}/{service_name}")
                    else:
                        errors.append(f"{cloud_provider}/{service_name}: {result.get('error')}")

                except Exception as e:
                    logger.error(f"Error loading {md_file}: {e}")
                    errors.append(f"{md_file.name}: {str(e)}")

            return {
                "success": True,
                "loaded_count": loaded_count,
                "total_files": len(md_files),
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Error loading cloud docs: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_markdown_doc(
        self,
        content: str,
        cloud_provider: str,
        service_name: str
    ) -> Dict[str, Any]:
        """
        解析Markdown文档为结构化数据

        Args:
            content: Markdown内容
            cloud_provider: 云平台名称
            service_name: 服务名称

        Returns:
            结构化文档数据
        """
        # 提取标题和代码块
        operations = []

        # 提取主要章节
        sections = re.split(r'\n##\s+', content)

        for section in sections[1:]:  # 跳过第一个空部分
            lines = section.split('\n', 1)
            if len(lines) < 2:
                continue

            title = lines[0].strip()
            body = lines[1] if len(lines) > 1 else ""

            # 提取JSON代码块
            json_blocks = re.findall(r'```json\n(.*?)\n```', body, re.DOTALL)

            # 创建操作条目
            operation = {
                "name": title,
                "service": service_name,
                "description": body[:200],  # 前200字符作为描述
                "parameters": [],
                "examples": json_blocks
            }

            operations.append(operation)

        return {
            "cloud_provider": cloud_provider,
            "service": service_name,
            "specifications": {
                "operations": operations,
                "examples": [],
                "schemas": {}
            }
        }

    async def delete_index(self, index_name: str) -> Dict[str, Any]:
        """删除索引"""
        try:
            # 从内存移除
            if index_name in self.indices:
                del self.indices[index_name]

            # 从磁盘删除
            persist_dir = os.path.join(
                self.config.rag.vector_store_path,
                index_name
            )

            if os.path.exists(persist_dir):
                import shutil
                shutil.rmtree(persist_dir)

            logger.info(f"Deleted index: {index_name}")
            return {
                "success": True,
                "index_name": index_name
            }

        except Exception as e:
            logger.error(f"Error deleting index {index_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# 全局RAG系统实例
_rag_system: Optional[RAGSystem] = None


def get_rag_system() -> RAGSystem:
    """获取全局RAG系统实例"""
    global _rag_system
    if _rag_system is None:
        _rag_system = RAGSystem()
    return _rag_system
