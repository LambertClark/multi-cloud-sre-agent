"""
SpecDoc Agent - API规格文档拉取Agent
负责从云服务SDK或规格文档中提取API定义
策略：SDK内省 > OpenAPI规格 > LLM解析HTML
"""
from typing import Dict, Any, List, Optional
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json
import logging
from urllib.parse import urljoin, urlparse
import re
import inspect

from .base_agent import BaseAgent, AgentResponse
from config import get_config
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class SpecDocAgent(BaseAgent):
    """
    SpecDoc Agent负责：
    1. 从云SDK中内省提取API定义（优先）
    2. 从OpenAPI/Swagger规格中解析
    3. 使用LLM解析HTML文档（备选）
    """

    # SDK客户端映射 - 通过内省SDK提取API（优先级最高）
    # 注意：GCP需要安装 google-cloud-monitoring 包
    SDK_CLIENTS = {
        "aws": {
            "cloudwatch": {"service": "cloudwatch", "module": "boto3"},
            "ec2": {"service": "ec2", "module": "boto3"},
            "s3": {"service": "s3", "module": "boto3"},
            "logs": {"service": "logs", "module": "boto3"}
        },
        "azure": {
            "monitor": {"module": "azure.mgmt.monitor", "class": "MonitorManagementClient"},
            "compute": {"module": "azure.mgmt.compute", "class": "ComputeManagementClient"}
        },
        "gcp": {
            # GCP SDK需要单独安装: pip install google-cloud-monitoring
            "monitoring": {"module": "google.cloud.monitoring_v3", "class": "MetricServiceClient"}
        }
    }

    # OpenAPI规格URL映射（备选方案）
    DOC_URLS = {
        "kubernetes": {
            "core": [
                "https://raw.githubusercontent.com/kubernetes/kubernetes/master/api/openapi-spec/swagger.json"
            ]
        }
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("SpecDocAgent", config)
        self.config_obj = get_config()
        self.session: Optional[aiohttp.ClientSession] = None
        self._llm: Optional[ChatOpenAI] = None  # 延迟初始化

    @property
    def llm(self) -> ChatOpenAI:
        """延迟初始化LLM（只在需要时创建）"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model="moonshotai/Kimi-K2-Instruct-0905",
                temperature=0,
                base_url=self.config_obj.llm.base_url,
                api_key=self.config_obj.llm.api_key
            )
        return self._llm

    def get_capabilities(self) -> List[str]:
        """获取Agent能力"""
        return [
            "拉取云服务API规格文档",
            "解析OpenAPI/Swagger规格",
            "提取API操作和参数信息",
            "获取示例代码",
            "支持AWS、Azure、GCP等多云平台"
        ]

    def validate_input(self, input_data: Any) -> bool:
        """验证输入"""
        if not isinstance(input_data, dict):
            return False
        return ("cloud_provider" in input_data and "service" in input_data) or \
               "service_name" in input_data

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        处理规格文档拉取请求

        Args:
            input_data: {
                "cloud_provider": "aws",  # aws, azure, gcp
                "service": "cloudwatch",
                "doc_type": "api_reference"  # 可选
            }

        Returns:
            AgentResponse包含规格文档数据
        """
        try:
            cloud_provider = input_data.get("cloud_provider", "aws")
            service = input_data.get("service") or input_data.get("service_name", "")
            doc_type = input_data.get("doc_type", "api_reference")

            specs = {"operations": [], "schemas": {}, "examples": []}
            source = "unknown"

            # 策略1：优先尝试从SDK提取API定义
            sdk_specs = await self._extract_from_sdk(cloud_provider, service)
            if sdk_specs and sdk_specs.get("operations"):
                specs = sdk_specs
                source = "sdk_introspection"
                logger.info(f"成功从SDK提取 {len(specs['operations'])} 个API操作")
            else:
                # 策略2：尝试从OpenAPI规格拉取
                doc_urls = self._get_doc_urls(cloud_provider, service, doc_type)
                if doc_urls:
                    specs = await self._fetch_specifications(doc_urls, cloud_provider, service)
                    source = "openapi_spec"
                    logger.info(f"从OpenAPI规格拉取 {len(specs.get('operations', []))} 个API操作")

            return AgentResponse(
                success=True,
                data={
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "specifications": specs,
                    "source": source
                },
                metadata={
                    "source": source,
                    "operations_found": len(specs.get("operations", []))
                }
            )

        except Exception as e:
            logger.error(f"Error in SpecDocAgent.process: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e)
            )

    def _get_doc_urls(
        self,
        cloud_provider: str,
        service: str,
        doc_type: str = "api_reference"
    ) -> List[str]:
        """获取文档URL列表"""
        urls = []

        provider_docs = self.DOC_URLS.get(cloud_provider, {})

        # 尝试获取特定服务的URL
        if service in provider_docs:
            service_urls = provider_docs[service]
            # 处理列表或单个URL
            if isinstance(service_urls, list):
                urls.extend(service_urls)
            else:
                urls.append(service_urls)

        return urls

    async def _extract_from_sdk(
        self,
        cloud_provider: str,
        service: str
    ) -> Optional[Dict[str, Any]]:
        """从云SDK中提取API定义"""
        try:
            # 检查是否有SDK配置
            provider_sdks = self.SDK_CLIENTS.get(cloud_provider, {})
            sdk_config = provider_sdks.get(service)

            if not sdk_config:
                logger.debug(f"没有找到 {cloud_provider}.{service} 的SDK配置")
                return None

            # 根据云平台类型提取API
            if cloud_provider == "aws":
                return await self._extract_from_boto3(sdk_config)
            elif cloud_provider == "azure":
                return await self._extract_from_azure_sdk(sdk_config)
            elif cloud_provider == "gcp":
                return await self._extract_from_gcp_sdk(sdk_config)
            else:
                return None

        except Exception as e:
            logger.warning(f"从SDK提取API失败 {cloud_provider}.{service}: {e}")
            return None

    async def _extract_from_boto3(self, sdk_config: Dict[str, str]) -> Dict[str, Any]:
        """从boto3客户端提取API操作"""
        try:
            import boto3
            from botocore.exceptions import NoRegionError

            service_name = sdk_config["service"]

            # 创建客户端（使用默认region或配置的region）
            try:
                client = boto3.client(service_name, region_name='us-east-1')
            except NoRegionError:
                client = boto3.client(service_name)

            # 获取服务模型
            service_model = client._service_model

            operations = []

            # 遍历所有操作
            for operation_name in service_model.operation_names:
                operation_model = service_model.operation_model(operation_name)

                # 提取参数信息
                parameters = []
                if operation_model.input_shape:
                    input_shape = operation_model.input_shape
                    for member_name, member_shape in input_shape.members.items():
                        parameters.append({
                            "name": member_name,
                            "type": member_shape.type_name,
                            "required": member_name in input_shape.required_members,
                            "description": member_shape.documentation or ""
                        })

                operations.append({
                    "name": operation_name,
                    "description": operation_model.documentation or f"AWS {service_name} {operation_name} operation",
                    "parameters": parameters,
                    "service": service_name,
                    "method": "POST",  # AWS API通常使用POST
                    "path": f"/{operation_name}"
                })

            logger.info(f"从boto3提取了 {len(operations)} 个操作")

            return {
                "operations": operations,
                "schemas": {},
                "examples": []
            }

        except ImportError:
            logger.warning("boto3未安装，无法从AWS SDK提取API")
            return None
        except Exception as e:
            logger.error(f"从boto3提取API失败: {e}")
            return None

    async def _extract_from_azure_sdk(self, sdk_config: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """从Azure SDK提取API操作"""
        try:
            module_name = sdk_config["module"]
            class_name = sdk_config["class"]

            # 动态导入Azure SDK模块
            import importlib
            from unittest.mock import MagicMock

            module = importlib.import_module(module_name)
            client_class = getattr(module, class_name)

            # Azure SDK需要实例化客户端才能访问操作组
            # 使用Mock凭证创建客户端实例
            mock_credential = MagicMock()
            mock_subscription = "mock-subscription-id"

            try:
                client = client_class(
                    credential=mock_credential,
                    subscription_id=mock_subscription
                )
            except TypeError:
                # 如果不需要subscription_id
                client = client_class(credential=mock_credential)

            operations = []

            # 遍历客户端的操作组属性
            for attr_name in dir(client):
                if attr_name.startswith('_') or attr_name == 'close':
                    continue

                attr = getattr(client, attr_name)

                # 跳过非操作组（如models等）
                if not hasattr(attr, '__class__') or 'operations' not in attr.__class__.__module__.lower():
                    continue

                # 遍历操作组的方法
                for method_name in dir(attr):
                    if method_name.startswith('_'):
                        continue

                    method = getattr(attr, method_name)

                    if not callable(method):
                        continue

                    # 尝试获取方法签名
                    try:
                        sig = inspect.signature(method)
                        parameters = []

                        for param_name, param in sig.parameters.items():
                            if param_name in ['self', 'cls']:
                                continue

                            parameters.append({
                                "name": param_name,
                                "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "any",
                                "required": param.default == inspect.Parameter.empty,
                                "description": ""
                            })

                        # 提取文档字符串
                        doc = inspect.getdoc(method) or f"Azure {attr_name} {method_name} operation"

                        operations.append({
                            "name": f"{attr_name}.{method_name}",
                            "description": doc[:200],
                            "parameters": parameters,
                            "service": module_name.split('.')[-1],
                            "method": "POST",
                            "path": f"/{attr_name}/{method_name}"
                        })
                    except Exception as e:
                        continue

            logger.info(f"从Azure SDK提取了 {len(operations)} 个操作")

            return {
                "operations": operations,
                "schemas": {},
                "examples": []
            }

        except ImportError as e:
            logger.warning(f"Azure SDK未安装或模块不存在 ({module_name}): {e}")
            return None
        except Exception as e:
            logger.error(f"从Azure SDK提取API失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _extract_from_gcp_sdk(self, sdk_config: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """从GCP SDK提取API操作"""
        try:
            module_name = sdk_config["module"]
            class_name = sdk_config["class"]

            # 动态导入GCP SDK模块
            import importlib
            module = importlib.import_module(module_name)
            client_class = getattr(module, class_name)

            # 获取客户端类的所有公共方法
            operations = []

            for method_name in dir(client_class):
                # 跳过私有方法和特殊方法
                if method_name.startswith('_'):
                    continue

                method = getattr(client_class, method_name)

                # 只处理可调用的方法
                if not callable(method):
                    continue

                # 跳过非API操作的方法
                skip_methods = [
                    'close', 'from_service_account_file', 'from_service_account_json',
                    'get_mtls_endpoint_and_cert_source', 'get_transport_class',
                    'parse_common_billing_account_path', 'parse_common_folder_path',
                    'parse_common_location_path', 'parse_common_organization_path',
                    'parse_common_project_path', 'common_billing_account_path',
                    'common_folder_path', 'common_location_path', 'common_organization_path',
                    'common_project_path'
                ]

                if method_name in skip_methods or 'parse_' in method_name or '_path' in method_name:
                    continue

                # 尝试获取方法签名
                try:
                    sig = inspect.signature(method)
                    parameters = []

                    for param_name, param in sig.parameters.items():
                        # 跳过self和cls
                        if param_name in ['self', 'cls']:
                            continue

                        parameters.append({
                            "name": param_name,
                            "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "any",
                            "required": param.default == inspect.Parameter.empty,
                            "description": ""
                        })

                    # 提取文档字符串
                    doc = inspect.getdoc(method) or f"GCP {module_name} {method_name} operation"

                    operations.append({
                        "name": method_name,
                        "description": doc[:200],  # 限制描述长度
                        "parameters": parameters,
                        "service": module_name.split('.')[-1],
                        "method": "POST",
                        "path": f"/{method_name}"
                    })
                except Exception as e:
                    # 如果无法获取签名，跳过这个方法
                    continue

            logger.info(f"从GCP SDK提取了 {len(operations)} 个操作")

            return {
                "operations": operations,
                "schemas": {},
                "examples": []
            }

        except ImportError as e:
            logger.warning(f"GCP SDK未安装或模块不存在 ({module_name}): {e}")
            return None
        except Exception as e:
            logger.error(f"从GCP SDK提取API失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _fetch_specifications(
        self,
        urls: List[str],
        cloud_provider: str,
        service: str
    ) -> Dict[str, Any]:
        """
        拉取并解析规格文档

        Returns:
            {
                "operations": [...],
                "schemas": {...},
                "examples": [...]
            }
        """
        specifications = {
            "operations": [],
            "schemas": {},
            "examples": []
        }

        async with aiohttp.ClientSession() as session:
            self.session = session

            for url in urls:
                try:
                    # 尝试获取OpenAPI规格
                    openapi_spec = await self._try_fetch_openapi(url)
                    if openapi_spec:
                        self._merge_openapi_spec(specifications, openapi_spec)
                        continue

                    # 如果没有OpenAPI规格，尝试解析HTML文档
                    html_spec = await self._parse_html_docs(url, cloud_provider, service)
                    if html_spec:
                        self._merge_spec(specifications, html_spec)

                except Exception as e:
                    logger.warning(f"Failed to fetch from {url}: {str(e)}")
                    continue

        self.session = None
        return specifications

    async def _try_fetch_openapi(self, base_url: str) -> Optional[Dict[str, Any]]:
        """尝试获取OpenAPI规格文档"""
        # 如果URL本身就指向JSON文件，直接尝试拉取
        if base_url.endswith('.json') or 'swagger' in base_url.lower() or 'openapi' in base_url.lower():
            try:
                async with self.session.get(base_url, timeout=30) as response:
                    if response.status == 200:
                        text = await response.text()
                        logger.info(f"成功拉取文档: {base_url}, 大小: {len(text)} 字符")
                        spec = json.loads(text)

                        # 验证是否是有效的OpenAPI/Swagger规格
                        if 'paths' in spec or 'swagger' in spec or 'openapi' in spec:
                            logger.info(f"成功解析OpenAPI规格，路径数: {len(spec.get('paths', {}))}")
                            return spec
                        else:
                            logger.warning(f"JSON文件不是有效的OpenAPI规格")
                    else:
                        logger.warning(f"HTTP {response.status}: {base_url}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败 {base_url}: {e}")
            except Exception as e:
                logger.error(f"拉取OpenAPI规格失败 {base_url}: {type(e).__name__}: {e}")

        # 常见的OpenAPI规格路径
        openapi_paths = [
            "/openapi.json",
            "/swagger.json",
            "/api-docs",
            "/v3/api-docs"
        ]

        for path in openapi_paths:
            try:
                url = urljoin(base_url, path)
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        spec = await response.json()
                        logger.info(f"成功拉取OpenAPI规格: {url}")
                        return spec
            except:
                continue

        return None

    async def _parse_html_docs(
        self,
        url: str,
        cloud_provider: str,
        service: str
    ) -> Dict[str, Any]:
        """使用LLM智能解析HTML文档"""
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status != 200:
                    return {}

                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')

                # 提取主要文本内容（去除脚本、样式等）
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                text_content = soup.get_text()

                # 限制文本长度（LLM输入限制）
                max_chars = 50000
                if len(text_content) > max_chars:
                    text_content = text_content[:max_chars] + "\n\n[文档内容过长，已截断]"

                # 使用LLM解析文档
                return await self._llm_parse_docs(text_content, cloud_provider, service, url)

        except Exception as e:
            logger.error(f"Error parsing HTML docs from {url}: {str(e)}")
            return {}

    async def _llm_parse_docs(
        self,
        text_content: str,
        cloud_provider: str,
        service: str,
        url: str
    ) -> Dict[str, Any]:
        """使用LLM解析文档内容提取API规格"""
        try:
            prompt = f"""你是一个API文档解析专家。请从以下{cloud_provider}云平台的{service}服务文档中提取API操作信息。

文档URL: {url}

文档内容：
{text_content}

请提取以下信息并以JSON格式返回（必须严格遵守JSON格式）：
{{
    "operations": [
        {{
            "name": "API操作名称",
            "description": "操作描述",
            "method": "HTTP方法(GET/POST/PUT/DELETE等)",
            "path": "API路径或端点",
            "parameters": [
                {{
                    "name": "参数名",
                    "type": "参数类型",
                    "required": true/false,
                    "description": "参数描述"
                }}
            ]
        }}
    ],
    "examples": [
        {{
            "operation": "操作名称",
            "code": "示例代码"
        }}
    ]
}}

要求：
1. 只提取API操作相关的信息，忽略导航、介绍等内容
2. 至少提取3-5个主要API操作
3. 参数信息要尽可能完整
4. 如果有示例代码，一定要提取
5. **返回纯JSON，不要包含任何markdown代码块标记（不要```json）**
6. 如果文档中没有明确的API操作，返回空的operations列表
"""

            # 调用LLM（使用异步方法）
            response = await self.llm.ainvoke(prompt)

            # 解析LLM响应
            response_text = response.content.strip()

            # 移除可能的markdown代码块标记
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            response_text = response_text.strip()

            # 解析JSON
            try:
                result = json.loads(response_text)
                logger.info(f"LLM成功解析文档，提取了 {len(result.get('operations', []))} 个API操作")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"LLM响应不是有效的JSON: {e}")
                logger.error(f"响应内容: {response_text[:500]}")
                return {"operations": [], "examples": []}

        except Exception as e:
            logger.error(f"LLM解析文档失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"operations": [], "examples": []}

    def _merge_openapi_spec(self, target: Dict[str, Any], openapi_spec: Dict[str, Any]):
        """合并OpenAPI规格到目标规格"""
        # 提取路径和操作
        paths = openapi_spec.get('paths', {})

        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                    target['operations'].append({
                        "name": operation.get('operationId', f"{method}_{path}"),
                        "path": path,
                        "method": method.upper(),
                        "parameters": operation.get('parameters', []),
                        "description": operation.get('summary', ''),
                        "requestBody": operation.get('requestBody'),
                        "responses": operation.get('responses')
                    })

        # 提取schemas
        schemas = openapi_spec.get('components', {}).get('schemas', {})
        target['schemas'].update(schemas)

    def _merge_spec(self, target: Dict[str, Any], source: Dict[str, Any]):
        """合并规格文档"""
        target['operations'].extend(source.get('operations', []))
        target['examples'].extend(source.get('examples', []))
        target['schemas'].update(source.get('schemas', {}))

    async def fetch_service_specifications(self, service_name: str) -> AgentResponse:
        """简化的服务规格拉取接口"""
        # 尝试识别云平台
        cloud_provider = "aws"  # 默认AWS
        if "azure" in service_name.lower():
            cloud_provider = "azure"
        elif "gcp" in service_name.lower() or "google" in service_name.lower():
            cloud_provider = "gcp"

        return await self.safe_process({
            "cloud_provider": cloud_provider,
            "service": service_name
        })
