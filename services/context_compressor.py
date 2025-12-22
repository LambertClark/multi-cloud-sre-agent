"""
上下文压缩器
自动压缩长对话历史，保留关键信息
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from services.conversation_manager import Message, MessageRole, ConversationSession
from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """压缩配置"""
    max_messages: int = 20  # 最多保留消息数
    max_tokens: int = 4000  # 最大token数（估算）
    keep_recent: int = 5  # 始终保留最近N条消息
    summary_trigger: int = 15  # 触发总结的消息数阈值


class ContextCompressor:
    """
    上下文压缩器

    策略：
    1. 始终保留最近N条消息（默认5条）
    2. 对更早的消息进行总结
    3. 提取关键实体和任务
    4. 控制总token数在限制内
    """

    def __init__(self, config: Optional[CompressionConfig] = None, llm: Optional[ChatOpenAI] = None):
        self.config = config or CompressionConfig()

        # LLM用于总结（延迟初始化）
        self._llm = llm
        self._llm_config = get_config().llm if not llm else None

    @property
    def llm(self) -> ChatOpenAI:
        """延迟初始化LLM"""
        if self._llm is None:
            llm_config = self._llm_config

            self._llm = ChatOpenAI(
                model=llm_config.model,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
                temperature=0.3,  # 总结时使用较低温度
                max_tokens=llm_config.max_tokens,
                timeout=60.0
            )

        return self._llm

    def should_compress(self, messages: List[Message]) -> bool:
        """判断是否需要压缩"""
        # 消息数量超过阈值
        if len(messages) >= self.config.summary_trigger:
            return True

        # Token数量超过阈值（粗略估算：每条消息约200 tokens）
        estimated_tokens = len(messages) * 200
        if estimated_tokens > self.config.max_tokens:
            return True

        return False

    async def compress_messages(self, messages: List[Message]) -> List[Message]:
        """
        压缩消息列表

        Args:
            messages: 原始消息列表

        Returns:
            压缩后的消息列表
        """
        if not self.should_compress(messages):
            return messages

        logger.info(f"开始压缩 {len(messages)} 条消息")

        # 1. 保留最近的消息
        recent_messages = messages[-self.config.keep_recent:]

        # 2. 需要总结的历史消息
        history_messages = messages[:-self.config.keep_recent]

        # 3. 生成总结
        if history_messages:
            summary = await self._summarize_messages(history_messages)

            # 创建总结消息
            summary_message = Message(
                role=MessageRole.SYSTEM,
                content=f"【对话历史总结】\n{summary}",
                metadata={"compressed": True, "original_count": len(history_messages)}
            )

            # 返回：总结 + 最近消息
            compressed = [summary_message] + recent_messages
        else:
            compressed = recent_messages

        logger.info(f"压缩完成: {len(messages)} → {len(compressed)} 条消息")

        return compressed

    async def _summarize_messages(self, messages: List[Message]) -> str:
        """
        使用LLM总结消息

        Args:
            messages: 需要总结的消息列表

        Returns:
            总结文本
        """
        # 构建对话历史文本
        conversation_text = self._format_messages(messages)

        system_prompt = """你是一个专业的对话总结专家。请总结以下对话的关键信息。

要求：
1. 提取用户的主要需求和意图
2. 列出已完成的任务和结果
3. 记录重要的上下文信息（如业务名称、资源ID、参数等）
4. 保留待处理的任务
5. 简洁明了，控制在300字以内

格式：
**用户需求**: ...
**已完成任务**: ...
**重要上下文**: ...
**待处理任务**: ...
"""

        user_prompt = f"""请总结以下对话：

