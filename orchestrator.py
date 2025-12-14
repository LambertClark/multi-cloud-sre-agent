"""
多云SRE Agent编排器
负责协调各个Agent完成完整的工作流
"""
from typing import Dict, Any, Optional, List
import logging
import json
from datetime import datetime

from agents import ManagerAgent, SpecDocAgent, CodeGeneratorAgent
from agents.task_planner_agent import get_task_planner
from tools import CloudToolRegistry, AWSMonitoringTools
from tools.cloud_tools import get_tool_registry
from rag_system import get_rag_system
from wasm_sandbox import get_sandbox
from task_executor import get_task_executor
from config import get_config

logger = logging.getLogger(__name__)


class MultiCloudOrchestrator:
    """
    多云SRE Agent编排器

    工作流程：
    1. 接收用户请求
    2. Manager Agent分析意图和拆解任务
    3. 检查是否有现成API工具
    4. 如果没有，则：
       a. SpecDoc Agent拉取API规格文档
       b. RAG系统索引文档
       c. Code Generator Agent生成代码
       d. WASM沙箱测试代码
       e. 执行代码
    5. 返回结果
    """

    def __init__(self):
        self.config = get_config()

        # 初始化各个组件
        self.manager_agent = ManagerAgent()
        self.spec_doc_agent = SpecDocAgent()
        self.code_gen_agent = CodeGeneratorAgent()
        self.task_planner = get_task_planner()
        self.task_executor = get_task_executor()
        self.rag_system = get_rag_system()
        self.sandbox = get_sandbox()
        self.tool_registry = get_tool_registry()

        # 初始化云工具
        self._init_cloud_tools()

        # 加载组员整理的云文档（后台任务）
        self._cloud_docs_loaded = False
        self._cloud_docs_loading = False

        logger.info("MultiCloudOrchestrator initialized")

    def _init_cloud_tools(self):
        """初始化云服务工具"""
        # 初始化AWS工具
        aws_tools = AWSMonitoringTools()

        # 注册工具到Manager Agent
        self._register_tools_with_manager()

        logger.info("Cloud tools initialized")

    def _register_tools_with_manager(self):
        """向Manager Agent注册已有的API"""
        # AWS CloudWatch
        self.manager_agent.register_api(
            "aws", "cloudwatch",
            ["get_metric_statistics", "list_metrics", "put_metric_alarm", "describe_alarms"]
        )

        # AWS Logs
        self.manager_agent.register_api(
            "aws", "logs",
            ["filter_log_events", "get_log_events", "describe_log_groups"]
        )

        # AWS X-Ray
        self.manager_agent.register_api(
            "aws", "xray",
            ["get_trace_summaries", "get_service_graph"]
        )

    async def _ensure_cloud_docs_loaded(self):
        """确保云文档已加载"""
        if self._cloud_docs_loaded:
            return

        if self._cloud_docs_loading:
            # 正在加载中，等待
            import asyncio
            while self._cloud_docs_loading:
                await asyncio.sleep(0.1)
            return

        # 开始加载
        self._cloud_docs_loading = True
        try:
            logger.info("Loading cloud documentation from teammate's docs...")
            result = await self.rag_system.load_cloud_docs()

            if result.get("success"):
                self._cloud_docs_loaded = True
                logger.info(
                    f"✅ Loaded {result['loaded_count']}/{result['total_files']} "
                    f"cloud documentation files"
                )
                if result.get("errors"):
                    logger.warning(f"Some files failed to load: {len(result['errors'])}")
            else:
                logger.warning(f"Failed to load cloud docs: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error loading cloud docs: {e}")
        finally:
            self._cloud_docs_loading = False

    async def process_request(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理用户请求

        Args:
            user_query: 用户查询
            context: 可选上下文

        Returns:
            处理结果
        """
        start_time = datetime.now()
        execution_log = []
        api_trace = []  # 用于记录API调用

        try:
            # 暂时禁用自动加载文档（embedding模型需要配置）
            # await self._ensure_cloud_docs_loaded()

            logger.info(f"Processing request: {user_query}")
            execution_log.append({
                "step": "start",
                "timestamp": start_time.isoformat(),
                "query": user_query
            })

            # 检查是否需要多步骤规划（复杂查询）
            if self._needs_multi_step_planning(user_query):
                logger.info("Detected complex query, using TaskPlanner")

                # 使用TaskPlannerAgent规划任务
                planner_response = await self.task_planner.process({
                    "query": user_query,
                    "context": context or {}
                })

                if not planner_response.success:
                    return self._create_error_response(
                        "Task planner failed",
                        planner_response.error,
                        execution_log
                    )

                execution_log.append({
                    "step": "task_planning",
                    "timestamp": datetime.now().isoformat(),
                    "result": planner_response.data
                })

                # 执行多步骤计划
                plan = planner_response.data["plan"]
                logger.info(f"Executing multi-step plan with {len(plan.get('steps', []))} steps")

                result = await self.task_executor.execute_plan(plan)
                
                # 收集TaskExecutor中的API调用（如果支持）
                if isinstance(result, dict) and "api_trace" in result:
                    api_trace.extend(result["api_trace"])

                execution_log.append({
                    "step": "task_execution",
                    "timestamp": datetime.now().isoformat(),
                    "result": result
                })
            else:
                # 原有流程：Manager Agent分析意图和规划
                logger.info("Step 1: Analyzing intent and creating execution plan")
                manager_response = await self.manager_agent.safe_process({
                    "query": user_query,
                    "context": context or {}
                })

                if not manager_response.success:
                    return self._create_error_response(
                        "Manager agent failed",
                        manager_response.error,
                        execution_log
                    )

                execution_log.append({
                    "step": "intent_analysis",
                    "timestamp": datetime.now().isoformat(),
                    "result": manager_response.data
                })

                intent = manager_response.data["intent"]
                execution_plan = manager_response.data["execution_plan"]
                # 步骤2：执行计划
                if execution_plan["has_existing_api"]:
                    # 使用现有API
                    result = await self._execute_with_existing_api(
                        execution_plan,
                        intent,
                        execution_log,
                        api_trace
                    )
                else:
                    # 动态生成代码
                    result = await self._execute_with_code_generation(
                        execution_plan,
                        intent,
                        execution_log,
                        api_trace
                    )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                "success": True,
                "result": result,
                "intent": intent,
                "execution_plan": execution_plan,
                "execution_log": execution_log,
                "api_trace": api_trace,
                "duration": duration,
                "timestamp": end_time.isoformat()
            }

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return self._create_error_response(
                "Orchestrator error",
                str(e),
                execution_log
            )
    async def _execute_with_existing_api(
        self,
        execution_plan: Dict[str, Any],
        intent: Dict[str, Any],
        execution_log: List[Dict[str, Any]],
        api_trace: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """使用现有API执行"""
        logger.info("Executing with existing API")

        cloud_provider = intent.get("cloud_provider")
        service = intent.get("service")
        operation = intent.get("operation")
        parameters = intent.get("parameters", {})

        # 记录API调用意图
        api_trace.append({
            "timestamp": datetime.now().isoformat(),
            "type": "existing_tool",
            "cloud_provider": cloud_provider,
            "service": service,
            "operation": operation,
            "parameters": parameters
        })

        # 调用API工具
        api_result = await self.tool_registry.call(
            cloud_provider,
            service,
            operation,
            parameters
        )

        execution_log.append({
            "step": "api_call",
            "timestamp": datetime.now().isoformat(),
            "api": f"{cloud_provider}.{service}.{operation}",
            "result": api_result
        })

        return api_result
    async def _execute_with_code_generation(
        self,
        execution_plan: Dict[str, Any],
        intent: Dict[str, Any],
        execution_log: List[Dict[str, Any]],
        api_trace: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """通过代码生成执行"""
        logger.info("Executing with code generation pipeline")

        cloud_provider = intent.get("cloud_provider")
        service = intent.get("service")
        operation = intent.get("operation")
        parameters = intent.get("parameters", {})

        # 记录代码生成意图
        api_trace.append({
            "timestamp": datetime.now().isoformat(),
            "type": "code_generation",
            "cloud_provider": cloud_provider,
            "service": service,
            "operation": operation,
            "note": "API calls are embedded in generated code"
        })

        # 步骤1：拉取API规格文档
        logger.info("Step 2.1: Fetching API specifications")
        spec_response = await self.spec_doc_agent.safe_process({
            "cloud_provider": cloud_provider,
            "service": service
        })

        if not spec_response.success:
            execution_log.append({
                "step": "fetch_spec",
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": spec_response.error
            })
            return {
                "success": False,
                "error": f"Failed to fetch specifications: {spec_response.error}"
            }

        execution_log.append({
            "step": "fetch_spec",
            "timestamp": datetime.now().isoformat(),
            "status": "success",
            "operations_found": len(spec_response.data.get("specifications", {}).get("operations", []))
        })

        # 步骤2：索引到RAG系统
        logger.info("Step 2.2: Indexing specifications to RAG")
        rag_response = await self.rag_system.index_documents(spec_response.data)

        if not rag_response.get("success"):
            execution_log.append({
                "step": "index_rag",
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": rag_response.get("error")
            })
            # 继续执行，即使RAG索引失败
            logger.warning("RAG indexing failed, continuing without RAG")

        else:
            execution_log.append({
                "step": "index_rag",
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "documents_indexed": rag_response.get("documents_indexed", 0)
            })

        # 步骤3：生成代码（带重试机制）
        logger.info("Step 2.3: Generating code with retry mechanism")
        max_retries = self.config.wasm.max_code_gen_retries
        enable_feedback = self.config.wasm.enable_retry_with_feedback

        generated_code = None
        test_response = None
        retry_context = None  # 用于存储错误反馈

        for attempt in range(max_retries):
            logger.info(f"Code generation attempt {attempt + 1}/{max_retries}")

            # 构建代码生成请求
            gen_request = {
                "operation": operation,
                "cloud_provider": cloud_provider,
                "service": service,
                "parameters": parameters,
                "language": "python",
                "specifications": spec_response.data.get("specifications")
            }

            # 如果有错误反馈，添加到请求中
            if retry_context and enable_feedback:
                gen_request["retry_context"] = retry_context
                logger.info(f"Retry with feedback: {retry_context.get('error_summary')}")

            # 生成代码
            code_response = await self.code_gen_agent.safe_process(gen_request)

            if not code_response.success:
                execution_log.append({
                    "step": f"generate_code_attempt_{attempt + 1}",
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed",
                    "error": code_response.error
                })

                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Failed to generate code after {max_retries} attempts: {code_response.error}"
                    }
                continue

            generated_code = code_response.data.get("code")

            execution_log.append({
                "step": f"generate_code_attempt_{attempt + 1}",
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "code_length": len(generated_code)
            })

            # 步骤4：测试代码
            logger.info(f"Step 2.4: Testing generated code (attempt {attempt + 1})")
            test_response = await self.sandbox.test_code({
                "code": generated_code,
                "language": "python",
                "operation": operation,
                "parameters": parameters
            })

            execution_log.append({
                "step": f"test_code_attempt_{attempt + 1}",
                "timestamp": datetime.now().isoformat(),
                "status": "success" if test_response.get("success") else "failed",
                "tests": test_response.get("tests", []),
                "errors": test_response.get("errors", [])
            })

            # 如果测试通过，跳出重试循环
            if test_response.get("success"):
                logger.info(f"Code generation and testing succeeded on attempt {attempt + 1}")
                break

            # 测试失败，准备重试
            if attempt < max_retries - 1:
                logger.warning(f"Test failed on attempt {attempt + 1}, preparing retry...")

                # 收集错误信息作为反馈
                retry_context = {
                    "previous_code": generated_code,
                    "test_errors": test_response.get("errors", []),
                    "failed_tests": [t for t in test_response.get("tests", []) if not t.get("passed")],
                    "error_summary": self._summarize_test_errors(test_response)
                }
            else:
                # 最后一次尝试也失败了
                logger.error(f"All {max_retries} code generation attempts failed")
                return {
                    "success": False,
                    "error": f"Code tests failed after {max_retries} attempts",
                    "test_results": test_response,
                    "code": generated_code,
                    "attempts": max_retries
                }

        # 步骤5：执行代码
        logger.info("Step 2.5: Executing code")
        exec_response = await self.sandbox.execute_code(
            code_response.data.get("code"),
            "python",
            parameters
        )

        execution_log.append({
            "step": "execute_code",
            "timestamp": datetime.now().isoformat(),
            "status": "success" if exec_response.get("success") else "failed",
            "output": exec_response.get("output", "")[:500]  # 限制输出长度
        })

        return {
            "success": exec_response.get("success"),
            "output": exec_response.get("output"),
            "code": code_response.data.get("code"),
            "test_results": test_response
        }

    def _needs_multi_step_planning(self, query: str) -> bool:
        """
        判断查询是否需要多步骤规划

        复杂查询特征：
        1. 包含聚合关键词：列出、全部、所有
        2. 包含过滤关键词：超过、大于、小于、>、<
        3. 包含业务标签：xxx业务
        4. 包含分析关键词：健康检查、分析、根因、原因、诊断
        5. 包含多个资源类型
        """
        query_lower = query.lower()

        # 聚合关键词
        aggregation_keywords = ["列出", "全部", "所有", "list", "all"]
        has_aggregation = any(kw in query for kw in aggregation_keywords)

        # 过滤关键词
        filter_keywords = ["超过", "大于", "小于", "高于", "低于", ">", "<", ">=", "<=", "不低于", "不高于"]
        has_filter = any(kw in query for kw in filter_keywords)

        # 业务标签
        has_business_tag = "业务" in query

        # 分析关键词
        analysis_keywords = ["健康检查", "分析", "根因", "原因", "诊断", "优化", "推荐", "定位", "巡查"]
        has_analysis = any(kw in query for kw in analysis_keywords)

        # 多个资源类型
        resource_keywords = ["服务器", "实例", "pod", "容器", "应用", "服务", "cdn", "缓存"]
        resource_count = sum(1 for kw in resource_keywords if kw in query)

        # 判断逻辑：
        # 1. 有聚合+过滤 -> 多步骤
        # 2. 有业务标签+任何操作 -> 多步骤
        # 3. 有分析关键词 -> 多步骤
        # 4. 多个资源类型 -> 多步骤
        needs_multi_step = (
            (has_aggregation and has_filter) or
            (has_business_tag and (has_aggregation or has_filter)) or
            has_analysis or
            resource_count >= 2
        )

        if needs_multi_step:
            logger.info(f"Query requires multi-step planning: agg={has_aggregation}, filter={has_filter}, business={has_business_tag}, analysis={has_analysis}, resources={resource_count}")

        return needs_multi_step

    def _summarize_test_errors(self, test_response: Dict[str, Any]) -> str:
        """总结测试错误，生成简洁的错误描述供LLM理解"""
        errors = test_response.get("errors", [])
        failed_tests = [t for t in test_response.get("tests", []) if not t.get("passed")]

        summary_parts = []

        # 汇总错误类型
        if errors:
            error_types = {}
            for error in errors:
                error_type = error.get("type", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1

            summary_parts.append(f"Errors: {', '.join([f'{k}({v})' for k, v in error_types.items()])}")

        # 汇总失败的测试
        if failed_tests:
            test_names = [t.get("name", "unknown") for t in failed_tests[:3]]  # 最多3个
            summary_parts.append(f"Failed tests: {', '.join(test_names)}")

        # 提取关键错误信息
        if errors:
            key_errors = []
            for error in errors[:2]:  # 最多2个详细错误
                msg = error.get("message", "")
                if msg:
                    key_errors.append(msg[:100])  # 限制长度
            if key_errors:
                summary_parts.append(f"Key errors: {'; '.join(key_errors)}")

        return " | ".join(summary_parts) if summary_parts else "Tests failed without specific errors"

    def _create_error_response(
        self,
        error_type: str,
        error_message: str,
        execution_log: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "success": False,
            "error_type": error_type,
            "error": error_message,
            "execution_log": execution_log,
            "timestamp": datetime.now().isoformat()
        }

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = {
            "status": "healthy",
            "components": {}
        }

        # 检查各个组件
        try:
            # Manager Agent
            health["components"]["manager_agent"] = {
                "status": "ok",
                "capabilities": len(self.manager_agent.get_capabilities())
            }

            # SpecDoc Agent
            health["components"]["spec_doc_agent"] = {
                "status": "ok",
                "capabilities": len(self.spec_doc_agent.get_capabilities())
            }

            # Code Generator Agent
            health["components"]["code_gen_agent"] = {
                "status": "ok",
                "capabilities": len(self.code_gen_agent.get_capabilities())
            }

            # RAG System
            indices = self.rag_system.list_indices()
            health["components"]["rag_system"] = {
                "status": "ok",
                "indices_count": len(indices),
                "indices": indices
            }

            # Tool Registry
            tools = self.tool_registry.list_tools()
            health["components"]["tool_registry"] = {
                "status": "ok",
                "tools_count": len(tools),
                "tools": tools[:10]  # 只显示前10个
            }

            # Sandbox
            health["components"]["sandbox"] = {
                "status": "ok",
                "test_mode": self.config.wasm.test_mode
            }

        except Exception as e:
            health["status"] = "degraded"
            health["error"] = str(e)

        return health


# 全局编排器实例
_orchestrator: Optional[MultiCloudOrchestrator] = None


def get_orchestrator() -> MultiCloudOrchestrator:
    """获取全局编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiCloudOrchestrator()
    return _orchestrator
