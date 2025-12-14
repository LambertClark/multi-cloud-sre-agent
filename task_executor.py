"""
Task Executor - 任务执行引擎
支持DAG编排、并行执行、数据聚合
"""
from typing import Dict, Any, List, Optional, Set
import asyncio
import logging
from dataclasses import dataclass
from collections import defaultdict

from agents.task_planner_agent import TaskStep
from tools.aws_tools import AWSMonitoringTools
from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""
    step_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    api_calls: List[Dict[str, Any]] = None  # 记录该步骤调用的API


class TaskExecutor:
    """
    任务执行引擎

    职责：
    1. 执行DAG任务计划
    2. 管理步骤依赖关系
    3. 并行执行独立任务
    4. 聚合多步骤结果
    5. 处理执行错误
    """

    def __init__(self):
        self.config = get_config()
        self.aws_tools = AWSMonitoringTools()

    async def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务计划

        Args:
            plan: 来自TaskPlannerAgent的执行计划

        Returns:
            执行结果
        """
        try:
            plan_type = plan.get("type", "simple")
            steps = plan.get("steps", [])
            
            result = {}
            if plan_type == "simple":
                # 简单任务：单步执行
                result = await self._execute_simple_plan(steps)
            elif plan_type in ["multi_step", "complex"]:
                # 多步骤任务：DAG执行
                result = await self._execute_dag_plan(steps)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown plan type: {plan_type}"
                }
            
            # 确保返回结果中包含api_trace
            if "api_trace" not in result:
                result["api_trace"] = []
                
            return result

        except Exception as e:
            logger.error(f"Error executing plan: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_simple_plan(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行简单计划（单步）"""
        if not steps:
            return {"success": False, "error": "No steps to execute"}

        step = steps[0]
        result = await self._execute_step(step, {})

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "results": [result],
            "api_trace": result.api_calls or []
        }

    async def _execute_dag_plan(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行DAG计划（多步骤，支持并行）

        算法：
        1. 构建依赖图
        2. 拓扑排序，识别可并行步骤
        3. 按层级执行：同层并行，跨层串行
        4. 聚合结果
        """
        # 构建依赖关系
        step_map = {s["step_id"]: s for s in steps}
        dependencies = {s["step_id"]: set(s.get("dependencies", [])) for s in steps}

        # 执行上下文（存储每个步骤的输出）
        context = {}
        results = []

        # 已完成的步骤
        completed = set()

        while len(completed) < len(steps):
            # 找出所有依赖已满足的步骤
            ready_steps = [
                step_id for step_id, deps in dependencies.items()
                if step_id not in completed and deps.issubset(completed)
            ]

            if not ready_steps:
                # 没有可执行的步骤，可能存在循环依赖
                return {
                    "success": False,
                    "error": "Circular dependency or no ready steps",
                    "completed": list(completed),
                    "remaining": list(set(step_map.keys()) - completed)
                }

            # 并行执行所有ready步骤
            tasks = [
                self._execute_step(step_map[step_id], context)
                for step_id in ready_steps
            ]

            step_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            for step_id, result in zip(ready_steps, step_results):
                if isinstance(result, Exception):
                    logger.error(f"Step {step_id} failed with exception: {result}")
                    result = ExecutionResult(
                        step_id=step_id,
                        success=False,
                        error=str(result)
                    )

                results.append(result)
                completed.add(step_id)

                # 将结果存入上下文
                if result.success and result.data:
                    output_key = step_map[step_id].get("output_key", step_id)
                    context[output_key] = result.data

        # 聚合最终结果
        final_data = self._aggregate_results(results, context)

        # 收集所有步骤的API调用
        api_trace = []
        for r in results:
            if r.api_calls:
                api_trace.extend(r.api_calls)

        return {
            "success": all(r.success for r in results),
            "data": final_data,
            "results": results,
            "context": context,
            "api_trace": api_trace
        }

    async def _execute_step(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ExecutionResult:
        """
        执行单个步骤

        Args:
            step: 步骤定义
            context: 执行上下文（包含前置步骤的输出）
        """
        import time
        start_time = time.time()

        try:
            step_id = step.get("step_id")
            step_type = step.get("step_type")
            operation = step.get("operation")
            parameters = step.get("parameters", {})

            logger.info(f"Executing step {step_id}: {step_type} - {operation}")

            # 根据步骤类型执行
            if step_type == "list_resources":
                data = await self._execute_list_resources(parameters, context)
            elif step_type == "query_metric":
                data = await self._execute_query_metric(parameters, context)
            elif step_type == "query_log":
                data = await self._execute_query_log(parameters, context)
            elif step_type == "query_trace":
                data = await self._execute_query_trace(parameters, context)
            elif step_type == "filter":
                data = await self._execute_filter(parameters, context)
            elif step_type == "aggregate":
                data = await self._execute_aggregate(parameters, context)
            elif step_type == "analyze":
                data = await self._execute_analyze(parameters, context)
            elif step_type == "format":
                data = await self._execute_format(parameters, context)
            else:
                return ExecutionResult(
                    step_id=step_id,
                    success=False,
                    error=f"Unknown step type: {step_type}"
                )

            execution_time = time.time() - start_time
            
            # 提取API调用记录
            api_calls = []
            if isinstance(data, dict) and "api_calls" in data:
                api_calls = data.pop("api_calls")

            return ExecutionResult(
                step_id=step_id,
                success=True,
                data=data,
                execution_time=execution_time,
                api_calls=api_calls
            )

        except Exception as e:
            logger.error(f"Error executing step {step.get('step_id')}: {str(e)}")
            execution_time = time.time() - start_time

            return ExecutionResult(
                step_id=step.get("step_id"),
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    async def _execute_list_resources(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """列出资源"""
        resource_type = parameters.get("resource_type", "ec2")
        tags = parameters.get("tags", {})

        if resource_type == "ec2":
            # 使用AWS工具列出EC2实例
            result = await self.aws_tools._list_ec2_instances_impl(tags=tags)
            
            # 记录API调用
            from datetime import datetime
            if isinstance(result, dict):
                result["api_calls"] = [{
                    "timestamp": datetime.now().isoformat(),
                    "type": "task_execution",
                    "cloud_provider": "aws",
                    "service": "ec2",
                    "operation": "describe_instances",
                    "parameters": tags
                }]
            return result

        return {"success": False, "error": f"Unsupported resource type: {resource_type}"}

    async def _execute_query_metric(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """查询指标（支持批量）"""
        metric_name = parameters.get("metric_name", "CPUUtilization")
        namespace = parameters.get("namespace", "AWS/EC2")

        # 从上下文获取资源列表
        resources = context.get("resources", {}).get("instances", [])

        if not resources:
            return {"success": False, "error": "No resources to query metrics"}

        # 并行查询所有实例的指标
        tasks = []
        api_calls = []
        from datetime import datetime
        
        for instance in resources:
            instance_id = instance.get("InstanceId")
            tasks.append(
                self.aws_tools._get_metric_statistics_impl(
                    namespace=namespace,
                    metric_name=metric_name,
                    dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    period=parameters.get("period", 300),
                    statistics=parameters.get("statistics", ["Average"]),
                    start_time=parameters.get("start_time"),
                    end_time=parameters.get("end_time")
                )
            )
            # 记录每个API调用
            api_calls.append({
                "timestamp": datetime.now().isoformat(),
                "type": "task_execution",
                "cloud_provider": "aws",
                "service": "cloudwatch",
                "operation": "get_metric_statistics",
                "parameters": {
                    "namespace": namespace,
                    "metric_name": metric_name,
                    "instance_id": instance_id
                }
            })

        results = await asyncio.gather(*tasks)

        # 组合结果：instance_id -> metric_data
        metrics = {}
        for instance, result in zip(resources, results):
            instance_id = instance.get("InstanceId")
            metrics[instance_id] = {
                "instance": instance,
                "metric_data": result.get("datapoints", []) if result.get("success") else []
            }

        return {
            "success": True,
            "metrics": metrics,
            "api_calls": api_calls
        }

    async def _execute_query_log(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """查询日志"""
        log_group = parameters.get("log_group")
        query = parameters.get("query", "")

        result = await self.aws_tools._query_logs_impl(
            log_group=log_group,
            query_string=query,
            start_time=parameters.get("start_time"),
            end_time=parameters.get("end_time")
        )

        return result

    async def _execute_query_trace(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """查询追踪"""
        filter_expression = parameters.get("filter_expression")

        result = await self.aws_tools._get_trace_summaries_impl(
            filter_expression=filter_expression,
            start_time=parameters.get("start_time"),
            end_time=parameters.get("end_time")
        )

        return result

    async def _execute_filter(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        过滤数据

        支持条件：
        - threshold: 阈值过滤（如CPU > 80）
        - status: 状态过滤
        - custom: 自定义过滤函数
        """
        filter_type = parameters.get("filter_type", "threshold")

        # 从上下文获取要过滤的数据
        source_key = parameters.get("source_key", "metrics")
        source_data = context.get(source_key, {})

        if filter_type == "threshold":
            # 阈值过滤
            threshold = parameters.get("threshold", 80)
            operator = parameters.get("operator", ">")

            filtered = {}
            metrics_data = source_data.get("metrics", {})

            for instance_id, data in metrics_data.items():
                metric_values = data.get("metric_data", [])
                if not metric_values:
                    continue

                # 取最新值或平均值
                latest_value = metric_values[-1].get("Average", 0) if metric_values else 0

                # 应用过滤条件
                if self._apply_operator(latest_value, operator, threshold):
                    filtered[instance_id] = data

            return {
                "success": True,
                "filtered_results": filtered,
                "total_count": len(metrics_data),
                "filtered_count": len(filtered)
            }

        return {"success": False, "error": f"Unsupported filter type: {filter_type}"}

    def _apply_operator(self, value: float, operator: str, threshold: float) -> bool:
        """应用比较运算符"""
        if operator == ">":
            return value > threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<":
            return value < threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        return False

    async def _execute_aggregate(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """聚合数据"""
        agg_type = parameters.get("agg_type", "summary")

        # 简单实现：统计摘要
        source_key = parameters.get("source_key", "filtered_results")
        source_data = context.get(source_key, {})

        return {
            "success": True,
            "aggregated": source_data,
            "summary": {
                "count": len(source_data.get("filtered_results", {}))
            }
        }

    async def _execute_analyze(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """智能分析（预留接口）"""
        # TODO: 实现LLM分析
        analysis_type = parameters.get("analysis_type", "health_check")

        return {
            "success": True,
            "analysis": {
                "type": analysis_type,
                "message": "Analysis not yet implemented"
            }
        }

    async def _execute_format(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """格式化输出"""
        format_type = parameters.get("format_type", "json")
        source_key = parameters.get("source_key", "filtered_results")

        data = context.get(source_key, {})

        return {
            "success": True,
            "formatted": data
        }

    def _aggregate_results(
        self,
        results: List[ExecutionResult],
        context: Dict[str, Any]
    ) -> Any:
        """聚合所有步骤的结果"""
        # 返回最后一个成功步骤的数据，或者整个上下文
        for result in reversed(results):
            if result.success and result.data:
                return result.data

        return context


# 全局实例
_task_executor: Optional[TaskExecutor] = None


def get_task_executor() -> TaskExecutor:
    """获取全局任务执行器实例"""
    global _task_executor
    if _task_executor is None:
        _task_executor = TaskExecutor()
    return _task_executor
