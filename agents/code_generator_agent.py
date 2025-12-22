"""
Code Generator Agent - 代码生成Agent
基于LangChain实现，根据API规格生成云服务调用代码
支持ReAct模式：自主生成→测试→观察→修正（最多3次）
"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
import json
import logging
import subprocess
import tempfile
import asyncio
from pathlib import Path

from .base_agent import BaseAgent, AgentResponse
from config import get_config
from rag_system import get_rag_system
from services.code_quality import CodeQualityAnalyzer
from services.code_templates import CodeTemplateLibrary
from services.test_generator import TestGenerator
from services.code_reviewer import CodeReviewer
from llm_utils import create_chat_llm

logger = logging.getLogger(__name__)


class CodeGeneratorAgent(BaseAgent):
    """
    Code Generator Agent负责：
    1. 从RAG系统检索相关API文档
    2. 根据文档和用户需求生成代码
    3. 生成完整的错误处理和注释
    4. 支持多语言（Python, JavaScript, TypeScript, Go）
    """

    SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "go"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("CodeGeneratorAgent", config)
        self.config_obj = get_config()
        self.llm = self._init_llm()
        self.rag_system = get_rag_system()
        self.max_react_iterations = 3  # ReAct最大迭代次数

        # 代码质量工具
        self.quality_analyzer = CodeQualityAnalyzer(enable_mypy=False)
        self.template_library = CodeTemplateLibrary()
        self.test_generator = TestGenerator()
        self.code_reviewer = CodeReviewer()

    def _init_llm(self) -> ChatOpenAI:
        """初始化LLM（禁用代理，配置更长的超时时间）"""
        return create_chat_llm(timeout=120.0)

    def get_capabilities(self) -> List[str]:
        """获取Agent能力"""
        return [
            "基于API规格生成代码",
            "支持多种编程语言",
            "集成RAG文档检索",
            "生成完整错误处理",
            "包含详细注释和文档"
        ]

    def validate_input(self, input_data: Any) -> bool:
        """验证输入"""
        if not isinstance(input_data, dict):
            return False
        return "operation" in input_data or "requirements" in input_data

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        处理代码生成请求

        Args:
            input_data: {
                "operation": "get_metric_statistics",
                "cloud_provider": "aws",
                "service": "cloudwatch",
                "parameters": {...},
                "language": "python",  # 可选
                "context": [...]  # 可选，来自之前步骤的上下文
            }

        Returns:
            AgentResponse包含生成的代码
        """
        try:
            operation = input_data.get("operation", "")
            cloud_provider = input_data.get("cloud_provider", "aws")
            service = input_data.get("service", "")
            parameters = input_data.get("parameters", {})
            language = input_data.get("language", "python")
            context = input_data.get("context", [])
            retry_context = input_data.get("retry_context")  # 错误反馈上下文
            specifications = input_data.get("specifications")  # API规格文档

            if language not in self.SUPPORTED_LANGUAGES:
                return AgentResponse(
                    success=False,
                    error=f"Unsupported language: {language}. Supported: {self.SUPPORTED_LANGUAGES}"
                )

            # 从RAG检索相关文档（在独立线程中运行，避免同步阻塞）
            rag_results = {"success": False, "results": []}  # 默认值
            try:
                loop = asyncio.get_event_loop()
                rag_results = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,  # 默认线程池
                        self._sync_rag_query,
                        f"{cloud_provider} {service} {operation}",
                        cloud_provider,
                        service,
                        5
                    ),
                    timeout=15.0  # 15秒超时（包含模型下载时间）
                )

                if not rag_results.get("success"):
                    logger.warning(f"RAG query failed: {rag_results.get('error')}")
                    rag_context = ""
                else:
                    # 构建RAG上下文
                    rag_context = self._build_rag_context(rag_results.get("results", []))
            except asyncio.TimeoutError:
                logger.warning("RAG query timeout (15s), skipping RAG context")
                rag_context = ""
                rag_results = {"success": False, "results": [], "error": "timeout"}
            except Exception as e:
                logger.warning(f"RAG query error: {str(e)}, skipping RAG context")
                rag_context = ""
                rag_results = {"success": False, "results": [], "error": str(e)}

            # 生成代码
            code = await self._generate_code(
                operation=operation,
                cloud_provider=cloud_provider,
                service=service,
                parameters=parameters,
                language=language,
                rag_context=rag_context,
                additional_context=context,
                retry_context=retry_context,
                specifications=specifications
            )

            # 代码质量检查和审查（仅Python）
            quality_result = None
            review_result = None

            if language == "python":
                try:
                    # 1. 代码质量分析
                    logger.info("执行代码质量分析...")
                    quality_result = self.quality_analyzer.analyze(code)

                    # 2. 代码审查
                    logger.info("执行代码审查...")
                    review_result = self.code_reviewer.review(code)

                    # 记录结果
                    logger.info(
                        f"质量分数: {quality_result.get('quality_score', 0):.1f}, "
                        f"审查分数: {review_result.score:.1f}"
                    )

                except Exception as e:
                    logger.warning(f"代码质量检查失败: {e}")

            return AgentResponse(
                success=True,
                data={
                    "code": code,
                    "language": language,
                    "operation": operation,
                    "cloud_provider": cloud_provider,
                    "service": service,
                    "quality_analysis": quality_result,
                    "review_result": review_result
                },
                metadata={
                    "rag_results_used": len(rag_results.get("results", [])),
                    "code_length": len(code),
                    "quality_score": quality_result.get("quality_score", 0) if quality_result else 0,
                    "review_score": review_result.score if review_result else 0
                }
            )

        except Exception as e:
            logger.error(f"Error in CodeGeneratorAgent.process: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return AgentResponse(
                success=False,
                error=str(e),
                agent_name=self.name
            )

    def _sync_rag_query(self, query_text: str, cloud_provider: str, service: str, top_k: int) -> Dict[str, Any]:
        """
        同步RAG查询（用于在独立线程中运行）

        这个方法会被run_in_executor调用，避免同步阻塞事件循环
        """
        import asyncio

        # 在独立线程中创建新的事件循环
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.rag_system.query(
                    query_text=query_text,
                    cloud_provider=cloud_provider,
                    service=service,
                    top_k=top_k
                )
            )

            loop.close()
            return result
        except Exception as e:
            logger.error(f"Sync RAG query failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _invoke_llm_with_retry(self, messages: List, max_retries: int = 3) -> Any:
        """
        带重试的LLM调用（处理连接中断问题）

        针对SiliconFlow API的间歇性连接问题，使用指数退避重试策略
        """
        import time

        for attempt in range(1, max_retries + 1):
            try:
                response = await self.llm.ainvoke(messages)
                return response
            except Exception as e:
                error_msg = str(e).lower()
                # 判断是否为可重试的错误
                is_retriable = any(keyword in error_msg for keyword in [
                    'connection', 'disconnect', 'timeout', 'timed out',
                    'network', 'remoteprot', 'server disconnected'
                ])

                if attempt < max_retries and is_retriable:
                    wait_time = 2 ** (attempt - 1)  # 指数退避：1s, 2s, 4s
                    logger.warning(
                        f"LLM call failed (attempt {attempt}/{max_retries}): {str(e)}"
                        f" - Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # 不可重试的错误或已达最大重试次数
                    logger.error(f"LLM call failed after {attempt} attempts: {str(e)}")
                    raise

    def _build_rag_context(self, results: List[Dict[str, Any]]) -> str:
        """构建RAG检索结果的上下文"""
        if not results:
            return ""

        context = "# Relevant API Documentation:\n\n"

        for i, result in enumerate(results, 1):
            context += f"## Document {i} (Score: {result.get('score', 0):.3f})\n\n"
            context += result.get("text", "")
            context += "\n\n---\n\n"

        return context

    async def _generate_code(
        self,
        operation: str,
        cloud_provider: str,
        service: str,
        parameters: Dict[str, Any],
        language: str,
        rag_context: str,
        additional_context: List[Dict[str, Any]],
        retry_context: Dict[str, Any] = None,
        specifications: Dict[str, Any] = None
    ) -> str:
        """生成代码（支持重试和错误反馈）"""

        system_prompt = self._get_system_prompt(language, retry_context)
        user_prompt = self._build_user_prompt(
            operation=operation,
            cloud_provider=cloud_provider,
            service=service,
            parameters=parameters,
            rag_context=rag_context,
            additional_context=additional_context,
            retry_context=retry_context,
            specifications=specifications
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await self._invoke_llm_with_retry(messages)
        code = self._extract_code_from_response(response.content, language)

        return code

    def _get_system_prompt(self, language: str, retry_context: Dict[str, Any] = None) -> str:
        """获取系统提示（支持重试场景）"""
        base_prompt = """你是一个专业的云服务代码生成专家。你的任务是根据API文档和用户需求生成高质量的代码。

要求：
1. 代码必须完整可运行
2. 包含完整的错误处理（使用try-except捕获异常）
3. 添加清晰的注释和文档
4. 遵循最佳实践和编码规范
5. 处理边界情况（空值、空列表等）
6. 包含必要的导入语句
7. 添加类型提示（如果语言支持）
8. 生成的代码应该易于理解和维护
9. 对于AWS API调用，优先使用paginator处理分页
10. 添加重试机制处理临时错误
11. 使用logging记录关键信息（不要使用print）
12. 确保资源正确清理（使用with语句或finally块）
"""

        if retry_context:
            base_prompt += """

IMPORTANT - 这是一次重试生成：
之前生成的代码测试失败了。请仔细分析测试错误信息，修正问题后重新生成代码。
关注：
1. 修复语法错误
2. 修正逻辑错误
3. 改进错误处理
4. 确保参数使用正确
5. 遵循API规格文档
"""

        language_specifics = {
            "python": """
语言特定要求（Python）：
- 使用type hints
- 遵循PEP 8规范
- 使用适当的异常处理
- 包含docstrings
- 使用async/await（如果适用）
- 使用logging而不是print
""",
            "javascript": """
语言特定要求（JavaScript）：
- 使用ES6+语法
- 使用async/await
- 包含JSDoc注释
- 使用try-catch错误处理
- 遵循Airbnb风格指南
""",
            "typescript": """
语言特定要求（TypeScript）：
- 使用严格的类型定义
- 定义接口和类型
- 包含TSDoc注释
- 使用async/await
- 遵循TypeScript最佳实践
""",
            "go": """
语言特定要求（Go）：
- 遵循Go命名约定
- 使用error返回值
- 包含godoc注释
- 使用defer处理清理
- 遵循Go最佳实践
"""
        }

        return base_prompt + language_specifics.get(language, "")

    def _build_user_prompt(
        self,
        operation: str,
        cloud_provider: str,
        service: str,
        parameters: Dict[str, Any],
        rag_context: str,
        additional_context: List[Dict[str, Any]],
        retry_context: Dict[str, Any] = None,
        specifications: Dict[str, Any] = None
    ) -> str:
        """构建用户提示（支持重试和规格文档）"""
        prompt = f"""请生成代码来实现以下云服务API调用：

**云平台**: {cloud_provider}
**服务**: {service}
**操作**: {operation}

**参数**:
{json.dumps(parameters, indent=2, ensure_ascii=False)}

"""

        # 添加API规格文档（最新拉取的）
        if specifications:
            prompt += f"""
**最新API规格文档**:
{json.dumps(specifications, indent=2, ensure_ascii=False)[:2000]}

"""

        if rag_context:
            prompt += f"""
**API文档参考**:
{rag_context}

"""

        if additional_context:
            prompt += f"""
**额外上下文**:
{json.dumps(additional_context, indent=2, ensure_ascii=False)}

"""

        # 如果是重试，添加错误反馈
        if retry_context:
            prompt += f"""
**⚠️ 重试信息 - 之前的代码测试失败了**:

**失败的代码**:
```python
{retry_context.get('previous_code', '')}
```

**测试错误摘要**:
{retry_context.get('error_summary', '')}

**详细错误**:
{json.dumps(retry_context.get('test_errors', []), indent=2, ensure_ascii=False)[:500]}

**失败的测试**:
{json.dumps(retry_context.get('failed_tests', []), indent=2, ensure_ascii=False)[:500]}

请分析上述错误，修正问题后重新生成代码。确保：
1. 修复所有语法错误
2. 修正API调用参数
3. 改进错误处理
4. 遵循最新的API规格文档

"""

        prompt += """
请生成完整的代码，包括：
1. 所有必要的导入
2. 客户端初始化
3. API调用函数
4. 错误处理
5. 返回值处理
6. 使用示例（在注释中或单独的main函数）

只返回代码，用```代码块包裹。
"""

        return prompt

    def _extract_code_from_response(self, response: str, language: str) -> str:
        """从响应中提取代码"""
        # 尝试提取代码块
        if f"```{language}" in response:
            start = response.find(f"```{language}") + len(f"```{language}")
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()

        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()

        # 如果没有代码块标记，返回整个响应
        return response.strip()

    async def generate_test_code(
        self,
        main_code: str,
        language: str,
        operation: str
    ) -> AgentResponse:
        """
        生成测试代码（使用TestGenerator自动生成）

        Args:
            main_code: 主代码
            language: 编程语言
            operation: 操作名称

        Returns:
            测试代码
        """
        try:
            # 优先使用TestGenerator自动生成（仅Python）
            if language == "python":
                logger.info("使用TestGenerator自动生成测试")
                test_code = self.test_generator.generate_tests(main_code)

                if test_code:
                    return AgentResponse(
                        success=True,
                        data={
                            "test_code": test_code,
                            "language": language,
                            "generator": "automatic"
                        }
                    )

            # 回退到LLM生成（其他语言或自动生成失败）
            logger.info("使用LLM生成测试")
            system_prompt = f"""你是一个测试代码生成专家。请为给定的代码生成完整的单元测试。

要求：
1. 使用标准测试框架（Python: pytest, JS: Jest, TS: Jest, Go: testing）
2. 测试正常情况
3. 测试边界情况
4. 测试错误处理
5. 使用Mock模拟外部API调用
6. 包含清晰的测试描述
7. 目标代码覆盖率 >80%
"""

            user_prompt = f"""请为以下{language}代码生成单元测试：

```{language}
{main_code}
```

操作名称: {operation}

生成完整的测试文件，只返回代码，用```代码块包裹。
"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self._invoke_llm_with_retry(messages)
            test_code = self._extract_code_from_response(response.content, language)

            return AgentResponse(
                success=True,
                data={
                    "test_code": test_code,
                    "language": language,
                    "generator": "llm"
                }
            )

        except Exception as e:
            logger.error(f"Error generating test code: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e)
            )

    async def refine_code(
        self,
        code: str,
        language: str,
        feedback: str
    ) -> AgentResponse:
        """
        根据反馈改进代码

        Args:
            code: 原始代码
            language: 编程语言
            feedback: 反馈信息

        Returns:
            改进后的代码
        """
        try:
            system_prompt = "你是一个代码优化专家。请根据反馈改进给定的代码。"

            user_prompt = f"""请改进以下{language}代码：

```{language}
{code}
```

**反馈**: {feedback}

请生成改进后的完整代码，只返回代码，用```代码块包裹。
"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self._invoke_llm_with_retry(messages)
            refined_code = self._extract_code_from_response(response.content, language)

            return AgentResponse(
                success=True,
                data={
                    "code": refined_code,
                    "language": language
                }
            )

        except Exception as e:
            logger.error(f"Error refining code: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e)
            )

    def get_relevant_templates(
        self,
        cloud_provider: str,
        operation: str
    ) -> List[Dict[str, Any]]:
        """
        获取相关的代码模板

        Args:
            cloud_provider: 云平台
            operation: 操作名称

        Returns:
            相关模板列表
        """
        from services.code_templates import CloudProvider

        # 映射云平台名称
        provider_map = {
            'aws': CloudProvider.AWS,
            'azure': CloudProvider.AZURE,
            'gcp': CloudProvider.GCP,
            'kubernetes': CloudProvider.KUBERNETES,
            'k8s': CloudProvider.KUBERNETES,
            'volcengine': CloudProvider.VOLCENGINE
        }

        provider_enum = provider_map.get(cloud_provider.lower())
        if not provider_enum:
            return []

        # 搜索相关模板
        templates = self.template_library.search_templates(
            cloud_provider=provider_enum,
            keyword=operation
        )

        # 转换为字典格式
        return [
            {
                'name': t.name,
                'description': t.description,
                'code': t.code_template,
                'example': t.example,
                'best_practices': t.best_practices,
                'common_pitfalls': t.common_pitfalls
            }
            for t in templates[:3]  # 最多返回3个模板
        ]

    async def process_with_react(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        ReAct模式处理：自主生成代码→测试→观察→修正（最多3次）

        Args:
            input_data: {
                "requirement": "需求描述",
                "operation": "操作名称",
                "cloud_provider": "aws",
                "service": "cloudwatch",
                "parameters": {...},
                "language": "python",
                "enable_auto_test": True  # 是否自动执行测试
            }

        Returns:
            AgentResponse包含最终代码和测试结果
        """
        try:
            requirement = input_data.get("requirement", "")
            operation = input_data.get("operation", "")
            cloud_provider = input_data.get("cloud_provider", "aws")
            service = input_data.get("service", "")
            parameters = input_data.get("parameters", {})
            language = input_data.get("language", "python")
            enable_auto_test = input_data.get("enable_auto_test", True)

            logger.info(f"[ReAct] Starting code generation: {requirement}")

            # ReAct历史记录
            react_history = []
            generated_code = None
            test_code = None

            for iteration in range(1, self.max_react_iterations + 1):
                logger.info(f"[ReAct] Iteration {iteration}/{self.max_react_iterations}")

                # === Thought阶段：分析和规划 ===
                thought = await self._react_thought(
                    requirement=requirement,
                    iteration_history=react_history
                )
                logger.info(f"[ReAct] Thought: {thought[:200]}...")

                # === Action阶段：生成/修正代码 ===
                if iteration == 1:
                    # 第一次：正常生成代码
                    code_response = await self.process({
                        "operation": operation,
                        "cloud_provider": cloud_provider,
                        "service": service,
                        "parameters": parameters,
                        "language": language
                    })

                    if not code_response.success:
                        return code_response

                    generated_code = code_response.data["code"]

                    # 生成测试代码
                    test_response = await self.generate_test_code(
                        main_code=generated_code,
                        language=language,
                        operation=operation
                    )

                    if test_response.success:
                        test_code = test_response.data["test_code"]
                else:
                    # 后续迭代：根据错误反馈重新生成
                    last_observation = react_history[-1]["observation"]

                    # 使用retry_context重新生成
                    code_response = await self.process({
                        "operation": operation,
                        "cloud_provider": cloud_provider,
                        "service": service,
                        "parameters": parameters,
                        "language": language,
                        "retry_context": {
                            "previous_code": generated_code,
                            "error_summary": last_observation.get("error", ""),
                            "test_errors": [last_observation.get("stderr", "")],
                            "failed_tests": [last_observation.get("stdout", "")]
                        }
                    })

                    if not code_response.success:
                        return code_response

                    generated_code = code_response.data["code"]

                    # 重新生成测试
                    test_response = await self.generate_test_code(
                        main_code=generated_code,
                        language=language,
                        operation=operation
                    )

                    if test_response.success:
                        test_code = test_response.data["test_code"]

                logger.info(f"[ReAct] Action: Generated {len(generated_code)} chars of code")

                # === Observation阶段：执行测试 ===
                if enable_auto_test and test_code:
                    observation = await self._react_observation(
                        code=generated_code,
                        test_code=test_code,
                        language=language
                    )
                else:
                    # 跳过测试，假设成功
                    observation = {
                        "status": "skipped",
                        "message": "Auto test disabled"
                    }

                logger.info(f"[ReAct] Observation: {observation.get('status')}")

                # 记录历史
                react_history.append({
                    "iteration": iteration,
                    "thought": thought,
                    "action": {
                        "code_length": len(generated_code),
                        "test_length": len(test_code) if test_code else 0
                    },
                    "observation": observation
                })

                # 如果测试通过或跳过，返回成功
                if observation.get("status") in ["success", "skipped"]:
                    return AgentResponse(
                        success=True,
                        data={
                            "code": generated_code,
                            "test_code": test_code,
                            "language": language,
                            "iterations": iteration,
                            "react_history": react_history
                        },
                        message=f"代码生成成功（{iteration}次ReAct迭代）",
                        agent_name=self.name
                    )

                # 继续下一次迭代
                if iteration < self.max_react_iterations:
                    logger.info(f"[ReAct] Test failed, retrying...")

            # 达到最大迭代次数
            return AgentResponse(
                success=False,
                data={
                    "code": generated_code,
                    "test_code": test_code,
                    "language": language,
                    "iterations": self.max_react_iterations,
                    "react_history": react_history
                },
                message=f"代码生成失败：{self.max_react_iterations}次ReAct迭代后测试仍未通过",
                agent_name=self.name
            )

        except Exception as e:
            logger.error(f"[ReAct] Error: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e),
                agent_name=self.name
            )

    async def _react_thought(
        self,
        requirement: str,
        iteration_history: List[Dict[str, Any]]
    ) -> str:
        """ReAct的Thought阶段：分析需求和历史错误"""
        if not iteration_history:
            # 第一次迭代
            prompt = f"""你是专业的Python开发Agent。需求：{requirement}

请简要分析：
1. 需要实现什么功能？
2. 采用什么技术方案？
3. 关键实现点？

（100字以内）"""
        else:
            # 后续迭代
            last_obs = iteration_history[-1]["observation"]
            prompt = f"""需求：{requirement}

第{len(iteration_history) + 1}次尝试。上次测试失败：
错误：{last_obs.get('error', 'N/A')[:300]}

请分析：
1. 失败的根本原因？
2. 如何修正？

（100字以内）"""

        messages = [
            SystemMessage(content="你是专业的Python开发专家。"),
            HumanMessage(content=prompt)
        ]

        response = await self._invoke_llm_with_retry(messages)
        return response.content.strip()

    async def _react_observation(
        self,
        code: str,
        test_code: str,
        language: str
    ) -> Dict[str, Any]:
        """ReAct的Observation阶段：执行测试并观察结果"""
        if language != "python":
            return {
                "status": "skipped",
                "message": f"Auto test not supported for {language}"
            }

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmppath = Path(tmpdir)

                # 写入主代码
                code_file = tmppath / "implementation.py"
                code_file.write_text(code, encoding="utf-8")

                # 写入测试代码
                test_file = tmppath / "test_implementation.py"

                # 确保测试导入了implementation
                if "import implementation" not in test_code and "from implementation" not in test_code:
                    test_code = "import sys\nsys.path.insert(0, '.')\nimport implementation\n" + test_code

                test_file.write_text(test_code, encoding="utf-8")

                # 运行pytest
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=tmpdir
                )

                if result.returncode == 0:
                    return {
                        "status": "success",
                        "stdout": result.stdout,
                        "message": "所有测试通过"
                    }
                else:
                    return {
                        "status": "failed",
                        "error": "测试失败",
                        "stderr": result.stderr,
                        "stdout": result.stdout,
                        "returncode": result.returncode
                    }

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "error": "测试超时（30秒）"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
