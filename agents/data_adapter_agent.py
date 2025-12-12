"""
Data Adapter Agent - 数据适配Agent
将多云平台的原始数据转换为统一Schema
采用混合架构：规则引擎（快速路径）+ LLM引擎（智能路径）
"""
from typing import Dict, Any, Optional, List, Type
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import json
import logging
from datetime import datetime

from .base_agent import BaseAgent, AgentResponse
from config import get_config
from rag_system import get_rag_system

# 导入Schema
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from schemas.health_schema import (
    MetricHealth, LogHealth, TraceHealth, ResourceHealth,
    HealthStatus, SeverityLevel, HealthIssue
)
from schemas.resource_schema import (
    ComputeResource, ContainerResource, NetworkResource, CDNResource,
    ResourceState, ResourceType
)
from schemas.metric_schema import (
    MetricResult, MetricDataPoint, MetricUnit, StatisticType
)

logger = logging.getLogger(__name__)


class DataAdapterAgent(BaseAgent):
    """
    数据适配Agent

    职责：
    1. 将云平台原始数据转换为统一Schema
    2. 优先使用规则引擎（快速）
    3. 规则不存在时使用LLM智能转换
    4. 支持查询RAG获取API文档辅助理解
    """

    # 规则引擎：已知的快速映射规则
    FAST_RULES = {
        "aws": {
            "ec2_to_compute": {
                "applicable": lambda data: "InstanceId" in data,
                "converter": "_convert_aws_ec2_fast",
            },
            "cloudwatch_metric": {
                "applicable": lambda data: "Datapoints" in data or "datapoints" in data,
                "converter": "_convert_aws_metric_fast",
            },
            "xray_traces": {
                "applicable": lambda data: "TraceSummaries" in data or "trace_summaries" in data,
                "converter": "_convert_aws_xray_fast",
            },
            "cloudwatch_logs": {
                "applicable": lambda data: "events" in data,
                "converter": "_convert_aws_logs_fast",
            },
        },
        "azure": {
            "vm_to_compute": {
                "applicable": lambda data: "vmId" in data or "id" in data and "/virtualMachines/" in data.get("id", ""),
                "converter": "_convert_azure_vm_fast",
            },
            "monitor_metric": {
                "applicable": lambda data: "value" in data and isinstance(data.get("value"), list) and any("timeseries" in item for item in data.get("value", [])),
                "converter": "_convert_azure_metric_fast",
            },
            "app_insights_traces": {
                "applicable": lambda data: "tables" in data and any(t.get("name") == "traces" for t in data.get("tables", [])),
                "converter": "_convert_azure_traces_fast",
            },
        },
        "gcp": {
            "gce_to_compute": {
                "applicable": lambda data: "id" in data and "machineType" in data and "zone" in data,
                "converter": "_convert_gcp_gce_fast",
            },
            "monitoring_metric": {
                "applicable": lambda data: "timeSeries" in data or "metricDescriptor" in data,
                "converter": "_convert_gcp_metric_fast",
            },
            "cloud_trace": {
                "applicable": lambda data: "spans" in data or "traceId" in data,
                "converter": "_convert_gcp_trace_fast",
            },
        },
        "kubernetes": {
            "pod_to_container": {
                "applicable": lambda data: data.get("kind") == "Pod" or (
                    "metadata" in data and "spec" in data and "status" in data
                ),
                "converter": "_convert_k8s_pod_fast",
            },
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("DataAdapterAgent", config)
        self.config_obj = get_config()
        self.llm = self._init_llm()
        self.rag_system = get_rag_system()

    def _init_llm(self) -> ChatOpenAI:
        """初始化LLM"""
        llm_config = self.config_obj.llm
        return ChatOpenAI(
            model=llm_config.model,
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            temperature=0.1,  # 数据转换需要精确性
            max_tokens=llm_config.max_tokens
        )

    def get_capabilities(self) -> List[str]:
        """获取Agent能力"""
        return [
            "多云数据格式统一转换",
            "规则引擎快速映射",
            "LLM智能适配未知格式",
            "RAG辅助理解API文档",
            "支持AWS/Azure/GCP/阿里云/腾讯云/K8s等"
        ]

    def validate_input(self, input_data: Any) -> bool:
        """验证输入"""
        if not isinstance(input_data, dict):
            return False
        required = ["raw_data", "cloud_provider", "target_schema"]
        return all(key in input_data for key in required)

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        处理数据转换请求

        Args:
            input_data: {
                "raw_data": {...},              # 云平台原始数据
                "cloud_provider": "aws",        # 云厂商
                "resource_type": "ec2",         # 资源类型（可选）
                "target_schema": "ComputeResource",  # 目标Schema名称
                "context": {...}                # 额外上下文（可选）
            }

        Returns:
            AgentResponse 包含转换后的Schema对象
        """
        try:
            raw_data = input_data["raw_data"]
            cloud_provider = input_data["cloud_provider"].lower()
            target_schema = input_data["target_schema"]
            resource_type = input_data.get("resource_type", "unknown")
            context = input_data.get("context", {})

            logger.info(f"Converting {cloud_provider} data to {target_schema}")

            # 第一步：尝试快速路径（规则引擎）
            fast_result = await self._try_fast_path(
                raw_data, cloud_provider, target_schema, resource_type
            )

            if fast_result["success"]:
                logger.info(f"Fast path succeeded for {cloud_provider}/{target_schema}")
                return AgentResponse(
                    success=True,
                    data=fast_result["data"],
                    metadata={
                        "conversion_method": "fast_rule",
                        "cloud_provider": cloud_provider,
                        "target_schema": target_schema
                    }
                )

            # 第二步：快速路径失败，使用LLM智能转换
            logger.info(f"Fast path failed, using LLM for {cloud_provider}/{target_schema}")
            llm_result = await self._llm_conversion(
                raw_data, cloud_provider, target_schema, resource_type, context
            )

            return AgentResponse(
                success=llm_result["success"],
                data=llm_result.get("data"),
                error=llm_result.get("error"),
                metadata={
                    "conversion_method": "llm_intelligent",
                    "cloud_provider": cloud_provider,
                    "target_schema": target_schema,
                    "rag_used": llm_result.get("rag_used", False)
                }
            )

        except Exception as e:
            logger.error(f"Error in DataAdapterAgent: {str(e)}")
            return AgentResponse(
                success=False,
                error=f"Conversion failed: {str(e)}"
            )

    async def _try_fast_path(
        self,
        raw_data: Dict[str, Any],
        cloud_provider: str,
        target_schema: str,
        resource_type: str
    ) -> Dict[str, Any]:
        """尝试快速路径转换"""

        # 检查是否有该云平台的规则
        if cloud_provider not in self.FAST_RULES:
            return {"success": False, "reason": "No rules for cloud provider"}

        provider_rules = self.FAST_RULES[cloud_provider]

        # 遍历规则，找到适用的
        for rule_name, rule in provider_rules.items():
            try:
                # 检查是否适用
                if rule["applicable"](raw_data):
                    # 调用对应的转换方法
                    converter_method = getattr(self, rule["converter"])
                    converted_data = converter_method(raw_data, target_schema)

                    if converted_data:
                        return {
                            "success": True,
                            "data": converted_data,
                            "rule_used": rule_name
                        }
            except Exception as e:
                logger.warning(f"Fast rule {rule_name} failed: {str(e)}")
                continue

        return {"success": False, "reason": "No applicable rule found"}

    async def _llm_conversion(
        self,
        raw_data: Dict[str, Any],
        cloud_provider: str,
        target_schema: str,
        resource_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """LLM智能转换"""

        # 可选：查询RAG获取API文档
        rag_context = ""
        rag_used = False

        if resource_type != "unknown":
            try:
                rag_results = await self.rag_system.query(
                    query_text=f"{cloud_provider} {resource_type} API response format",
                    cloud_provider=cloud_provider,
                    top_k=3
                )
                if rag_results.get("success"):
                    rag_used = True
                    rag_docs = rag_results.get("results", [])
                    rag_context = "\n\n".join([
                        f"API文档片段 {i+1}:\n{doc.get('text', '')}"
                        for i, doc in enumerate(rag_docs)
                    ])
            except Exception as e:
                logger.warning(f"RAG query failed: {str(e)}")

        # 获取目标Schema定义
        schema_definition = self._get_schema_definition(target_schema)

        # 构建Prompt
        system_prompt = f"""你是一个数据格式转换专家。你的任务是将云平台的原始API响应数据转换为统一的Schema格式。

目标Schema定义：
{schema_definition}

要求：
1. 仔细理解原始数据的结构
2. 将字段映射到目标Schema
3. 处理嵌套字段和数组
4. 转换时间格式为ISO 8601
5. 映射状态枚举值
6. 只返回JSON格式的转换结果，不要额外说明
7. 如果某些字段在原始数据中不存在，使用null或合理的默认值
"""

        user_prompt = f"""请将以下{cloud_provider}云平台的原始数据转换为目标Schema格式。

原始数据：
```json
{json.dumps(raw_data, indent=2, ensure_ascii=False)[:3000]}
```

资源类型：{resource_type}
目标Schema：{target_schema}

额外上下文：
{json.dumps(context, indent=2, ensure_ascii=False) if context else "无"}

{f"API文档参考：{rag_context[:1000]}" if rag_context else ""}

请返回转换后的JSON数据，确保符合目标Schema的所有字段定义。
"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self.llm.ainvoke(messages)
            content = response.content.strip()

            # 提取JSON
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            # 解析JSON
            converted_data = json.loads(content)

            # 尝试实例化Schema对象（验证）
            schema_obj = self._instantiate_schema(target_schema, converted_data)

            return {
                "success": True,
                "data": schema_obj,
                "rag_used": rag_used
            }

        except json.JSONDecodeError as e:
            logger.error(f"LLM返回的不是有效JSON: {str(e)}")
            return {
                "success": False,
                "error": f"LLM转换失败：返回格式错误 - {str(e)}"
            }
        except Exception as e:
            logger.error(f"LLM conversion error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    # ==================== 快速路径转换方法 ====================

    def _convert_aws_ec2_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """AWS EC2快速转换"""
        try:
            # 提取标签
            tags = {tag["Key"]: tag["Value"] for tag in raw_data.get("Tags", [])}

            # 状态映射
            state_mapping = {
                "running": ResourceState.RUNNING,
                "stopped": ResourceState.STOPPED,
                "pending": ResourceState.PENDING,
                "shutting-down": ResourceState.TERMINATING,
                "terminated": ResourceState.TERMINATED,
            }

            aws_state = raw_data.get("State", {}).get("Name", "unknown")

            return ComputeResource(
                resource_id=raw_data.get("InstanceId", ""),
                resource_name=tags.get("Name"),
                resource_type=ResourceType.EC2,
                cloud_provider="aws",
                state=state_mapping.get(aws_state, ResourceState.UNKNOWN),
                created_at=raw_data.get("LaunchTime"),
                region=raw_data.get("Placement", {}).get("AvailabilityZone", "")[:-1],
                availability_zone=raw_data.get("Placement", {}).get("AvailabilityZone"),
                tags=tags,
                instance_type=raw_data.get("InstanceType"),
                private_ip=raw_data.get("PrivateIpAddress"),
                public_ip=raw_data.get("PublicIpAddress"),
                vpc_id=raw_data.get("VpcId"),
                subnet_id=raw_data.get("SubnetId"),
                raw_data=raw_data,
            )
        except Exception as e:
            logger.error(f"Fast EC2 conversion failed: {str(e)}")
            return None

    def _convert_aws_metric_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """AWS CloudWatch Metric快速转换"""
        try:
            datapoints = []
            for dp in raw_data.get("datapoints", raw_data.get("Datapoints", [])):
                datapoints.append(
                    MetricDataPoint(
                        timestamp=dp.get("Timestamp"),
                        value=dp.get("Average") or dp.get("Sum") or dp.get("Maximum", 0),
                        unit=MetricUnit(dp.get("Unit", "None")),
                        statistic=StatisticType.AVERAGE,
                    )
                )

            datapoints.sort(key=lambda x: x.timestamp)

            return MetricResult(
                metric_namespace=raw_data.get("metadata", {}).get("namespace", ""),
                metric_name=raw_data.get("metadata", {}).get("metric_name", ""),
                dimensions=raw_data.get("metadata", {}).get("dimensions", {}),
                datapoints=datapoints,
                unit=MetricUnit(datapoints[0].unit) if datapoints else MetricUnit.NONE,
                cloud_provider="aws",
                raw_data=raw_data,
            )
        except Exception as e:
            logger.error(f"Fast Metric conversion failed: {str(e)}")
            return None

    def _convert_aws_xray_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """AWS X-Ray快速转换"""
        try:
            from schemas.health_schema import TraceHealth

            trace_summaries = raw_data.get("trace_summaries", raw_data.get("TraceSummaries", []))

            total_traces = len(trace_summaries)
            error_traces = 0
            durations = []

            for trace in trace_summaries:
                duration_ms = trace.get("Duration", 0) * 1000

                if trace.get("IsError") or trace.get("IsFault") or trace.get("IsThrottle"):
                    error_traces += 1

                durations.append(duration_ms)

            durations.sort()
            n = len(durations)

            avg_duration = sum(durations) / n if n > 0 else 0
            p50 = durations[int(n * 0.5)] if n > 0 else 0
            p95 = durations[int(n * 0.95)] if n > 0 else 0
            p99 = durations[int(n * 0.99)] if n > 0 else 0

            error_rate = error_traces / total_traces if total_traces > 0 else 0
            is_healthy = error_rate < 0.01 and p95 < 1000
            health_score = max(0, 100 - (error_rate * 1000) - (p95 / 100))

            return TraceHealth(
                service_name=raw_data.get("service_name", "unknown"),
                time_range={
                    "start": raw_data.get("start_time", datetime.utcnow()),
                    "end": raw_data.get("end_time", datetime.utcnow())
                },
                total_traces=total_traces,
                error_traces=error_traces,
                error_rate=error_rate,
                avg_duration_ms=avg_duration,
                p50_duration_ms=p50,
                p95_duration_ms=p95,
                p99_duration_ms=p99,
                is_healthy=is_healthy,
                health_score=health_score,
                raw_data=raw_data,
                cloud_provider="aws",
            )
        except Exception as e:
            logger.error(f"Fast XRay conversion failed: {str(e)}")
            return None

    def _convert_aws_logs_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """AWS CloudWatch Logs快速转换"""
        try:
            from schemas.health_schema import LogHealth

            events = raw_data.get("events", [])
            total_logs = len(events)

            error_count = 0
            warning_count = 0
            critical_count = 0

            for event in events:
                message = event.get("message", "").upper()

                if "CRITICAL" in message or "FATAL" in message:
                    critical_count += 1
                elif "ERROR" in message:
                    error_count += 1
                elif "WARN" in message:
                    warning_count += 1

            error_rate = (error_count + critical_count) / total_logs if total_logs > 0 else 0
            is_healthy = error_rate < 0.01 and critical_count == 0
            health_score = max(0, 100 - (error_rate * 1000) - (critical_count * 10))

            return LogHealth(
                log_source=raw_data.get("log_group", "unknown"),
                time_range={
                    "start": raw_data.get("start_time", datetime.utcnow()),
                    "end": raw_data.get("end_time", datetime.utcnow())
                },
                total_logs=total_logs,
                error_count=error_count,
                warning_count=warning_count,
                critical_count=critical_count,
                error_rate=error_rate,
                is_healthy=is_healthy,
                health_score=health_score,
                raw_data=raw_data,
                cloud_provider="aws",
            )
        except Exception as e:
            logger.error(f"Fast Logs conversion failed: {str(e)}")
            return None

    def _convert_k8s_pod_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """Kubernetes Pod快速转换"""
        try:
            metadata = raw_data.get("metadata", {})
            spec = raw_data.get("spec", {})
            status = raw_data.get("status", {})

            phase = status.get("phase", "Unknown")
            state_mapping = {
                "Running": ResourceState.RUNNING,
                "Pending": ResourceState.PENDING,
                "Succeeded": ResourceState.TERMINATED,
                "Failed": ResourceState.ERROR,
                "Unknown": ResourceState.UNKNOWN,
            }

            restart_count = sum(
                cs.get("restartCount", 0)
                for cs in status.get("containerStatuses", [])
            )

            containers = spec.get("containers", [])
            resources = containers[0].get("resources", {}) if containers else {}

            return ContainerResource(
                resource_id=f"{metadata.get('namespace', 'default')}/{metadata.get('name', '')}",
                resource_name=metadata.get("name"),
                resource_type=ResourceType.POD,
                cloud_provider="kubernetes",
                state=state_mapping.get(phase, ResourceState.UNKNOWN),
                created_at=datetime.fromisoformat(
                    metadata.get("creationTimestamp", "").replace("Z", "+00:00")
                ) if metadata.get("creationTimestamp") else None,
                tags=metadata.get("labels", {}),
                namespace=metadata.get("namespace"),
                container_image=containers[0].get("image") if containers else None,
                container_count=len(containers),
                cpu_request=resources.get("requests", {}).get("cpu"),
                cpu_limit=resources.get("limits", {}).get("cpu"),
                memory_request=resources.get("requests", {}).get("memory"),
                memory_limit=resources.get("limits", {}).get("memory"),
                pod_ip=status.get("podIP"),
                node_name=spec.get("nodeName"),
                restart_count=restart_count,
                raw_data=raw_data,
            )
        except Exception as e:
            logger.error(f"Fast K8s Pod conversion failed: {str(e)}")
            return None

    # ==================== Azure转换方法 ====================

    def _convert_azure_vm_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """Azure Virtual Machine快速转换"""
        try:
            # 提取标签
            tags = raw_data.get("tags", {})

            # Azure VM状态映射
            state_mapping = {
                "PowerState/running": ResourceState.RUNNING,
                "PowerState/stopped": ResourceState.STOPPED,
                "PowerState/deallocated": ResourceState.STOPPED,
                "PowerState/starting": ResourceState.PENDING,
                "PowerState/stopping": ResourceState.TERMINATING,
            }

            # 从实例视图获取电源状态
            power_state = "unknown"
            if "instanceView" in raw_data:
                statuses = raw_data.get("instanceView", {}).get("statuses", [])
                for status in statuses:
                    if status.get("code", "").startswith("PowerState/"):
                        power_state = status.get("code")
                        break

            # 从ID提取资源组和区域
            vm_id = raw_data.get("id", "")
            location = raw_data.get("location", "")

            return ComputeResource(
                resource_id=raw_data.get("vmId") or vm_id,
                resource_name=raw_data.get("name"),
                resource_type=ResourceType.VM_AZURE,
                cloud_provider="azure",
                state=state_mapping.get(power_state, ResourceState.UNKNOWN),
                created_at=None,  # Azure不在基本响应中提供创建时间
                region=location,
                tags=tags,
                instance_type=raw_data.get("hardwareProfile", {}).get("vmSize"),
                private_ip=raw_data.get("networkProfile", {}).get("networkInterfaces", [{}])[0].get("privateIPAddress") if raw_data.get("networkProfile", {}).get("networkInterfaces") else None,
                vpc_id=raw_data.get("networkProfile", {}).get("networkInterfaces", [{}])[0].get("properties", {}).get("virtualNetwork", {}).get("id") if raw_data.get("networkProfile", {}).get("networkInterfaces") else None,
                raw_data=raw_data,
            )
        except Exception as e:
            logger.error(f"Fast Azure VM conversion failed: {str(e)}")
            return None

    def _convert_azure_metric_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """Azure Monitor Metric快速转换"""
        try:
            datapoints = []

            # Azure返回格式: {"value": [{"timeseries": [{"data": [...]}]}]}
            for metric_value in raw_data.get("value", []):
                timeseries_list = metric_value.get("timeseries", [])
                for timeseries in timeseries_list:
                    for dp in timeseries.get("data", []):
                        if "timeStamp" in dp:
                            value = dp.get("average") or dp.get("total") or dp.get("maximum") or dp.get("minimum", 0)
                            datapoints.append(
                                MetricDataPoint(
                                    timestamp=datetime.fromisoformat(dp["timeStamp"].replace("Z", "+00:00")),
                                    value=value,
                                    unit=MetricUnit.NONE,  # Azure使用不同的单位系统
                                    statistic=StatisticType.AVERAGE,
                                )
                            )

            datapoints.sort(key=lambda x: x.timestamp)

            # 提取指标名称
            metric_name = ""
            if raw_data.get("value"):
                metric_name = raw_data["value"][0].get("name", {}).get("value", "")

            return MetricResult(
                metric_namespace=raw_data.get("namespace", ""),
                metric_name=metric_name,
                dimensions={},
                datapoints=datapoints,
                unit=MetricUnit.NONE,
                cloud_provider="azure",
                raw_data=raw_data,
            )
        except Exception as e:
            logger.error(f"Fast Azure Metric conversion failed: {str(e)}")
            return None

    def _convert_azure_traces_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """Azure Application Insights Traces快速转换"""
        try:
            from schemas.health_schema import TraceHealth

            # Azure App Insights返回格式: {"tables": [{"rows": [...]}]}
            total_traces = 0
            error_traces = 0
            durations = []

            for table in raw_data.get("tables", []):
                if table.get("name") == "traces":
                    rows = table.get("rows", [])
                    total_traces = len(rows)

                    for row in rows:
                        # 假设列顺序：timestamp, duration, success, ...
                        duration_ms = row[1] if len(row) > 1 else 0
                        is_success = row[2] if len(row) > 2 else True

                        durations.append(duration_ms)
                        if not is_success:
                            error_traces += 1

            durations.sort()
            n = len(durations)

            avg_duration = sum(durations) / n if n > 0 else 0
            p50 = durations[int(n * 0.5)] if n > 0 else 0
            p95 = durations[int(n * 0.95)] if n > 0 else 0
            p99 = durations[int(n * 0.99)] if n > 0 else 0

            error_rate = error_traces / total_traces if total_traces > 0 else 0
            is_healthy = error_rate < 0.01 and p95 < 1000
            health_score = max(0, 100 - (error_rate * 1000) - (p95 / 100))

            return TraceHealth(
                service_name=raw_data.get("service_name", "unknown"),
                time_range={
                    "start": raw_data.get("start_time", datetime.utcnow()),
                    "end": raw_data.get("end_time", datetime.utcnow())
                },
                total_traces=total_traces,
                error_traces=error_traces,
                error_rate=error_rate,
                avg_duration_ms=avg_duration,
                p50_duration_ms=p50,
                p95_duration_ms=p95,
                p99_duration_ms=p99,
                is_healthy=is_healthy,
                health_score=health_score,
                raw_data=raw_data,
                cloud_provider="azure",
            )
        except Exception as e:
            logger.error(f"Fast Azure Traces conversion failed: {str(e)}")
            return None

    # ==================== GCP转换方法 ====================

    def _convert_gcp_gce_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """GCP Compute Engine快速转换"""
        try:
            # 提取标签
            tags = raw_data.get("labels", {})

            # GCP状态映射
            state_mapping = {
                "RUNNING": ResourceState.RUNNING,
                "STOPPED": ResourceState.STOPPED,
                "PROVISIONING": ResourceState.PENDING,
                "STAGING": ResourceState.PENDING,
                "STOPPING": ResourceState.TERMINATING,
                "TERMINATED": ResourceState.TERMINATED,
            }

            # 提取zone（从URL中）
            zone_url = raw_data.get("zone", "")
            zone = zone_url.split("/")[-1] if zone_url else ""
            region = "-".join(zone.split("-")[:2]) if zone else ""

            # 提取网络接口
            network_interfaces = raw_data.get("networkInterfaces", [])
            private_ip = network_interfaces[0].get("networkIP") if network_interfaces else None
            public_ip = None
            if network_interfaces and network_interfaces[0].get("accessConfigs"):
                public_ip = network_interfaces[0]["accessConfigs"][0].get("natIP")

            # 提取机器类型
            machine_type_url = raw_data.get("machineType", "")
            machine_type = machine_type_url.split("/")[-1] if machine_type_url else ""

            return ComputeResource(
                resource_id=str(raw_data.get("id")),
                resource_name=raw_data.get("name"),
                resource_type=ResourceType.GCE,
                cloud_provider="gcp",
                state=state_mapping.get(raw_data.get("status"), ResourceState.UNKNOWN),
                created_at=datetime.fromisoformat(raw_data["creationTimestamp"].replace("Z", "+00:00")) if "creationTimestamp" in raw_data else None,
                region=region,
                availability_zone=zone,
                tags=tags,
                instance_type=machine_type,
                private_ip=private_ip,
                public_ip=public_ip,
                raw_data=raw_data,
            )
        except Exception as e:
            logger.error(f"Fast GCP GCE conversion failed: {str(e)}")
            return None

    def _convert_gcp_metric_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """GCP Cloud Monitoring Metric快速转换"""
        try:
            datapoints = []

            # GCP返回格式: {"timeSeries": [{"points": [...]}]}
            for ts in raw_data.get("timeSeries", []):
                for point in ts.get("points", []):
                    interval = point.get("interval", {})
                    value_data = point.get("value", {})

                    # 提取值（可能是doubleValue, int64Value等）
                    value = (
                        value_data.get("doubleValue") or
                        value_data.get("int64Value") or
                        value_data.get("distributionValue", {}).get("mean") or
                        0
                    )

                    if "endTime" in interval:
                        datapoints.append(
                            MetricDataPoint(
                                timestamp=datetime.fromisoformat(interval["endTime"].replace("Z", "+00:00")),
                                value=float(value),
                                unit=MetricUnit.NONE,
                                statistic=StatisticType.AVERAGE,
                            )
                        )

            datapoints.sort(key=lambda x: x.timestamp)

            # 提取指标类型
            metric_type = ""
            if raw_data.get("timeSeries"):
                metric_type = raw_data["timeSeries"][0].get("metric", {}).get("type", "")

            return MetricResult(
                metric_namespace="",
                metric_name=metric_type,
                dimensions={},
                datapoints=datapoints,
                unit=MetricUnit.NONE,
                cloud_provider="gcp",
                raw_data=raw_data,
            )
        except Exception as e:
            logger.error(f"Fast GCP Metric conversion failed: {str(e)}")
            return None

    def _convert_gcp_trace_fast(self, raw_data: Dict[str, Any], target_schema: str) -> Optional[Any]:
        """GCP Cloud Trace快速转换"""
        try:
            from schemas.health_schema import TraceHealth

            # GCP返回格式: {"spans": [...]}
            spans = raw_data.get("spans", [])
            total_traces = len(spans)
            error_traces = 0
            durations = []

            for span in spans:
                # 计算持续时间
                start_time = span.get("startTime")
                end_time = span.get("endTime")

                if start_time and end_time:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    duration_ms = (end_dt - start_dt).total_seconds() * 1000
                    durations.append(duration_ms)

                # 检查错误
                if span.get("status", {}).get("code", 0) != 0:
                    error_traces += 1

            durations.sort()
            n = len(durations)

            avg_duration = sum(durations) / n if n > 0 else 0
            p50 = durations[int(n * 0.5)] if n > 0 else 0
            p95 = durations[int(n * 0.95)] if n > 0 else 0
            p99 = durations[int(n * 0.99)] if n > 0 else 0

            error_rate = error_traces / total_traces if total_traces > 0 else 0
            is_healthy = error_rate < 0.01 and p95 < 1000
            health_score = max(0, 100 - (error_rate * 1000) - (p95 / 100))

            return TraceHealth(
                service_name=raw_data.get("service_name", "unknown"),
                time_range={
                    "start": raw_data.get("start_time", datetime.utcnow()),
                    "end": raw_data.get("end_time", datetime.utcnow())
                },
                total_traces=total_traces,
                error_traces=error_traces,
                error_rate=error_rate,
                avg_duration_ms=avg_duration,
                p50_duration_ms=p50,
                p95_duration_ms=p95,
                p99_duration_ms=p99,
                is_healthy=is_healthy,
                health_score=health_score,
                raw_data=raw_data,
                cloud_provider="gcp",
            )
        except Exception as e:
            logger.error(f"Fast GCP Trace conversion failed: {str(e)}")
            return None

    # ==================== 辅助方法 ====================

    def _get_schema_definition(self, schema_name: str) -> str:
        """获取Schema定义（用于LLM理解）"""
        schema_definitions = {
            "ComputeResource": """
ComputeResource Schema:
- resource_id: str (必需，资源唯一ID)
- resource_name: str (可选，资源名称)
- resource_type: ResourceType枚举 (ec2/ecs/cvm等)
- cloud_provider: str (aws/aliyun/tencent/huawei/volc)
- state: ResourceState枚举 (running/stopped/pending/terminating/terminated/error/unknown)
- created_at: datetime (创建时间，ISO格式)
- region: str (区域)
- availability_zone: str (可用区)
- tags: dict (标签键值对)
- instance_type: str (实例类型)
- private_ip: str (内网IP)
- public_ip: str (公网IP)
- vpc_id: str (VPC ID)
- subnet_id: str (子网ID)
- raw_data: dict (原始数据)
""",
            "ContainerResource": """
ContainerResource Schema:
- resource_id: str (必需，格式：namespace/name)
- resource_name: str
- resource_type: ResourceType.POD
- cloud_provider: str
- state: ResourceState枚举
- created_at: datetime
- tags: dict (来自labels)
- namespace: str
- container_image: str
- container_count: int
- cpu_request: str
- cpu_limit: str
- memory_request: str
- memory_limit: str
- pod_ip: str
- node_name: str
- restart_count: int
- state_reason: str (状态原因)
- state_message: str (状态消息)
- raw_data: dict
""",
            "MetricResult": """
MetricResult Schema:
- metric_namespace: str
- metric_name: str
- dimensions: dict
- datapoints: list[MetricDataPoint] (每个点包含timestamp, value, unit, statistic)
- unit: MetricUnit枚举 (Percent/Seconds/Bytes/Count等)
- cloud_provider: str
- raw_data: dict
""",
            "TraceHealth": """
TraceHealth Schema:
- service_name: str
- time_range: dict (包含start和end的datetime)
- total_traces: int
- error_traces: int
- error_rate: float (0-1)
- avg_duration_ms: float
- p50_duration_ms: float
- p95_duration_ms: float
- p99_duration_ms: float
- is_healthy: bool
- health_score: float (0-100)
- error_trace_samples: list[dict] (错误样本)
- raw_data: dict
- cloud_provider: str
""",
            "LogHealth": """
LogHealth Schema:
- log_source: str (日志组名称)
- time_range: dict (start/end)
- total_logs: int
- error_count: int
- warning_count: int
- critical_count: int
- error_rate: float (0-1)
- is_healthy: bool
- health_score: float (0-100)
- critical_samples: list[dict] (关键错误样本)
- raw_data: dict
- cloud_provider: str
"""
        }

        return schema_definitions.get(schema_name, f"Schema: {schema_name} (定义未找到)")

    def _instantiate_schema(self, schema_name: str, data: Dict[str, Any]) -> Any:
        """实例化Schema对象"""
        schema_map = {
            "ComputeResource": ComputeResource,
            "ContainerResource": ContainerResource,
            "NetworkResource": NetworkResource,
            "CDNResource": CDNResource,
            "MetricResult": MetricResult,
            "TraceHealth": TraceHealth,
            "LogHealth": LogHealth,
            "MetricHealth": MetricHealth,
            "ResourceHealth": ResourceHealth,
        }

        schema_class = schema_map.get(schema_name)
        if not schema_class:
            raise ValueError(f"Unknown schema: {schema_name}")

        return schema_class(**data)
