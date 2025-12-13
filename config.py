"""
配置管理模块
用于管理多云SRE Agent的配置
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """LLM配置"""
    model: str = "moonshotai/Kimi-K2-Instruct-0905"
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("OPENAI_API_BASE", ""))
    temperature: float = 0.7
    max_tokens: int = 4000

    # 多模型配置
    alternative_models: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "openai": {
            "model": "gpt-4",
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "base_url": "https://api.openai.com/v1"
        },
        "azure": {
            "model": "gpt-4",
            "api_key": os.getenv("AZURE_OPENAI_KEY", ""),
            "base_url": os.getenv("AZURE_OPENAI_ENDPOINT", "")
        },
        "anthropic": {
            "model": "claude-3-5-sonnet-20241022",
            "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
            "base_url": ""
        }
    })


@dataclass
class CloudConfig:
    """云平台配置"""
    # AWS配置
    aws_access_key: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    aws_secret_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))

    # Azure配置
    azure_subscription_id: str = field(default_factory=lambda: os.getenv("AZURE_SUBSCRIPTION_ID", ""))
    azure_client_id: str = field(default_factory=lambda: os.getenv("AZURE_CLIENT_ID", ""))
    azure_client_secret: str = field(default_factory=lambda: os.getenv("AZURE_CLIENT_SECRET", ""))
    azure_tenant_id: str = field(default_factory=lambda: os.getenv("AZURE_TENANT_ID", ""))

    # GCP配置
    gcp_project_id: str = field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", ""))
    gcp_credentials_path: str = field(default_factory=lambda: os.getenv("GCP_CREDENTIALS_PATH", ""))

    # 阿里云配置
    aliyun_access_key: str = field(default_factory=lambda: os.getenv("ALIYUN_ACCESS_KEY_ID", ""))
    aliyun_secret_key: str = field(default_factory=lambda: os.getenv("ALIYUN_SECRET_ACCESS_KEY", ""))
    aliyun_region: str = field(default_factory=lambda: os.getenv("ALIYUN_REGION", "cn-hangzhou"))

    # 火山云配置
    volc_access_key: str = field(default_factory=lambda: os.getenv("VOLC_ACCESS_KEY", ""))
    volc_secret_key: str = field(default_factory=lambda: os.getenv("VOLC_SECRET_KEY", ""))
    volc_region: str = field(default_factory=lambda: os.getenv("VOLC_REGION", "cn-beijing"))


@dataclass
class RAGConfig:
    """RAG系统配置"""
    vector_store_path: str = "./data/vector_store"
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    similarity_threshold: float = 0.7
    embedding_model: str = "BAAI/bge-small-zh-v1.5"  # 硅基流动支持的模型
    use_chromadb: bool = True  # 使用ChromaDB
    cloud_docs_dir: str = "./docs"  # 组员整理的文档目录


@dataclass
class WASMConfig:
    """WASM沙箱配置"""
    runtime: str = "wasmtime"  # 或 wasmer
    timeout: int = 30  # 秒
    memory_limit: int = 512 * 1024 * 1024  # 512MB
    max_code_gen_retries: int = 3  # 代码生成最大重试次数
    enable_retry_with_feedback: bool = True  # 启用错误反馈重试
    enable_networking: bool = False  # 安全起见，默认关闭网络
    test_mode: str = "full"  # basic, functional, full


@dataclass
class AgentConfig:
    """Agent配置"""
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 300  # 5分钟
    enable_logging: bool = True
    log_level: str = "INFO"


@dataclass
class Config:
    """全局配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    wasm: WASMConfig = field(default_factory=WASMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

    # 项目根目录
    project_root: str = field(default_factory=lambda: os.getcwd())

    # 数据目录
    data_dir: str = "./data"
    specs_dir: str = "./data/specs"
    generated_code_dir: str = "./generated"

    def __post_init__(self):
        """初始化后创建必要的目录"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.specs_dir, exist_ok=True)
        os.makedirs(self.generated_code_dir, exist_ok=True)
        os.makedirs(self.rag.vector_store_path, exist_ok=True)


# 全局配置实例
config = Config()


def get_config() -> Config:
    """获取全局配置"""
    return config


def update_config(**kwargs):
    """更新配置"""
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
