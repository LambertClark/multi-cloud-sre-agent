"""
Azure可观测性工具集（示例/参考实现）

⚠️ 重要说明：
本文件不应该在系统启动时自动初始化！

用途：
1. 作为Agent代码生成的参考实现
2. 用于测试和验证
3. 可选的手动注册（如果用户明确需要）

核心理念：工具应该由Agent根据用户需求动态生成，而不是硬编码。
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from azure.identity import ClientSecretCredential
try:
    from azure.monitor.query import LogsQueryClient
except ImportError:
    LogsQueryClient = None
from azure.mgmt.monitor import MonitorManagementClient
from azure.core.exceptions import AzureError

from config import get_config
from .cloud_tools import get_tool_registry

logger = logging.getLogger(__name__)


class AzureMonitoringTools:
    """Azure监控工具类"""

    def __init__(self):
        self.config = get_config()
        self._credential = None
        self._logs_client = None
        self._monitor_mgmt_client = None
        self.tool_registry = get_tool_registry()
        self._register_all_tools()

    def _get_credential(self):
        """获取Azure凭证"""
        if self._credential is None:
            self._credential = ClientSecretCredential(
                tenant_id=self.config.cloud.azure_tenant_id,
                client_id=self.config.cloud.azure_client_id,
                client_secret=self.config.cloud.azure_client_secret
            )
        return self._credential

    def _get_metrics_client(self):
        """获取Azure Monitor Metrics客户端 (使用MonitorManagementClient)"""
        # Azure Monitor指标查询使用MonitorManagementClient
        return self._get_monitor_mgmt_client()

    def _get_logs_client(self):
        """获取Log Analytics客户端"""
        if self._logs_client is None:
            if LogsQueryClient is None:
                raise ImportError("LogsQueryClient is not available. Please install azure-monitor-query package.")
            self._logs_client = LogsQueryClient(self._get_credential())
        return self._logs_client

    def _get_monitor_mgmt_client(self):
        """获取Monitor Management客户端"""
        if self._monitor_mgmt_client is None:
            self._monitor_mgmt_client = MonitorManagementClient(
                credential=self._get_credential(),
                subscription_id=self.config.cloud.azure_subscription_id
            )
        return self._monitor_mgmt_client

    def _register_all_tools(self):
        """注册所有工具"""
        # Azure Monitor Metrics
        self.tool_registry.register_tool(
            "azure", "monitor", "get_metric_statistics",
            self._get_metric_statistics_impl,
            metadata={"description": "获取Azure Monitor指标统计数据"}
        )

        self.tool_registry.register_tool(
            "azure", "monitor", "list_metrics",
            self._list_metrics_impl,
            metadata={"description": "列出可用的Azure Monitor指标"}
        )

        self.tool_registry.register_tool(
            "azure", "monitor", "create_metric_alert",
            self._create_metric_alert_impl,
            metadata={"description": "创建或更新Azure Monitor告警"}
        )

        self.tool_registry.register_tool(
            "azure", "monitor", "list_alert_rules",
            self._list_alert_rules_impl,
            metadata={"description": "查询Azure Monitor告警规则"}
        )

        # Log Analytics
        self.tool_registry.register_tool(
            "azure", "logs", "query_logs",
            self._query_logs_impl,
            metadata={"description": "使用KQL查询Log Analytics"}
        )

        self.tool_registry.register_tool(
            "azure", "logs", "list_workspaces",
            self._list_workspaces_impl,
            metadata={"description": "列出Log Analytics工作区"}
        )

        # Application Insights
        self.tool_registry.register_tool(
            "azure", "appinsights", "query_traces",
            self._query_traces_impl,
            metadata={"description": "查询Application Insights追踪数据"}
        )

        self.tool_registry.register_tool(
            "azure", "appinsights", "query_dependencies",
            self._query_dependencies_impl,
            metadata={"description": "查询Application Insights依赖关系"}
        )

        logger.info("Azure monitoring tools registered successfully")

    async def _get_metric_statistics_impl(
        self,
        resource_uri: str,
        metric_names: List[str],
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "PT5M",
        aggregation: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        获取Azure Monitor指标统计数据

        Args:
            resource_uri: Azure资源URI (如 /subscriptions/{id}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{vm})
            metric_names: 指标名称列表 (如 ["Percentage CPU", "Network In"])
            start_time: 开始时间 (ISO格式或相对时间如'1h')
            end_time: 结束时间
            interval: 时间粒度 (ISO 8601格式, 如 PT1M, PT5M, PT1H)
            aggregation: 聚合类型列表 (Average, Total, Maximum, Minimum, Count)

        Returns:
            指标统计数据
        """
        try:
            client = self._get_metrics_client()

            # 处理时间
            if start_time is None:
                start_dt = datetime.utcnow() - timedelta(hours=1)
            else:
                start_dt = self._parse_time(start_time)

            if end_time is None:
                end_dt = datetime.utcnow()
            else:
                end_dt = self._parse_time(end_time)

            # 默认聚合类型
            if aggregation is None:
                aggregation = ["Average"]

            # 查询指标
            response = client.query_resource(
                resource_uri=resource_uri,
                metric_names=metric_names,
                timespan=(start_dt, end_dt),
                granularity=timedelta(seconds=self._parse_interval(interval)),
                aggregations=aggregation
            )

            # 格式化结果
            metrics_data = []
            for metric in response.metrics:
                metric_info = {
                    "name": metric.name,
                    "unit": metric.unit,
                    "timeseries": []
                }

                for timeseries in metric.timeseries:
                    ts_data = {
                        "metadata": timeseries.metadata_values if hasattr(timeseries, 'metadata_values') else {},
                        "data": []
                    }

                    for data_point in timeseries.data:
                        point = {
                            "timestamp": data_point.timestamp.isoformat(),
                        }
                        if data_point.average is not None:
                            point["average"] = data_point.average
                        if data_point.total is not None:
                            point["total"] = data_point.total
                        if data_point.maximum is not None:
                            point["maximum"] = data_point.maximum
                        if data_point.minimum is not None:
                            point["minimum"] = data_point.minimum
                        if data_point.count is not None:
                            point["count"] = data_point.count

                        ts_data["data"].append(point)

                    metric_info["timeseries"].append(ts_data)

                metrics_data.append(metric_info)

            return {
                "success": True,
                "metrics": metrics_data,
                "metadata": {
                    "resource_uri": resource_uri,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat(),
                    "interval": interval
                }
            }

        except AzureError as e:
            logger.error(f"Azure Error: {str(e)}")
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
        resource_uri: str,
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        列出可用的Azure Monitor指标定义

        Args:
            resource_uri: Azure资源URI
            namespace: 指标命名空间过滤

        Returns:
            指标定义列表
        """
        try:
            client = self._get_monitor_mgmt_client()

            # 获取指标定义
            params = {}
            if namespace:
                params['metricnamespace'] = namespace

            metric_definitions = client.metric_definitions.list(
                resource_uri=resource_uri,
                **params
            )

            metrics = []
            for metric_def in metric_definitions:
                metrics.append({
                    "name": metric_def.name.value,
                    "unit": metric_def.unit,
                    "primary_aggregation_type": metric_def.primary_aggregation_type,
                    "supported_aggregations": [agg for agg in metric_def.supported_aggregation_types] if metric_def.supported_aggregation_types else [],
                    "metric_availabilities": [
                        {
                            "time_grain": str(avail.time_grain),
                            "retention": str(avail.retention)
                        } for avail in metric_def.metric_availabilities
                    ] if metric_def.metric_availabilities else [],
                    "namespace": metric_def.namespace,
                    "dimensions": [dim.value for dim in metric_def.dimensions] if metric_def.dimensions else []
                })

            return {
                "success": True,
                "metrics": metrics,
                "count": len(metrics)
            }

        except Exception as e:
            logger.error(f"Error listing metrics: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _create_metric_alert_impl(
        self,
        resource_group: str,
        alert_rule_name: str,
        target_resource_uri: str,
        metric_name: str,
        operator: str,
        threshold: float,
        aggregation: str = "Average",
        window_size: str = "PT5M",
        frequency: str = "PT1M",
        severity: int = 3,
        description: Optional[str] = None,
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        创建或更新Azure Monitor指标告警

        Args:
            resource_group: 资源组名称
            alert_rule_name: 告警规则名称
            target_resource_uri: 目标资源URI
            metric_name: 指标名称
            operator: 比较运算符 (GreaterThan, LessThan, GreaterOrLessThan, etc)
            threshold: 阈值
            aggregation: 聚合类型 (Average, Total, Maximum, Minimum, Count)
            window_size: 评估窗口大小 (ISO 8601格式)
            frequency: 评估频率 (ISO 8601格式)
            severity: 严重性 (0-4, 0最严重)
            description: 告警描述
            enabled: 是否启用

        Returns:
            创建结果
        """
        try:
            client = self._get_monitor_mgmt_client()

            # 构建告警规则
            from azure.mgmt.monitor.models import (
                MetricAlertResource,
                MetricAlertCriteria,
                MetricCriteria
            )

            criteria = MetricAlertCriteria(
                all_of=[
                    MetricCriteria(
                        name="metric1",
                        metric_name=metric_name,
                        operator=operator,
                        threshold=threshold,
                        time_aggregation=aggregation
                    )
                ]
            )

            alert_rule = MetricAlertResource(
                description=description or f"Alert for {metric_name}",
                severity=severity,
                enabled=enabled,
                scopes=[target_resource_uri],
                evaluation_frequency=frequency,
                window_size=window_size,
                criteria=criteria,
                location="global"
            )

            # 创建或更新告警规则
            result = client.metric_alerts.create_or_update(
                resource_group_name=resource_group,
                rule_name=alert_rule_name,
                parameters=alert_rule
            )

            return {
                "success": True,
                "alert_rule_name": alert_rule_name,
                "id": result.id,
                "message": "Alert rule created/updated successfully"
            }

        except Exception as e:
            logger.error(f"Error creating metric alert: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _list_alert_rules_impl(
        self,
        resource_group: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        查询Azure Monitor告警规则

        Args:
            resource_group: 资源组名称 (如果为空则列出所有)

        Returns:
            告警规则列表
        """
        try:
            client = self._get_monitor_mgmt_client()

            if resource_group:
                alert_rules = client.metric_alerts.list_by_resource_group(resource_group)
            else:
                alert_rules = client.metric_alerts.list_by_subscription()

            rules = []
            for rule in alert_rules:
                rules.append({
                    "name": rule.name,
                    "id": rule.id,
                    "description": rule.description,
                    "severity": rule.severity,
                    "enabled": rule.enabled,
                    "scopes": rule.scopes,
                    "evaluation_frequency": rule.evaluation_frequency,
                    "window_size": rule.window_size
                })

            return {
                "success": True,
                "alert_rules": rules,
                "count": len(rules)
            }

        except Exception as e:
            logger.error(f"Error listing alert rules: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _query_logs_impl(
        self,
        workspace_id: str,
        query: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        使用KQL查询Log Analytics

        Args:
            workspace_id: Log Analytics工作区ID
            query: KQL查询语句
            start_time: 开始时间
            end_time: 结束时间
            timeout: 查询超时时间（秒）

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

            # 执行查询
            response = client.query_workspace(
                workspace_id=workspace_id,
                query=query,
                timespan=(start_dt, end_dt),
                server_timeout=timeout
            )

            # 格式化结果
            results = []
            if response.tables:
                for table in response.tables:
                    table_data = {
                        "name": table.name,
                        "columns": [col.name for col in table.columns],
                        "rows": []
                    }

                    for row in table.rows:
                        row_dict = {}
                        for i, col in enumerate(table.columns):
                            row_dict[col.name] = row[i]
                        table_data["rows"].append(row_dict)

                    results.append(table_data)

            return {
                "success": True,
                "tables": results,
                "metadata": {
                    "workspace_id": workspace_id,
                    "query": query,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat()
                }
            }

        except AzureError as e:
            logger.error(f"Azure Error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error querying logs: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _list_workspaces_impl(
        self,
        resource_group: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        列出Log Analytics工作区

        Args:
            resource_group: 资源组名称 (如果为空则列出所有)

        Returns:
            工作区列表
        """
        try:
            from azure.mgmt.loganalytics import LogAnalyticsManagementClient

            client = LogAnalyticsManagementClient(
                credential=self._get_credential(),
                subscription_id=self.config.cloud.azure_subscription_id
            )

            if resource_group:
                workspaces = client.workspaces.list_by_resource_group(resource_group)
            else:
                workspaces = client.workspaces.list()

            workspace_list = []
            for ws in workspaces:
                workspace_list.append({
                    "name": ws.name,
                    "id": ws.id,
                    "customer_id": ws.customer_id,
                    "location": ws.location,
                    "sku": ws.sku.name if ws.sku else None,
                    "retention_in_days": ws.retention_in_days
                })

            return {
                "success": True,
                "workspaces": workspace_list,
                "count": len(workspace_list)
            }

        except Exception as e:
            logger.error(f"Error listing workspaces: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _query_traces_impl(
        self,
        app_insights_id: str,
        query: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        查询Application Insights追踪数据

        Args:
            app_insights_id: Application Insights应用ID
            query: KQL查询语句 (针对traces表)
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            追踪数据
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

            # 如果查询不包含traces表,自动添加
            if "traces" not in query.lower():
                query = f"traces | {query}"

            # 执行查询
            response = client.query_workspace(
                workspace_id=app_insights_id,
                query=query,
                timespan=(start_dt, end_dt)
            )

            # 格式化结果
            traces = []
            if response.tables:
                for table in response.tables:
                    for row in table.rows:
                        trace_dict = {}
                        for i, col in enumerate(table.columns):
                            trace_dict[col.name] = row[i]
                        traces.append(trace_dict)

            return {
                "success": True,
                "traces": traces,
                "count": len(traces),
                "metadata": {
                    "app_insights_id": app_insights_id,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error querying traces: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _query_dependencies_impl(
        self,
        app_insights_id: str,
        query: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        查询Application Insights依赖关系

        Args:
            app_insights_id: Application Insights应用ID
            query: KQL查询语句 (可选,针对dependencies表)
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            依赖关系数据
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

            # 默认查询
            if not query:
                query = """
                dependencies
                | summarize
                    count=count(),
                    avg_duration=avg(duration),
                    success_rate=countif(success == true) * 100.0 / count()
                    by target, type
                | order by count desc
                """

            # 执行查询
            response = client.query_workspace(
                workspace_id=app_insights_id,
                query=query,
                timespan=(start_dt, end_dt)
            )

            # 格式化结果
            dependencies = []
            if response.tables:
                for table in response.tables:
                    for row in table.rows:
                        dep_dict = {}
                        for i, col in enumerate(table.columns):
                            dep_dict[col.name] = row[i]
                        dependencies.append(dep_dict)

            return {
                "success": True,
                "dependencies": dependencies,
                "count": len(dependencies),
                "metadata": {
                    "app_insights_id": app_insights_id,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error querying dependencies: {str(e)}")
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

    def _parse_interval(self, interval: str) -> int:
        """
        解析ISO 8601间隔为秒数

        Args:
            interval: ISO 8601格式 (如 PT1M, PT5M, PT1H)

        Returns:
            秒数
        """
        # 简单解析PT格式
        if not interval.startswith('PT'):
            raise ValueError(f"Invalid interval format: {interval}")

        interval = interval[2:]  # 移除PT前缀

        if interval.endswith('M'):
            return int(interval[:-1]) * 60
        elif interval.endswith('H'):
            return int(interval[:-1]) * 3600
        elif interval.endswith('S'):
            return int(interval[:-1])
        else:
            raise ValueError(f"Invalid interval format: PT{interval}")
