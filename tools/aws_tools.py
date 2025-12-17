"""
AWS可观测性工具集
聚焦CloudWatch监控、日志、X-Ray追踪等
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import logging

from config import get_config
from .cloud_tools import get_tool_registry

logger = logging.getLogger(__name__)


class AWSMonitoringTools:
    """AWS监控工具类"""

    def __init__(self):
        self.config = get_config()
        self._cloudwatch_client = None
        self._logs_client = None
        self._xray_client = None
        self._ec2_client = None
        self._ce_client = None  # Cost Explorer
        self.tool_registry = get_tool_registry()
        self._register_all_tools()

    def _get_cloudwatch_client(self):
        """获取CloudWatch客户端"""
        if self._cloudwatch_client is None:
            self._cloudwatch_client = boto3.client(
                'cloudwatch',
                aws_access_key_id=self.config.cloud.aws_access_key,
                aws_secret_access_key=self.config.cloud.aws_secret_key,
                region_name=self.config.cloud.aws_region
            )
        return self._cloudwatch_client

    def _get_logs_client(self):
        """获取CloudWatch Logs客户端"""
        if self._logs_client is None:
            self._logs_client = boto3.client(
                'logs',
                aws_access_key_id=self.config.cloud.aws_access_key,
                aws_secret_access_key=self.config.cloud.aws_secret_key,
                region_name=self.config.cloud.aws_region
            )
        return self._logs_client

    def _get_xray_client(self):
        """获取X-Ray客户端"""
        if self._xray_client is None:
            self._xray_client = boto3.client(
                'xray',
                aws_access_key_id=self.config.cloud.aws_access_key,
                aws_secret_access_key=self.config.cloud.aws_secret_key,
                region_name=self.config.cloud.aws_region
            )
        return self._xray_client

    def _get_ec2_client(self):
        """获取EC2客户端"""
        if self._ec2_client is None:
            self._ec2_client = boto3.client(
                'ec2',
                aws_access_key_id=self.config.cloud.aws_access_key,
                aws_secret_access_key=self.config.cloud.aws_secret_key,
                region_name=self.config.cloud.aws_region
            )
        return self._ec2_client

    def _register_all_tools(self):
        """注册所有工具"""
        # 注意：这些方法已经用@tool装饰器装饰了，需要获取实际的函数
        # CloudWatch Metrics
        self.tool_registry.register_tool(
            "aws", "cloudwatch", "get_metric_statistics",
            self._get_metric_statistics_impl,
            metadata={"description": "获取CloudWatch指标统计数据"}
        )

        self.tool_registry.register_tool(
            "aws", "cloudwatch", "list_metrics",
            self._list_metrics_impl,
            metadata={"description": "列出可用的CloudWatch指标"}
        )

        self.tool_registry.register_tool(
            "aws", "cloudwatch", "put_metric_alarm",
            self._put_metric_alarm_impl,
            metadata={"description": "创建或更新CloudWatch告警"}
        )

        self.tool_registry.register_tool(
            "aws", "cloudwatch", "describe_alarms",
            self._describe_alarms_impl,
            metadata={"description": "查询CloudWatch告警状态"}
        )

        # CloudWatch Logs
        self.tool_registry.register_tool(
            "aws", "logs", "filter_log_events",
            self._filter_log_events_impl,
            metadata={"description": "过滤查询日志事件"}
        )

        self.tool_registry.register_tool(
            "aws", "logs", "get_log_events",
            self._get_log_events_impl,
            metadata={"description": "获取日志流中的事件"}
        )

        self.tool_registry.register_tool(
            "aws", "logs", "describe_log_groups",
            self._describe_log_groups_impl,
            metadata={"description": "列出日志组"}
        )

        # X-Ray
        self.tool_registry.register_tool(
            "aws", "xray", "get_trace_summaries",
            self._get_trace_summaries_impl,
            metadata={"description": "获取追踪摘要"}
        )

        self.tool_registry.register_tool(
            "aws", "xray", "get_service_graph",
            self._get_service_graph_impl,
            metadata={"description": "获取服务依赖图"}
        )

        # EC2 + Metrics Combined
        self.tool_registry.register_tool(
            "aws", "ec2", "batch_get_cpu_with_threshold",
            self._batch_get_ec2_cpu_with_threshold_impl,
            metadata={"description": "批量查询EC2实例CPU利用率并按阈值过滤"}
        )

        logger.info("AWS monitoring tools registered successfully")

    async def _get_metric_statistics_impl(
        self,
        namespace: str,
        metric_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        period: int = 300,
        statistics: Optional[List[str]] = None,
        dimensions: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        获取CloudWatch指标统计数据

        Args:
            namespace: AWS命名空间 (如 AWS/EC2, AWS/Lambda)
            metric_name: 指标名称 (如 CPUUtilization)
            start_time: 开始时间 (ISO格式或相对时间如'1h')
            end_time: 结束时间
            period: 统计周期（秒）
            statistics: 统计类型列表 (Average, Sum, Maximum, Minimum, SampleCount)
            dimensions: 维度过滤

        Returns:
            指标统计数据
        """
        try:
            client = self._get_cloudwatch_client()

            # 处理时间
            if start_time is None:
                start_dt = datetime.utcnow() - timedelta(hours=1)
            else:
                start_dt = self._parse_time(start_time)

            if end_time is None:
                end_dt = datetime.utcnow()
            else:
                end_dt = self._parse_time(end_time)

            # 默认统计类型
            if statistics is None:
                statistics = ['Average']

            params = {
                'Namespace': namespace,
                'MetricName': metric_name,
                'StartTime': start_dt,
                'EndTime': end_dt,
                'Period': period,
                'Statistics': statistics
            }

            if dimensions:
                params['Dimensions'] = dimensions

            response = client.get_metric_statistics(**params)

            return {
                "success": True,
                "datapoints": response.get('Datapoints', []),
                "label": response.get('Label'),
                "metadata": {
                    "namespace": namespace,
                    "metric_name": metric_name,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat()
                }
            }

        except ClientError as e:
            logger.error(f"AWS ClientError: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error getting metric statistics: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _list_metrics_impl(
        self,
        namespace: Optional[str] = None,
        metric_name: Optional[str] = None,
        dimensions: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        列出可用的CloudWatch指标

        Args:
            namespace: 过滤命名空间
            metric_name: 过滤指标名称
            dimensions: 过滤维度

        Returns:
            指标列表
        """
        try:
            client = self._get_cloudwatch_client()

            params = {}
            if namespace:
                params['Namespace'] = namespace
            if metric_name:
                params['MetricName'] = metric_name
            if dimensions:
                params['Dimensions'] = dimensions

            response = client.list_metrics(**params)

            return {
                "success": True,
                "metrics": response.get('Metrics', []),
                "count": len(response.get('Metrics', []))
            }

        except Exception as e:
            logger.error(f"Error listing metrics: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _put_metric_alarm_impl(
        self,
        alarm_name: str,
        metric_name: str,
        namespace: str,
        comparison_operator: str,
        threshold: float,
        evaluation_periods: int = 1,
        period: int = 300,
        statistic: str = 'Average',
        dimensions: Optional[List[Dict[str, str]]] = None,
        alarm_description: Optional[str] = None,
        actions_enabled: bool = True,
        alarm_actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建或更新CloudWatch告警

        Args:
            alarm_name: 告警名称
            metric_name: 指标名称
            namespace: 命名空间
            comparison_operator: 比较运算符 (GreaterThanThreshold, LessThanThreshold, etc)
            threshold: 阈值
            evaluation_periods: 评估周期数
            period: 统计周期（秒）
            statistic: 统计类型
            dimensions: 维度
            alarm_description: 告警描述
            actions_enabled: 是否启用操作
            alarm_actions: 告警操作（SNS主题ARN等）

        Returns:
            创建结果
        """
        try:
            client = self._get_cloudwatch_client()

            params = {
                'AlarmName': alarm_name,
                'MetricName': metric_name,
                'Namespace': namespace,
                'ComparisonOperator': comparison_operator,
                'Threshold': threshold,
                'EvaluationPeriods': evaluation_periods,
                'Period': period,
                'Statistic': statistic,
                'ActionsEnabled': actions_enabled
            }

            if dimensions:
                params['Dimensions'] = dimensions
            if alarm_description:
                params['AlarmDescription'] = alarm_description
            if alarm_actions:
                params['AlarmActions'] = alarm_actions

            client.put_metric_alarm(**params)

            return {
                "success": True,
                "alarm_name": alarm_name,
                "message": "Alarm created/updated successfully"
            }

        except Exception as e:
            logger.error(f"Error creating alarm: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _describe_alarms_impl(
        self,
        alarm_names: Optional[List[str]] = None,
        state_value: Optional[str] = None,
        max_records: int = 100
    ) -> Dict[str, Any]:
        """
        查询CloudWatch告警状态

        Args:
            alarm_names: 告警名称列表
            state_value: 状态过滤 (OK, ALARM, INSUFFICIENT_DATA)
            max_records: 最大返回数量

        Returns:
            告警列表
        """
        try:
            client = self._get_cloudwatch_client()

            params = {'MaxRecords': max_records}
            if alarm_names:
                params['AlarmNames'] = alarm_names
            if state_value:
                params['StateValue'] = state_value

            response = client.describe_alarms(**params)

            return {
                "success": True,
                "alarms": response.get('MetricAlarms', []),
                "count": len(response.get('MetricAlarms', []))
            }

        except Exception as e:
            logger.error(f"Error describing alarms: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _filter_log_events_impl(
        self,
        log_group_name: str,
        log_stream_names: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        filter_pattern: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        过滤查询日志事件

        Args:
            log_group_name: 日志组名称
            log_stream_names: 日志流名称列表
            start_time: 开始时间
            end_time: 结束时间
            filter_pattern: 过滤模式
            limit: 最大返回数量

        Returns:
            日志事件列表
        """
        try:
            client = self._get_logs_client()

            params = {
                'logGroupName': log_group_name,
                'limit': limit
            }

            if log_stream_names:
                params['logStreamNames'] = log_stream_names
            if start_time:
                params['startTime'] = int(self._parse_time(start_time).timestamp() * 1000)
            if end_time:
                params['endTime'] = int(self._parse_time(end_time).timestamp() * 1000)
            if filter_pattern:
                params['filterPattern'] = filter_pattern

            response = client.filter_log_events(**params)

            return {
                "success": True,
                "events": response.get('events', []),
                "count": len(response.get('events', [])),
                "next_token": response.get('nextToken')
            }

        except Exception as e:
            logger.error(f"Error filtering log events: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_log_events_impl(
        self,
        log_group_name: str,
        log_stream_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        获取日志流中的事件

        Args:
            log_group_name: 日志组名称
            log_stream_name: 日志流名称
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大返回数量

        Returns:
            日志事件列表
        """
        try:
            client = self._get_logs_client()

            params = {
                'logGroupName': log_group_name,
                'logStreamName': log_stream_name,
                'limit': limit
            }

            if start_time:
                params['startTime'] = int(self._parse_time(start_time).timestamp() * 1000)
            if end_time:
                params['endTime'] = int(self._parse_time(end_time).timestamp() * 1000)

            response = client.get_log_events(**params)

            return {
                "success": True,
                "events": response.get('events', []),
                "count": len(response.get('events', [])),
                "next_forward_token": response.get('nextForwardToken'),
                "next_backward_token": response.get('nextBackwardToken')
            }

        except Exception as e:
            logger.error(f"Error getting log events: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _describe_log_groups_impl(
        self,
        log_group_name_prefix: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        列出日志组

        Args:
            log_group_name_prefix: 日志组名称前缀
            limit: 最大返回数量

        Returns:
            日志组列表
        """
        try:
            client = self._get_logs_client()

            params = {'limit': limit}
            if log_group_name_prefix:
                params['logGroupNamePrefix'] = log_group_name_prefix

            response = client.describe_log_groups(**params)

            return {
                "success": True,
                "log_groups": response.get('logGroups', []),
                "count": len(response.get('logGroups', []))
            }

        except Exception as e:
            logger.error(f"Error describing log groups: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_trace_summaries_impl(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        filter_expression: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取X-Ray追踪摘要

        Args:
            start_time: 开始时间
            end_time: 结束时间
            filter_expression: 过滤表达式

        Returns:
            追踪摘要列表
        """
        try:
            client = self._get_xray_client()

            if start_time is None:
                start_dt = datetime.utcnow() - timedelta(hours=1)
            else:
                start_dt = self._parse_time(start_time)

            if end_time is None:
                end_dt = datetime.utcnow()
            else:
                end_dt = self._parse_time(end_time)

            params = {
                'StartTime': start_dt,
                'EndTime': end_dt
            }

            if filter_expression:
                params['FilterExpression'] = filter_expression

            response = client.get_trace_summaries(**params)

            return {
                "success": True,
                "trace_summaries": response.get('TraceSummaries', []),
                "count": len(response.get('TraceSummaries', []))
            }

        except Exception as e:
            logger.error(f"Error getting trace summaries: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_service_graph_impl(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取X-Ray服务依赖图

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            服务依赖图
        """
        try:
            client = self._get_xray_client()

            if start_time is None:
                start_dt = datetime.utcnow() - timedelta(hours=1)
            else:
                start_dt = self._parse_time(start_time)

            if end_time is None:
                end_dt = datetime.utcnow()
            else:
                end_dt = self._parse_time(end_time)

            response = client.get_service_graph(
                StartTime=start_dt,
                EndTime=end_dt
            )

            return {
                "success": True,
                "services": response.get('Services', []),
                "count": len(response.get('Services', []))
            }

        except Exception as e:
            logger.error(f"Error getting service graph: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _list_ec2_instances_impl(
        self,
        tags: Optional[Dict[str, str]] = None,
        instance_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        列出EC2实例（支持Tag过滤）

        Args:
            tags: Tag过滤字典，如 {"业务": "xxx", "环境": "生产"}
            instance_ids: 实例ID列表
            filters: 自定义过滤器

        Returns:
            EC2实例列表
        """
        try:
            client = self._get_ec2_client()

            params = {}

            # 构建过滤器
            ec2_filters = []

            # Tag过滤
            if tags:
                for key, value in tags.items():
                    ec2_filters.append({
                        'Name': f'tag:{key}',
                        'Values': [value]
                    })

            # 添加自定义过滤器
            if filters:
                ec2_filters.extend(filters)

            if ec2_filters:
                params['Filters'] = ec2_filters

            if instance_ids:
                params['InstanceIds'] = instance_ids

            response = client.describe_instances(**params)

            # 提取实例信息
            instances = []
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instances.append(instance)

            return {
                "success": True,
                "instances": instances,
                "count": len(instances)
            }

        except Exception as e:
            logger.error(f"Error listing EC2 instances: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _query_logs_impl(
        self,
        log_group: str,
        query_string: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        使用CloudWatch Logs Insights查询日志

        Args:
            log_group: 日志组名称
            query_string: 查询字符串
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大结果数

        Returns:
            查询结果
        """
        try:
            client = self._get_logs_client()

            # 处理时间
            if start_time is None:
                start_dt = datetime.utcnow() - timedelta(hours=1)
            else:
                start_dt = self._parse_time(start_time)

            if end_time is None:
                end_dt = datetime.utcnow()
            else:
                end_dt = self._parse_time(end_time)

            # 开始查询
            start_query_response = client.start_query(
                logGroupName=log_group,
                startTime=int(start_dt.timestamp()),
                endTime=int(end_dt.timestamp()),
                queryString=query_string,
                limit=limit
            )

            query_id = start_query_response['queryId']

            # 轮询查询结果（最多等待30秒）
            import time
            max_attempts = 30
            for _ in range(max_attempts):
                time.sleep(1)

                results_response = client.get_query_results(queryId=query_id)
                status = results_response['status']

                if status == 'Complete':
                    return {
                        "success": True,
                        "results": results_response.get('results', []),
                        "statistics": results_response.get('statistics', {})
                    }
                elif status == 'Failed':
                    return {
                        "success": False,
                        "error": "Query failed"
                    }

            return {
                "success": False,
                "error": "Query timeout"
            }

        except Exception as e:
            logger.error(f"Error querying logs: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _batch_get_ec2_cpu_with_threshold_impl(
        self,
        threshold: float = 80.0,
        tags: Optional[Dict[str, str]] = None,
        instance_ids: Optional[List[str]] = None,
        period: int = 300,
        duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        批量查询EC2实例CPU利用率并按阈值过滤

        Args:
            threshold: CPU利用率阈值（百分比，默认80）
            tags: Tag过滤条件，如 {"业务": "电商平台"}
            instance_ids: 指定实例ID列表（可选）
            period: 统计周期（秒，默认300）
            duration_minutes: 查询时长（分钟，默认60）

        Returns:
            高CPU实例列表，包含实例信息和CPU指标
        """
        try:
            # 1. 获取EC2实例列表
            instances_response = await self._list_ec2_instances_impl(
                tags=tags,
                instance_ids=instance_ids
            )

            if not instances_response.get("success"):
                return instances_response

            instances = instances_response.get("instances", [])

            if not instances:
                return {
                    "success": True,
                    "high_cpu_instances": [],
                    "count": 0,
                    "message": "No instances found matching criteria"
                }

            logger.info(f"Found {len(instances)} instances, querying CPU metrics...")

            # 2. 批量查询CPU指标（并行）
            import asyncio

            async def get_instance_cpu(instance):
                instance_id = instance["InstanceId"]

                # 查询CPU指标
                cpu_response = await self._get_metric_statistics_impl(
                    namespace="AWS/EC2",
                    metric_name="CPUUtilization",
                    start_time=f"{duration_minutes}m",
                    period=period,
                    statistics=["Average", "Maximum"],
                    dimensions=[{
                        "Name": "InstanceId",
                        "Value": instance_id
                    }]
                )

                if not cpu_response.get("success"):
                    logger.warning(f"Failed to get CPU for {instance_id}: {cpu_response.get('error')}")
                    return None

                datapoints = cpu_response.get("datapoints", [])

                if not datapoints:
                    logger.debug(f"No CPU data for {instance_id}")
                    return None

                # 计算平均CPU和最大CPU
                avg_cpu = sum(dp.get("Average", 0) for dp in datapoints) / len(datapoints)
                max_cpu = max(dp.get("Maximum", 0) for dp in datapoints)

                return {
                    "instance": instance,
                    "instance_id": instance_id,
                    "avg_cpu": round(avg_cpu, 2),
                    "max_cpu": round(max_cpu, 2),
                    "datapoints_count": len(datapoints),
                    "cpu_datapoints": datapoints
                }

            # 并行查询所有实例的CPU
            results = await asyncio.gather(
                *[get_instance_cpu(inst) for inst in instances],
                return_exceptions=True
            )

            # 3. 过滤高CPU实例
            high_cpu_instances = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error querying CPU: {result}")
                    continue

                if result is None:
                    continue

                # 检查是否超过阈值
                if result["avg_cpu"] >= threshold or result["max_cpu"] >= threshold:
                    # 提取关键实例信息
                    instance = result["instance"]
                    tags_dict = {}
                    for tag in instance.get("Tags", []):
                        tags_dict[tag["Key"]] = tag["Value"]

                    high_cpu_instances.append({
                        "instance_id": result["instance_id"],
                        "instance_type": instance.get("InstanceType"),
                        "state": instance.get("State", {}).get("Name"),
                        "tags": tags_dict,
                        "avg_cpu_utilization": result["avg_cpu"],
                        "max_cpu_utilization": result["max_cpu"],
                        "datapoints_count": result["datapoints_count"],
                        "cpu_datapoints": result["cpu_datapoints"]
                    })

            # 按平均CPU降序排序
            high_cpu_instances.sort(key=lambda x: x["avg_cpu_utilization"], reverse=True)

            logger.info(
                f"Found {len(high_cpu_instances)} instances with CPU >= {threshold}% "
                f"out of {len(instances)} total instances"
            )

            return {
                "success": True,
                "high_cpu_instances": high_cpu_instances,
                "count": len(high_cpu_instances),
                "total_instances_checked": len(instances),
                "threshold": threshold,
                "query_metadata": {
                    "period_seconds": period,
                    "duration_minutes": duration_minutes
                }
            }

        except Exception as e:
            logger.error(f"Error in batch_get_ec2_cpu_with_threshold: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_time(self, time_str: str) -> datetime:
        """
        解析时间字符串

        支持格式：
        - ISO格式: 2024-01-01T00:00:00Z
        - 相对时间: 1h, 30m, 1d
        """
        if isinstance(time_str, datetime):
            return time_str

        # 尝试ISO格式
        try:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except:
            pass

        # 尝试相对时间
        now = datetime.utcnow()
        if time_str.endswith('h'):
            hours = int(time_str[:-1])
            return now - timedelta(hours=hours)
        elif time_str.endswith('m'):
            minutes = int(time_str[:-1])
            return now - timedelta(minutes=minutes)
        elif time_str.endswith('d'):
            days = int(time_str[:-1])
            return now - timedelta(days=days)

        raise ValueError(f"Invalid time format: {time_str}")
