"""
Tag Mapping Service - 业务标签到资源映射服务
支持通过业务标签（如"xxx业务"）查询相关的多云资源
"""
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TaggedResource:
    """标记的资源"""
    resource_id: str
    resource_type: str  # ec2, pod, log_group, cdn, alb等
    cloud_provider: str  # aws, k8s, azure, gcp等
    tags: Dict[str, str]
    resource_data: Optional[Dict[str, Any]] = None


class TagMappingService:
    """
    业务标签映射服务

    职责：
    1. 通过业务标签查询多云资源
    2. 标准化不同云平台的标签格式
    3. 支持EC2、LogGroup、Pod、CDN、ALB等资源类型
    """

    def __init__(self, aws_tools=None, k8s_tools=None):
        """
        初始化标签映射服务

        Args:
            aws_tools: AWS工具实例
            k8s_tools: Kubernetes工具实例
        """
        self.aws_tools = aws_tools
        self.k8s_tools = k8s_tools

        # 标签键标准化映射
        self.tag_key_mapping = {
            # 业务标签
            "业务": ["业务", "Business", "business", "app", "App", "application"],
            "环境": ["环境", "Environment", "environment", "env", "Env"],
            "项目": ["项目", "Project", "project", "proj"],
            "负责人": ["负责人", "Owner", "owner", "team", "Team"],
            # K8s特殊标签
            "k8s.app": ["app", "app.kubernetes.io/name"],
            "k8s.component": ["component", "app.kubernetes.io/component"],
        }

    async def get_resources_by_tag(
        self,
        tag_key: str,
        tag_value: str,
        resource_types: Optional[List[str]] = None,
        cloud_providers: Optional[List[str]] = None
    ) -> List[TaggedResource]:
        """
        通过标签查询资源

        Args:
            tag_key: 标签键（如："业务"）
            tag_value: 标签值（如："电商平台"）
            resource_types: 资源类型过滤（如：["ec2", "pod"]），None表示全部
            cloud_providers: 云平台过滤（如：["aws", "k8s"]），None表示全部

        Returns:
            标记的资源列表
        """
        results = []

        # 标准化标签键
        normalized_keys = self._normalize_tag_key(tag_key)

        # 如果未指定云平台，默认查询所有
        if cloud_providers is None:
            cloud_providers = []
            if self.aws_tools:
                cloud_providers.append("aws")
            if self.k8s_tools:
                cloud_providers.append("k8s")

        # 如果未指定资源类型，默认查询所有
        if resource_types is None:
            resource_types = ["ec2", "log_group", "pod", "cdn", "alb"]

        # AWS资源查询
        if "aws" in cloud_providers and self.aws_tools:
            # EC2实例
            if "ec2" in resource_types:
                ec2_resources = await self._get_aws_ec2_by_tag(
                    normalized_keys, tag_value
                )
                results.extend(ec2_resources)

            # CloudWatch LogGroup
            if "log_group" in resource_types:
                log_resources = await self._get_aws_log_groups_by_tag(
                    normalized_keys, tag_value
                )
                results.extend(log_resources)

            # CloudFront CDN
            if "cdn" in resource_types:
                cdn_resources = await self._get_aws_cloudfront_by_tag(
                    normalized_keys, tag_value
                )
                results.extend(cdn_resources)

            # ALB
            if "alb" in resource_types:
                alb_resources = await self._get_aws_alb_by_tag(
                    normalized_keys, tag_value
                )
                results.extend(alb_resources)

        # Kubernetes资源查询
        if "k8s" in cloud_providers and self.k8s_tools:
            if "pod" in resource_types:
                pod_resources = await self._get_k8s_pods_by_label(
                    normalized_keys, tag_value
                )
                results.extend(pod_resources)

        logger.info(
            f"Found {len(results)} resources with tag {tag_key}={tag_value}"
        )

        return results

    async def get_log_groups_by_business(self, business_name: str) -> List[str]:
        """
        通过业务名称获取相关的LogGroup列表

        Args:
            business_name: 业务名称

        Returns:
            LogGroup名称列表
        """
        resources = await self.get_resources_by_tag(
            tag_key="业务",
            tag_value=business_name,
            resource_types=["log_group"]
        )

        return [r.resource_id for r in resources]

    async def get_pods_by_business(
        self,
        business_name: str,
        namespace: Optional[str] = None
    ) -> List[TaggedResource]:
        """
        通过业务名称获取相关的Pod列表

        Args:
            business_name: 业务名称
            namespace: K8s命名空间过滤（可选）

        Returns:
            Pod资源列表
        """
        resources = await self.get_resources_by_tag(
            tag_key="业务",
            tag_value=business_name,
            resource_types=["pod"]
        )

        # 命名空间过滤
        if namespace:
            resources = [
                r for r in resources
                if r.resource_data and r.resource_data.get("namespace") == namespace
            ]

        return resources

    def _normalize_tag_key(self, tag_key: str) -> List[str]:
        """
        标准化标签键

        将用户输入的标签键转换为可能的多种变体

        Args:
            tag_key: 原始标签键

        Returns:
            标准化后的标签键列表
        """
        # 查找映射
        for standard_key, variants in self.tag_key_mapping.items():
            if tag_key in variants:
                return variants

        # 如果没有映射，返回原始键和常见变体
        return [tag_key, tag_key.lower(), tag_key.capitalize()]

    async def _get_aws_ec2_by_tag(
        self,
        tag_keys: List[str],
        tag_value: str
    ) -> List[TaggedResource]:
        """通过标签查询AWS EC2实例"""
        results = []

        try:
            # 尝试每个标签键变体
            for key in tag_keys:
                response = await self.aws_tools._list_ec2_instances_impl(
                    tags={key: tag_value}
                )

                if response.get("success"):
                    instances = response.get("instances", [])

                    for instance in instances:
                        # 提取标签
                        tags = {}
                        for tag in instance.get("Tags", []):
                            tags[tag["Key"]] = tag["Value"]

                        results.append(TaggedResource(
                            resource_id=instance["InstanceId"],
                            resource_type="ec2",
                            cloud_provider="aws",
                            tags=tags,
                            resource_data=instance
                        ))

                # 找到结果就停止
                if results:
                    break

        except Exception as e:
            logger.error(f"Error querying AWS EC2 by tag: {str(e)}")

        return results

    async def _get_aws_log_groups_by_tag(
        self,
        tag_keys: List[str],
        tag_value: str
    ) -> List[TaggedResource]:
        """通过标签查询AWS CloudWatch LogGroup"""
        results = []

        try:
            # CloudWatch Logs API
            import boto3
            from config import get_config

            config = get_config()
            client = boto3.client(
                'logs',
                aws_access_key_id=config.cloud.aws_access_key,
                aws_secret_access_key=config.cloud.aws_secret_key,
                region_name=config.cloud.aws_region
            )

            # 列出所有LogGroup
            paginator = client.get_paginator('describe_log_groups')

            for page in paginator.paginate():
                for log_group in page.get('logGroups', []):
                    log_group_name = log_group['logGroupName']

                    # 获取LogGroup标签
                    try:
                        tags_response = client.list_tags_log_group(
                            logGroupName=log_group_name
                        )
                        tags = tags_response.get('tags', {})

                        # 检查标签匹配
                        for key in tag_keys:
                            if tags.get(key) == tag_value:
                                results.append(TaggedResource(
                                    resource_id=log_group_name,
                                    resource_type="log_group",
                                    cloud_provider="aws",
                                    tags=tags,
                                    resource_data=log_group
                                ))
                                break

                    except Exception as e:
                        logger.debug(f"Error getting tags for {log_group_name}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error querying AWS LogGroups by tag: {str(e)}")

        return results

    async def _get_aws_cloudfront_by_tag(
        self,
        tag_keys: List[str],
        tag_value: str
    ) -> List[TaggedResource]:
        """通过标签查询AWS CloudFront分发"""
        results = []

        try:
            import boto3
            from config import get_config

            config = get_config()
            client = boto3.client(
                'cloudfront',
                aws_access_key_id=config.cloud.aws_access_key,
                aws_secret_access_key=config.cloud.aws_secret_key
            )

            # 列出所有分发
            paginator = client.get_paginator('list_distributions')

            for page in paginator.paginate():
                items = page.get('DistributionList', {}).get('Items', [])

                for dist in items:
                    dist_id = dist['Id']

                    # 获取标签
                    try:
                        tags_response = client.list_tags_for_resource(
                            Resource=dist['ARN']
                        )
                        tag_items = tags_response.get('Tags', {}).get('Items', [])

                        tags = {}
                        for tag in tag_items:
                            tags[tag['Key']] = tag['Value']

                        # 检查标签匹配
                        for key in tag_keys:
                            if tags.get(key) == tag_value:
                                results.append(TaggedResource(
                                    resource_id=dist_id,
                                    resource_type="cdn",
                                    cloud_provider="aws",
                                    tags=tags,
                                    resource_data=dist
                                ))
                                break

                    except Exception as e:
                        logger.debug(f"Error getting tags for distribution {dist_id}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error querying AWS CloudFront by tag: {str(e)}")

        return results

    async def _get_aws_alb_by_tag(
        self,
        tag_keys: List[str],
        tag_value: str
    ) -> List[TaggedResource]:
        """通过标签查询AWS ALB"""
        results = []

        try:
            import boto3
            from config import get_config

            config = get_config()
            client = boto3.client(
                'elbv2',
                aws_access_key_id=config.cloud.aws_access_key,
                aws_secret_access_key=config.cloud.aws_secret_key,
                region_name=config.cloud.aws_region
            )

            # 列出所有负载均衡器
            paginator = client.get_paginator('describe_load_balancers')

            for page in paginator.paginate():
                for lb in page.get('LoadBalancers', []):
                    lb_arn = lb['LoadBalancerArn']

                    # 获取标签
                    try:
                        tags_response = client.describe_tags(
                            ResourceArns=[lb_arn]
                        )

                        tag_descriptions = tags_response.get('TagDescriptions', [])
                        if tag_descriptions:
                            tag_items = tag_descriptions[0].get('Tags', [])

                            tags = {}
                            for tag in tag_items:
                                tags[tag['Key']] = tag['Value']

                            # 检查标签匹配
                            for key in tag_keys:
                                if tags.get(key) == tag_value:
                                    results.append(TaggedResource(
                                        resource_id=lb['LoadBalancerName'],
                                        resource_type="alb",
                                        cloud_provider="aws",
                                        tags=tags,
                                        resource_data=lb
                                    ))
                                    break

                    except Exception as e:
                        logger.debug(f"Error getting tags for ALB {lb_arn}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error querying AWS ALB by tag: {str(e)}")

        return results

    async def _get_k8s_pods_by_label(
        self,
        label_keys: List[str],
        label_value: str
    ) -> List[TaggedResource]:
        """通过标签查询Kubernetes Pod"""
        results = []

        if not self.k8s_tools:
            return results

        try:
            # 尝试每个标签键变体
            for key in label_keys:
                # 构建label selector
                label_selector = f"{key}={label_value}"

                # 调用K8s工具查询（需要K8s工具已实现）
                # 这里假设K8s工具有类似方法
                pods_response = await self.k8s_tools.list_pods(
                    label_selector=label_selector
                )

                if pods_response.get("success"):
                    pods = pods_response.get("pods", [])

                    for pod in pods:
                        metadata = pod.get("metadata", {})
                        labels = metadata.get("labels", {})

                        results.append(TaggedResource(
                            resource_id=f"{metadata.get('namespace')}/{metadata.get('name')}",
                            resource_type="pod",
                            cloud_provider="k8s",
                            tags=labels,
                            resource_data=pod
                        ))

                # 找到结果就停止
                if results:
                    break

        except Exception as e:
            logger.error(f"Error querying K8s Pods by label: {str(e)}")

        return results