{conversation_text}
"""

        try:
            # 调用LLM生成总结
            messages_llm = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self.llm.ainvoke(messages_llm)
            summary = response.content.strip()

            return summary

        except Exception as e:
            logger.error(f"LLM总结失败: {e}")

            # Fallback: 简单的文本总结
            return self._simple_summary(messages)

    def _format_messages(self, messages: List[Message]) -> str:
        """格式化消息为文本"""
        lines = []

        for msg in messages:
            role_name = {
                MessageRole.USER: "用户",
                MessageRole.ASSISTANT: "助手",
                MessageRole.SYSTEM: "系统"
            }.get(msg.role, msg.role.value)

            lines.append(f"{role_name}: {msg.content}")

        return "\n".join(lines)

    def _simple_summary(self, messages: List[Message]) -> str:
        """简单的文本总结（Fallback）"""
        # 提取用户消息
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]

        summary_parts = []

        if user_messages:
            user_requests = [m.content[:100] for m in user_messages[:3]]  # 只取前3条
            summary_parts.append(f"**用户需求**: {'; '.join(user_requests)}")

        if assistant_messages:
            summary_parts.append(f"**助手回复**: 共{len(assistant_messages)}次交互")

        if not summary_parts:
            summary_parts.append("对话历史")

        return "\n".join(summary_parts)

    def extract_context_variables(self, messages: List[Message]) -> Dict[str, Any]:
        """
        从消息中提取上下文变量

        提取常见的实体：
        - 业务名称
        - 资源ID
        - 云平台
        - 服务名称
        """
        context = {}

        for msg in messages:
            # 从metadata提取
            if msg.metadata:
                # 云平台
                if "cloud_provider" in msg.metadata:
                    context["cloud_provider"] = msg.metadata["cloud_provider"]

                # 服务
                if "service" in msg.metadata:
                    context["service"] = msg.metadata["service"]

                # 业务名称
                if "business_name" in msg.metadata:
                    context["business_name"] = msg.metadata["business_name"]

                # 其他自定义变量
                for key, value in msg.metadata.items():
                    if key.startswith("ctx_"):
                        context[key.replace("ctx_", "")] = value

        return context

    async def compress_session(self, session: ConversationSession) -> ConversationSession:
        """
        压缩整个会话

        Args:
            session: 原始会话

        Returns:
            压缩后的会话（不修改原会话）
        """
        if not self.should_compress(session.messages):
            return session

        # 创建新会话副本
        compressed_session = ConversationSession(
            session_id=session.session_id,
            user_id=session.user_id,
            messages=[],  # 将被替换
            tasks=session.tasks.copy(),  # 保留所有任务
            context_variables=session.context_variables.copy(),
            created_at=session.created_at,
            updated_at=session.updated_at,
            metadata=session.metadata.copy()
        )

        # 压缩消息
        compressed_messages = await self.compress_messages(session.messages)
        compressed_session.messages = compressed_messages

        # 提取并合并上下文变量
        extracted_context = self.extract_context_variables(session.messages)
        compressed_session.context_variables.update(extracted_context)

        return compressed_session


def estimate_tokens(text: str) -> int:
    """
    估算文本的token数

    简单估算：1个token ≈ 4个字符（英文）或 1.5个汉字
    """
    # 统计中文字符和其他字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars

    # 估算tokens
    estimated = int(chinese_chars / 1.5 + other_chars / 4)

    return estimated


async def compress_for_llm(
    messages: List[Message],
    max_tokens: int = 4000,
    keep_recent: int = 5
) -> List[Dict[str, str]]:
    """
    为LLM调用准备压缩的消息

    Args:
        messages: 原始消息列表
        max_tokens: 最大token限制
        keep_recent: 保留最近N条消息

    Returns:
        LLM格式的消息列表 [{"role": "user", "content": "..."}]
    """
    compressor = ContextCompressor(
        config=CompressionConfig(
            max_tokens=max_tokens,
            keep_recent=keep_recent
        )
    )

    # 检查是否需要压缩
    total_tokens = sum(estimate_tokens(msg.content) for msg in messages)

    if total_tokens > max_tokens:
        compressed_messages = await compressor.compress_messages(messages)
    else:
        compressed_messages = messages

    # 转换为LLM格式
    llm_messages = []
    for msg in compressed_messages:
        llm_messages.append({
            "role": msg.role.value,
            "content": msg.content
        })

    return llm_messages
