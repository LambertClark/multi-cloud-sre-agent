"""
任务规划Agent - 将复杂查询分解为多步骤执行计划
支持多资源聚合、条件过滤、智能分析
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import get_config
from .base_agent import BaseAgent, AgentResponse

logger = logging.getLogger(__name__)


@dataclass
class TaskStep:
    """任务步骤"""
    step_id: str
    step_type: str  # api_call, aggregate, filter, analyze, code_gen
    description: str
    operation: str
    parameters: Dict[str, Any]
    dependencies: List[str] = None  # 依赖的前置步骤ID
    output_key: str = None  # 输出结果的key


class TaskPlannerAgent(BaseAgent):
    """
    任务规划Agent

    职责：
    1. 分析复杂查询需求
    2. 识别是否需要多步骤编排
    3. 生成执行计划（DAG）
    4. 识别需要的数据源（metric/log/trace）
    5. 确定聚合、过滤、分析策略
    """

    def __init__(self):
        super().__init__("TaskPlannerAgent")
        self.config = get_config()
        self.llm = ChatOpenAI(
            model=self.config.llm.model,
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.base_url,
            temperature=0.3  # 较低温度，保证规划稳定性
        )

    def get_capabilities(self) -> List[str]:
        return [
            "multi_step_planning",
            "task_decomposition",
            "dependency_analysis",
            "data_source_identification",
            "aggregation_strategy"
        ]

    def can_handle(self, input_data: Dict[str, Any]) -> bool:
        return "query" in input_data or "user_request" in input_data

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        处理任务规划请求

        Args:
            input_data: {
                "query": "列出全部CPU利用率超过80%的服务器",
                "context": {...}  # 可选的上下文信息
            }

        Returns:
            AgentResponse包含执行计划
        """
        try:
            query = input_data.get("query") or input_data.get("user_request", "")
            context = input_data.get("context", {})

            # 分析查询复杂度
            complexity = await self._analyze_complexity(query)

            # 根据复杂度决定规划策略
            if complexity["level"] == "simple":
                # 简单查询：单步骤
                plan = await self._plan_simple_task(query, context)
            elif complexity["level"] == "moderate":
                # 中等复杂度：多步骤但无分析
                plan = await self._plan_multi_step_task(query, context, complexity)
            else:
                # 高复杂度：需要智能分析
                plan = await self._plan_complex_task(query, context, complexity)

            return AgentResponse(
                success=True,
                data={
                    "plan": plan,
                    "complexity": complexity,
                    "estimated_steps": len(plan.get("steps", []))
                },
                metadata={
                    "planner": "TaskPlannerAgent",
                    "query": query
                }
            )

        except Exception as e:
            logger.error(f"Error in TaskPlannerAgent.process: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e)
            )

    async def _analyze_complexity(self, query: str) -> Dict[str, Any]:
        """
        分析查询复杂度

        Returns:
            {
                "level": "simple" | "moderate" | "complex",
                "requires_aggregation": bool,
                "requires_filtering": bool,
                "requires_analysis": bool,
                "requires_tags": bool,
                "data_sources": ["metric", "log", "trace"],
                "features": [...]
            }
        """
        system_prompt = """你是一个云服务查询分析专家。分析用户查询的复杂度和特征。

复杂度等级：
- simple: 单一资源查询，无聚合过滤（如"查询服务器A的CPU使用率"）
- moderate: 多资源聚合，有条件过滤（如"列出CPU>80%的服务器"）
- complex: 需要智能分析、根因定位、优化建议（如"分析异常根本原因"）

特征识别：
- requires_aggregation: 需要聚合多个资源数据
- requires_filtering: 需要基于条件过滤
- requires_analysis: 需要LLM智能分析
- requires_tags: 需要使用标签/业务标识
- data_sources: 需要的数据源（metric/log/trace）

以JSON格式返回分析结果。"""

        user_prompt = f"""分析以下查询：

查询: {query}

返回JSON格式的复杂度分析。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await self.llm.ainvoke(messages)

        # 解析LLM返回的JSON
        import json
        try:
            # 提取JSON（可能包含在代码块中）
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            complexity = json.loads(content)
            return complexity
        except:
            # 默认复杂度
            logger.warning("Failed to parse complexity analysis, using default")
            return {
                "level": "moderate",
                "requires_aggregation": True,
                "requires_filtering": True,
                "requires_analysis": False,
                "requires_tags": False,
                "data_sources": ["metric"]
            }

    async def _plan_simple_task(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """规划简单任务（单步骤）"""
        return {
            "type": "simple",
            "steps": [{
                "step_id": "step_1",
                "step_type": "api_call",
                "description": query,
                "operation": "query",
                "parameters": {},
                "dependencies": [],
                "output_key": "result"
            }],
            "execution_mode": "sequential"
        }

    async def _plan_multi_step_task(
        self,
        query: str,
        context: Dict[str, Any],
        complexity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        规划多步骤任务

        典型场景：
        1. 列出CPU>80%的服务器
           Step 1: 获取所有服务器列表（可能带Tag过滤）
           Step 2: 并行查询每台服务器的CPU指标
           Step 3: 过滤CPU>80%的结果
           Step 4: 格式化输出
        """
        system_prompt = """你是云服务任务规划专家。将查询分解为多个步骤。

步骤类型：
- list_resources: 列出资源（支持Tag过滤）
- query_metric: 查询指标
- query_log: 查询日志
- query_trace: 查询追踪
- filter: 过滤数据
- aggregate: 聚合数据
- format: 格式化输出

返回JSON格式的执行计划，包含steps数组。每个step包含：
- step_id: 步骤ID
- step_type: 步骤类型
- description: 步骤描述
- operation: 具体操作
- parameters: 参数
- dependencies: 依赖的前置步骤ID列表
- output_key: 输出结果的key"""

        user_prompt = f"""规划以下查询的执行步骤：

查询: {query}

复杂度分析: {complexity}

返回JSON格式的执行计划。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await self.llm.ainvoke(messages)

        import json
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            plan = json.loads(content)
            plan["type"] = "multi_step"
            plan["execution_mode"] = "dag"  # DAG执行
            return plan
        except Exception as e:
            logger.error(f"Failed to parse task plan: {e}")
            # 返回默认计划
            return self._create_default_multi_step_plan(query, complexity)

    async def _plan_complex_task(
        self,
        query: str,
        context: Dict[str, Any],
        complexity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        规划复杂任务（需要智能分析）

        典型场景：
        1. 分析应用异常根本原因
           Step 1: 获取应用的Trace数据
           Step 2: 获取相关的Log数据
           Step 3: 获取Metric数据
           Step 4: LLM分析根因
           Step 5: 生成诊断报告
        """
        # 类似multi_step，但增加analyze步骤
        plan = await self._plan_multi_step_task(query, context, complexity)

        # 确保有analyze步骤
        has_analyze = any(s.get("step_type") == "analyze" for s in plan.get("steps", []))

        if not has_analyze and complexity.get("requires_analysis"):
            # 添加分析步骤
            plan["steps"].append({
                "step_id": f"step_{len(plan['steps']) + 1}",
                "step_type": "analyze",
                "description": "智能分析数据并生成诊断报告",
                "operation": "llm_analyze",
                "parameters": {
                    "analysis_type": "root_cause" if "根因" in query or "原因" in query else "health_check"
                },
                "dependencies": [s["step_id"] for s in plan.get("steps", [])],
                "output_key": "analysis_result"
            })

        plan["type"] = "complex"
        return plan

    def _create_default_multi_step_plan(
        self,
        query: str,
        complexity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建默认的多步骤计划"""
        steps = []

        # Step 1: 列出资源
        steps.append({
            "step_id": "step_1",
            "step_type": "list_resources",
            "description": "获取资源列表",
            "operation": "list",
            "parameters": {},
            "dependencies": [],
            "output_key": "resources"
        })

        # Step 2: 查询指标
        if "metric" in complexity.get("data_sources", []):
            steps.append({
                "step_id": "step_2",
                "step_type": "query_metric",
                "description": "查询指标数据",
                "operation": "get_metrics",
                "parameters": {},
                "dependencies": ["step_1"],
                "output_key": "metrics"
            })

        # Step 3: 过滤
        if complexity.get("requires_filtering"):
            steps.append({
                "step_id": "step_3",
                "step_type": "filter",
                "description": "过滤数据",
                "operation": "filter",
                "parameters": {},
                "dependencies": ["step_2"],
                "output_key": "filtered_results"
            })

        return {
            "type": "multi_step",
            "steps": steps,
            "execution_mode": "dag"
        }


# 全局实例
_task_planner: Optional[TaskPlannerAgent] = None


def get_task_planner() -> TaskPlannerAgent:
    """获取全局任务规划Agent实例"""
    global _task_planner
    if _task_planner is None:
        _task_planner = TaskPlannerAgent()
    return _task_planner
