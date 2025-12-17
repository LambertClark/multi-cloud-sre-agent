"""
Manager Agent - 任务编排和流程控制
负责解析用户请求、拆解任务、协调各子Agent
支持ReAct模式：动态推理、自适应调整
"""
from typing import Dict, Any, List, Optional
from enum import Enum
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
import logging
import asyncio

from .base_agent import BaseAgent, AgentResponse
from .code_generator_agent import CodeGeneratorAgent
from .data_adapter_agent import DataAdapterAgent
from config import get_config

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Action类型"""
    GENERATE_CODE = "generate_code"          # 生成代码
    ADAPT_DATA = "adapt_data"                # 转换数据
    ANALYZE = "analyze"                      # LLM分析
    FINISH = "finish"                        # 完成任务


class ManagerAgent(BaseAgent):
    """
    Manager Agent负责：
    1. 解析用户请求意图（查询监控、配置告警、分析日志等）
    2. 识别目标云平台和服务
    3. 判断是否需要拉取文档或使用现有API
    4. 协调各个子Agent的工作流程
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("ManagerAgent", config)
        self.config_obj = get_config()
        self.llm = self._init_llm()
        self.available_tools = []
        self.registered_apis = {}  # 已注册的云服务API

        # 注册子Agent
        self.sub_agents = {
            "code_generator": CodeGeneratorAgent(),
            "data_adapter": DataAdapterAgent()
        }

        self.max_react_iterations = 8  # ReAct最大迭代次数

    def _init_llm(self) -> ChatOpenAI:
        """初始化LLM"""
        llm_config = self.config_obj.llm
        return ChatOpenAI(
            model=llm_config.model,
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens
        )

    def register_tool(self, tool_func):
        """注册工具"""
        self.available_tools.append(tool_func)
        logger.info(f"Registered tool: {tool_func.name}")

    def register_api(self, cloud_provider: str, service: str, operations: List[str]):
        """
        注册已有的云服务API

        Args:
            cloud_provider: 云平台名称 (aws, azure, gcp, aliyun, volc)
            service: 服务名称 (cloudwatch, monitor, etc)
            operations: 支持的操作列表
        """
        key = f"{cloud_provider}.{service}"
        if key not in self.registered_apis:
            self.registered_apis[key] = []
        self.registered_apis[key].extend(operations)
        logger.info(f"Registered API: {key} with operations: {operations}")

    def get_capabilities(self) -> List[str]:
        """获取Agent能力"""
        return [
            "意图识别和任务规划",
            "云平台和服务识别",
            "可观测性任务编排",
            "动态API调用决策",
            "工作流程协调"
        ]

    def validate_input(self, input_data: Any) -> bool:
        """验证输入"""
        if not isinstance(input_data, dict):
            return False
        return "query" in input_data or "task" in input_data

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        处理用户请求

        Args:
            input_data: {
                "query": "用户查询",
                "context": {...},  # 可选上下文
                "preferences": {...}  # 可选偏好设置
            }

        Returns:
            AgentResponse包含任务规划结果
        """
        try:
            query = input_data.get("query") or input_data.get("task")
            context = input_data.get("context", {})

            # 第一步：意图识别和任务拆解
            intent_result = await self._analyze_intent(query, context)

            if not intent_result["success"]:
                return AgentResponse(
                    success=False,
                    error=f"Intent analysis failed: {intent_result.get('error')}"
                )

            # 第二步：判断是否需要使用现有API
            execution_plan = await self._create_execution_plan(intent_result)

            return AgentResponse(
                success=True,
                data={
                    "intent": intent_result,
                    "execution_plan": execution_plan,
                    "query": query
                },
                metadata={
                    "requires_spec_fetch": execution_plan.get("requires_spec_fetch", False),
                    "cloud_provider": intent_result.get("cloud_provider"),
                    "service": intent_result.get("service")
                }
            )

        except Exception as e:
            logger.error(f"Error in ManagerAgent.process: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e)
            )

    async def _analyze_intent(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析用户意图

        识别：
        - 云平台（AWS, Azure, GCP, 阿里云, 火山云）
        - 服务类型（监控、日志、追踪、告警）
        - 操作类型（查询、配置、分析、导出）
        - 具体参数
        """
        system_prompt = """你是一个多云SRE助手的意图分析模块。
你需要分析用户的请求，识别以下信息：

1. **云平台** (cloud_provider): aws, azure, gcp, aliyun, volc
2. **服务类型** (service_type): monitoring, logging, tracing, alerting
3. **具体服务** (service): 如cloudwatch, monitor, cloud_monitoring等
4. **操作类型** (operation_type):
   - query: 查询数据
   - configure: 配置设置
   - analyze: 分析统计
   - export: 导出数据
   - create: 创建资源
   - delete: 删除资源
   - update: 更新资源
5. **具体操作** (operation): 如get_metrics, set_alarm, query_logs等
6. **参数** (parameters): 操作所需的参数

请以JSON格式返回分析结果。

示例：
用户："查询AWS EC2实例的CPU使用率"
返回：
{
  "cloud_provider": "aws",
  "service_type": "monitoring",
  "service": "cloudwatch",
  "operation_type": "query",
  "operation": "get_metric_statistics",
  "parameters": {
    "namespace": "AWS/EC2",
    "metric_name": "CPUUtilization"
  },
  "confidence": 0.95
}
"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"用户请求：{query}\n\n上下文：{json.dumps(context, ensure_ascii=False)}")
            ]

            response = await self.llm.ainvoke(messages)

            # 解析LLM响应
            content = response.content.strip()

            # 尝试提取JSON
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            result = json.loads(content)
            result["success"] = True

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {
                "success": False,
                "error": f"Failed to parse intent: {str(e)}",
                "raw_response": content
            }
        except Exception as e:
            logger.error(f"Error in intent analysis: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _create_execution_plan(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建执行计划

        判断：
        1. 是否有现成的API工具可用
        2. 如果没有，是否需要拉取Spec文档
        3. 制定具体的执行步骤
        """
        cloud_provider = intent.get("cloud_provider")
        service = intent.get("service")
        operation = intent.get("operation")

        # 检查是否有已注册的API
        api_key = f"{cloud_provider}.{service}"
        has_api = api_key in self.registered_apis and operation in self.registered_apis[api_key]

        plan = {
            "has_existing_api": has_api,
            "requires_spec_fetch": not has_api,
            "steps": []
        }

        if has_api:
            # 使用现有API
            plan["steps"] = [
                {
                    "step": 1,
                    "action": "call_api",
                    "tool": api_key,
                    "operation": operation,
                    "parameters": intent.get("parameters", {})
                }
            ]
        else:
            # 需要动态生成
            plan["steps"] = [
                {
                    "step": 1,
                    "action": "fetch_spec",
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "description": "拉取API规格文档"
                },
                {
                    "step": 2,
                    "action": "index_spec",
                    "description": "将规格文档索引到RAG系统"
                },
                {
                    "step": 3,
                    "action": "generate_code",
                    "operation": operation,
                    "parameters": intent.get("parameters", {}),
                    "description": "生成API调用代码"
                },
                {
                    "step": 4,
                    "action": "test_code",
                    "description": "在WASM沙箱中测试代码"
                },
                {
                    "step": 5,
                    "action": "execute_code",
                    "description": "执行生成的代码"
                }
            ]

        # 添加元数据
        plan["metadata"] = {
            "cloud_provider": cloud_provider,
            "service": service,
            "operation": operation,
            "estimated_steps": len(plan["steps"])
        }

        return plan

    async def execute_plan(
        self,
        plan: Dict[str, Any],
        spec_doc_agent=None,
        rag_system=None,
        code_gen_agent=None,
        wasm_sandbox=None,
        cloud_tools=None
    ) -> AgentResponse:
        """
        执行计划

        Args:
            plan: 执行计划
            spec_doc_agent: 规格文档拉取Agent
            rag_system: RAG系统
            code_gen_agent: 代码生成Agent
            wasm_sandbox: WASM沙箱
            cloud_tools: 云服务工具集

        Returns:
            执行结果
        """
        try:
            results = []

            for step in plan["steps"]:
                action = step["action"]

                if action == "call_api":
                    # 调用现有API
                    if cloud_tools is None:
                        return AgentResponse(
                            success=False,
                            error="Cloud tools not available"
                        )

                    result = await cloud_tools.call(
                        step["tool"],
                        step["operation"],
                        step["parameters"]
                    )
                    results.append({"step": step["step"], "result": result})

                elif action == "fetch_spec":
                    # 拉取规格文档
                    if spec_doc_agent is None:
                        return AgentResponse(
                            success=False,
                            error="SpecDoc agent not available"
                        )

                    spec_response = await spec_doc_agent.safe_process({
                        "cloud_provider": step["cloud_provider"],
                        "service": step["service"]
                    })

                    if not spec_response.success:
                        return spec_response

                    results.append({
                        "step": step["step"],
                        "result": spec_response.data
                    })

                elif action == "index_spec":
                    # 索引到RAG
                    if rag_system is None:
                        return AgentResponse(
                            success=False,
                            error="RAG system not available"
                        )

                    # 获取上一步的spec数据
                    spec_data = results[-1]["result"]
                    rag_response = await rag_system.index_documents(spec_data)

                    if not rag_response["success"]:
                        return AgentResponse(
                            success=False,
                            error=f"RAG indexing failed: {rag_response.get('error')}"
                        )

                    results.append({
                        "step": step["step"],
                        "result": rag_response
                    })

                elif action == "generate_code":
                    # 生成代码
                    if code_gen_agent is None:
                        return AgentResponse(
                            success=False,
                            error="Code generation agent not available"
                        )

                    code_response = await code_gen_agent.safe_process({
                        "operation": step["operation"],
                        "parameters": step["parameters"],
                        "context": results
                    })

                    if not code_response.success:
                        return code_response

                    results.append({
                        "step": step["step"],
                        "result": code_response.data
                    })

                elif action == "test_code":
                    # 测试代码
                    if wasm_sandbox is None:
                        return AgentResponse(
                            success=False,
                            error="WASM sandbox not available"
                        )

                    code_data = results[-1]["result"]
                    test_response = await wasm_sandbox.test_code(code_data)

                    if not test_response["success"]:
                        return AgentResponse(
                            success=False,
                            error=f"Code test failed: {test_response.get('error')}"
                        )

                    results.append({
                        "step": step["step"],
                        "result": test_response
                    })

                elif action == "execute_code":
                    # 执行代码
                    code_data = results[-3]["result"]  # 从生成代码步骤获取
                    exec_response = await self._execute_generated_code(code_data)

                    if not exec_response["success"]:
                        return AgentResponse(
                            success=False,
                            error=f"Code execution failed: {exec_response.get('error')}"
                        )

                    results.append({
                        "step": step["step"],
                        "result": exec_response
                    })

            return AgentResponse(
                success=True,
                data={
                    "results": results,
                    "final_result": results[-1]["result"] if results else None
                },
                metadata={
                    "steps_completed": len(results),
                    "plan": plan
                }
            )

        except Exception as e:
            logger.error(f"Error executing plan: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e),
                metadata={"partial_results": results}
            )

    async def _execute_generated_code(self, code_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行生成的代码"""
        # TODO: 实现代码执行逻辑
        # 这里需要根据代码类型（Python/JS等）选择合适的执行方式
        return {
            "success": True,
            "output": "Code execution not implemented yet",
            "code": code_data
        }

    # ============ ReAct模式方法 ============

    async def process_with_react(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        使用ReAct模式处理任务（推荐使用）

        Args:
            input_data: {
                "user_request": "帮我分析电商平台的健康状况",
                "context": {...},
                "max_iterations": 8  # 可选
            }

        Returns:
            AgentResponse with task results
        """
        user_request = input_data.get("user_request") or input_data.get("task") or input_data.get("query")
        context = input_data.get("context", {})
        max_iterations = input_data.get("max_iterations", self.max_react_iterations)

        logger.info(f"ManagerAgent (ReAct) received: {user_request}")

        try:
            result = await self._react_loop(
                user_request=user_request,
                context=context,
                max_iterations=max_iterations
            )
            return result

        except Exception as e:
            logger.error(f"ManagerAgent ReAct failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return AgentResponse(
                success=False,
                error=f"Manager Agent ReAct failed: {str(e)}",
                agent_name=self.name
            )

    async def _react_loop(
        self,
        user_request: str,
        context: Dict[str, Any],
        max_iterations: int
    ) -> AgentResponse:
        """ReAct主循环：Thought → Action → Observation"""
        react_history = []
        accumulated_data = {}

        for iteration in range(1, max_iterations + 1):
            logger.info(f"=== ReAct Iteration {iteration}/{max_iterations} ===")

            # 1. Thought: LLM推理下一步
            thought_result = await self._react_thought(
                user_request=user_request,
                context=context,
                history=react_history,
                accumulated_data=accumulated_data,
                iteration=iteration
            )

            thought = thought_result["thought"]
            action = thought_result["action"]
            is_final = thought_result.get("is_final", False)

            logger.info(f"Thought: {thought[:150]}...")
            logger.info(f"Action: {action['type']}")

            # 2. Action: 执行动作
            observation = await self._execute_action(action, accumulated_data)

            logger.info(f"Observation: {observation.get('status')}")

            # 3. 记录历史
            react_history.append({
                "iteration": iteration,
                "thought": thought,
                "action": action,
                "observation": observation
            })

            # 4. 更新数据
            if observation.get("success"):
                data = observation.get("data", {})
                accumulated_data.update(data)

            # 5. 判断完成
            if is_final or observation.get("task_completed"):
                logger.info(f"✅ Task completed in {iteration} iterations")

                final_report = await self._generate_final_report(
                    user_request, react_history, accumulated_data
                )

                return AgentResponse(
                    success=True,
                    data={
                        "result": final_report,
                        "accumulated_data": accumulated_data,
                        "iterations": iteration,
                        "react_history": react_history
                    },
                    message=f"Task completed in {iteration} iterations",
                    agent_name=self.name
                )

            # 检查失败
            if observation.get("status") == "failed" and not observation.get("can_retry"):
                return AgentResponse(
                    success=False,
                    data={
                        "accumulated_data": accumulated_data,
                        "iterations": iteration,
                        "react_history": react_history
                    },
                    error=observation.get("error"),
                    agent_name=self.name
                )

        # 达到最大迭代
        logger.warning(f"⚠️  Max iterations reached ({max_iterations})")
        return AgentResponse(
            success=False,
            data={
                "accumulated_data": accumulated_data,
                "iterations": max_iterations,
                "react_history": react_history
            },
            error=f"Max iterations ({max_iterations}) reached",
            agent_name=self.name
        )

    async def _react_thought(
        self,
        user_request: str,
        context: Dict,
        history: List[Dict],
        accumulated_data: Dict,
        iteration: int
    ) -> Dict[str, Any]:
        """Thought阶段：LLM推理"""
        system_prompt = """你是Manager Agent，负责任务编排。

**可用子Agent：**
- code_generator: 生成查询/操作代码
- data_adapter: 转换数据格式

**可用Action：**
- generate_code: 生成代码
- adapt_data: 转换数据
- analyze: LLM分析
- finish: 完成任务

**输出JSON格式：**
```json
{
  "thought": "我的推理...",
  "action": {
    "type": "generate_code",
    "target": "code_generator",
    "parameters": {...}
  },
  "is_final": false
}
```

**原则：**
1. 一次只做一件事
2. 先收集数据，再分析
3. 完成时用finish action
"""

        user_prompt = f"""# 用户请求
{user_request}

# 当前迭代
第 {iteration} 次

# 已完成步骤
"""
        if history:
            for step in history[-3:]:  # 只显示最近3步
                user_prompt += f"- {step['action']['type']}: {step['observation'].get('status')}\n"
        else:
            user_prompt += "（尚未开始）\n"

        user_prompt += f"\n# 已收集数据\n{json.dumps(accumulated_data, ensure_ascii=False, indent=2)[:500]}\n\n决定下一步："

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await self._invoke_llm_with_retry(messages)

        return self._parse_thought_response(response.content)

    def _parse_thought_response(self, text: str) -> Dict:
        """解析Thought输出"""
        try:
            import re
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = text.strip()

            result = json.loads(json_str)

            if "thought" not in result or "action" not in result:
                raise ValueError("Missing required fields")

            return result

        except Exception as e:
            logger.error(f"Failed to parse thought: {str(e)}")
            return {
                "thought": f"Parse error: {str(e)}",
                "action": {"type": "analyze", "parameters": {}},
                "is_final": False
            }

    async def _execute_action(
        self,
        action: Dict[str, Any],
        accumulated_data: Dict
    ) -> Dict[str, Any]:
        """执行Action"""
        action_type = action.get("type")

        try:
            if action_type == "generate_code":
                target = action.get("target", "code_generator")
                params = action.get("parameters", {})
                agent = self.sub_agents.get(target)

                if not agent:
                    return {"success": False, "status": "failed", "error": f"Agent not found: {target}"}

                result = await agent.process(params)

                return {
                    "success": result.success,
                    "status": "success" if result.success else "failed",
                    "data": {"generated_code": result.data.get("code")} if result.success else {},
                    "error": result.error if not result.success else None
                }

            elif action_type == "adapt_data":
                agent = self.sub_agents.get("data_adapter")
                result = await agent.process(action.get("parameters", {}))

                return {
                    "success": result.success,
                    "status": "success" if result.success else "failed",
                    "data": {"adapted": result.data} if result.success else {},
                    "error": result.error if not result.success else None
                }

            elif action_type == "analyze":
                # LLM分析数据
                prompt = f"分析数据：\n{json.dumps(accumulated_data, ensure_ascii=False, indent=2)}"
                messages = [HumanMessage(content=prompt)]
                response = await self._invoke_llm_with_retry(messages)

                return {
                    "success": True,
                    "status": "success",
                    "data": {"analysis": response.content}
                }

            elif action_type == "finish":
                return {
                    "success": True,
                    "status": "completed",
                    "task_completed": True
                }

            else:
                return {
                    "success": False,
                    "status": "failed",
                    "error": f"Unknown action: {action_type}"
                }

        except Exception as e:
            logger.error(f"Action execution failed: {str(e)}")
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "can_retry": True
            }

    async def _generate_final_report(
        self,
        user_request: str,
        history: List[Dict],
        accumulated_data: Dict
    ) -> str:
        """生成最终报告"""
        prompt = f"""# 任务
{user_request}

# 执行过程
{len(history)} 个步骤

# 收集的数据
{json.dumps(accumulated_data, ensure_ascii=False, indent=2)[:1000]}

生成简洁的中文报告，包含：
1. 完成了什么
2. 关键发现
3. 建议
"""

        messages = [HumanMessage(content=prompt)]
        response = await self._invoke_llm_with_retry(messages)

        return response.content

    async def _invoke_llm_with_retry(self, messages: List, max_retries: int = 3) -> Any:
        """带重试的LLM调用"""
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.llm.ainvoke(messages)
                return response
            except Exception as e:
                error_msg = str(e).lower()
                is_retriable = any(keyword in error_msg for keyword in [
                    'connection', 'disconnect', 'timeout', 'network'
                ])

                if attempt < max_retries and is_retriable:
                    wait_time = 2 ** (attempt - 1)
                    logger.warning(f"LLM retry {attempt}/{max_retries} in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"LLM failed after {attempt} attempts")
                    raise
