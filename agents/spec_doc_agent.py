"""
SpecDoc Agent - API规格文档拉取Agent
负责从云服务官方文档拉取API规格
"""
from typing import Dict, Any, List, Optional
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json
import logging
from urllib.parse import urljoin, urlparse
import re

from .base_agent import BaseAgent, AgentResponse
from config import get_config

logger = logging.getLogger(__name__)


class SpecDocAgent(BaseAgent):
    """
    SpecDoc Agent负责：
    1. 从云服务官方文档网站拉取API规格文档
    2. 解析OpenAPI/Swagger规格
    3. 提取API操作、参数、响应格式、示例代码
    """

    # 云平台文档URL映射
    DOC_URLS = {
        "aws": {
            "cloudwatch": "https://docs.aws.amazon.com/cloudwatch/",
            "logs": "https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/",
            "xray": "https://docs.aws.amazon.com/xray/",
            "api_reference": "https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/"
        },
        "azure": {
            "monitor": "https://learn.microsoft.com/en-us/azure/azure-monitor/",
            "api_reference": "https://learn.microsoft.com/en-us/rest/api/monitor/"
        },
        "gcp": {
            "monitoring": "https://cloud.google.com/monitoring/docs",
            "api_reference": "https://cloud.google.com/monitoring/api/ref_v3/rest"
        }
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("SpecDocAgent", config)
        self.config_obj = get_config()
        self.session: Optional[aiohttp.ClientSession] = None

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

            # 获取文档URL
            doc_urls = self._get_doc_urls(cloud_provider, service, doc_type)

            if not doc_urls:
                return AgentResponse(
                    success=False,
                    error=f"No documentation URLs found for {cloud_provider}.{service}"
                )

            # 拉取文档
            specs = await self._fetch_specifications(doc_urls, cloud_provider, service)

            return AgentResponse(
                success=True,
                data={
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "specifications": specs,
                    "doc_urls": doc_urls
                },
                metadata={
                    "urls_fetched": len(doc_urls),
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
            urls.append(provider_docs[service])

        # 添加API参考URL
        if doc_type == "api_reference" and "api_reference" in provider_docs:
            urls.append(provider_docs["api_reference"])

        return urls

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
                        return await response.json()
            except:
                continue

        return None

    async def _parse_html_docs(
        self,
        url: str,
        cloud_provider: str,
        service: str
    ) -> Dict[str, Any]:
        """解析HTML文档"""
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status != 200:
                    return {}

                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')

                # 根据云平台使用不同的解析策略
                if cloud_provider == "aws":
                    return self._parse_aws_docs(soup, service)
                elif cloud_provider == "azure":
                    return self._parse_azure_docs(soup, service)
                elif cloud_provider == "gcp":
                    return self._parse_gcp_docs(soup, service)

                return {}

        except Exception as e:
            logger.error(f"Error parsing HTML docs from {url}: {str(e)}")
            return {}

    def _parse_aws_docs(self, soup: BeautifulSoup, service: str) -> Dict[str, Any]:
        """解析AWS文档"""
        operations = []
        examples = []

        # 查找API操作
        api_sections = soup.find_all(['h2', 'h3'], class_=re.compile('api|operation'))

        for section in api_sections:
            operation_name = section.get_text().strip()

            # 查找参数表格
            parameters = []
            next_element = section.find_next_sibling()

            while next_element and next_element.name != section.name:
                if next_element.name == 'table':
                    parameters.extend(self._extract_parameters_from_table(next_element))
                next_element = next_element.find_next_sibling()

            # 查找示例代码
            code_blocks = section.find_next_siblings('pre', limit=3)
            for code in code_blocks:
                examples.append({
                    "operation": operation_name,
                    "code": code.get_text().strip()
                })

            operations.append({
                "name": operation_name,
                "service": service,
                "parameters": parameters,
                "description": self._extract_description(section)
            })

        return {
            "operations": operations,
            "examples": examples
        }

    def _parse_azure_docs(self, soup: BeautifulSoup, service: str) -> Dict[str, Any]:
        """解析Azure文档"""
        # Azure文档解析逻辑
        operations = []

        # Azure使用不同的HTML结构
        api_sections = soup.find_all('div', class_=re.compile('api-operation'))

        for section in api_sections:
            operation_name = section.find('h3')
            if operation_name:
                operations.append({
                    "name": operation_name.get_text().strip(),
                    "service": service,
                    "parameters": [],
                    "description": ""
                })

        return {"operations": operations, "examples": []}

    def _parse_gcp_docs(self, soup: BeautifulSoup, service: str) -> Dict[str, Any]:
        """解析GCP文档"""
        # GCP文档解析逻辑
        operations = []

        api_sections = soup.find_all('div', class_='method')

        for section in api_sections:
            method_name = section.find('h4')
            if method_name:
                operations.append({
                    "name": method_name.get_text().strip(),
                    "service": service,
                    "parameters": [],
                    "description": ""
                })

        return {"operations": operations, "examples": []}

    def _extract_parameters_from_table(self, table) -> List[Dict[str, Any]]:
        """从表格中提取参数信息"""
        parameters = []

        rows = table.find_all('tr')[1:]  # 跳过表头
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                parameters.append({
                    "name": cols[0].get_text().strip(),
                    "type": cols[1].get_text().strip() if len(cols) > 1 else "",
                    "description": cols[2].get_text().strip() if len(cols) > 2 else "",
                    "required": "required" in row.get_text().lower()
                })

        return parameters

    def _extract_description(self, element) -> str:
        """提取描述信息"""
        next_p = element.find_next('p')
        if next_p:
            return next_p.get_text().strip()
        return ""

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
