"""
Code Generator Agent - 代码生成Agent
基于LangChain实现，根据API规格生成云服务调用代码
"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
import json
import logging

from .base_agent import BaseAgent, AgentResponse
from config import get_config
from rag_system import get_rag_system

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

            # 从RAG检索相关文档
            rag_results = await self.rag_system.query(
                query_text=f"{cloud_provider} {service} {operation}",
                cloud_provider=cloud_provider,
                service=service,
                top_k=5
            )

            if not rag_results.get("success"):
                logger.warning(f"RAG query failed: {rag_results.get('error')}")
                rag_context = ""
            else:
                # 构建RAG上下文
                rag_context = self._build_rag_context(rag_results.get("results", []))

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

            return AgentResponse(
                success=True,
                data={
                    "code": code,
                    "language": language,
                    "operation": operation,
                    "cloud_provider": cloud_provider,
                    "service": service
                },
                metadata={
                    "rag_results_used": len(rag_results.get("results", [])),
                    "code_length": len(code)
                }
            )

        except Exception as e:
            logger.error(f"Error in CodeGeneratorAgent.process: {str(e)}")
            return AgentResponse(
                success=False,
                error=str(e)
            )

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

        response = await self.llm.ainvoke(messages)
        code = self._extract_code_from_response(response.content, language)

        return code

    def _get_system_prompt(self, language: str, retry_context: Dict[str, Any] = None) -> str:
        """获取系统提示（支持重试场景）"""
        base_prompt = """你是一个专业的云服务代码生成专家。你的任务是根据API文档和用户需求生成高质量的代码。

要求：
1. 代码必须完整可运行
2. 包含完整的错误处理
3. 添加清晰的注释和文档
4. 遵循最佳实践和编码规范
5. 处理边界情况
6. 包含必要的导入语句
7. 添加类型提示（如果语言支持）
8. 生成的代码应该易于理解和维护
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
        生成测试代码

        Args:
            main_code: 主代码
            language: 编程语言
            operation: 操作名称

        Returns:
            测试代码
        """
        try:
            system_prompt = f"""你是一个测试代码生成专家。请为给定的代码生成完整的单元测试。

要求：
1. 使用标准测试框架（Python: pytest, JS: Jest, TS: Jest, Go: testing）
2. 测试正常情况
3. 测试边界情况
4. 测试错误处理
5. 使用Mock模拟外部API调用
6. 包含清晰的测试描述
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

            response = await self.llm.ainvoke(messages)
            test_code = self._extract_code_from_response(response.content, language)

            return AgentResponse(
                success=True,
                data={
                    "test_code": test_code,
                    "language": language
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

            response = await self.llm.ainvoke(messages)
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
