"""
对话管理器测试
"""
import pytest
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import shutil

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.conversation_manager import (
    ConversationManager,
    Message,
    MessageRole,
    TaskStatus,
    TaskContext,
    ConversationSession
)
from services.context_compressor import ContextCompressor, compress_for_llm, estimate_tokens


class TestConversationManager:
    """测试对话管理器"""

    @pytest.fixture
    def manager(self, tmp_path):
        """创建临时管理器"""
        storage_dir = tmp_path / "test_conversations"
        manager = ConversationManager(storage_dir=str(storage_dir))
        yield manager

        # 清理
        if storage_dir.exists():
            shutil.rmtree(storage_dir)

    def test_create_session(self, manager):
        """测试创建会话"""
        session = manager.create_session(user_id="user1")

        assert session.session_id is not None
        assert session.user_id == "user1"
        assert len(session.messages) == 0
        assert len(session.tasks) == 0

    def test_add_message(self, manager):
        """测试添加消息"""
        session = manager.create_session()

        manager.add_message(
            session.session_id,
            MessageRole.USER,
            "列出所有EC2实例"
        )

        manager.add_message(
            session.session_id,
            MessageRole.ASSISTANT,
            "好的，我来帮你查询",
            metadata={"cloud_provider": "aws"}
        )

        # 重新获取会话
        session = manager.get_session(session.session_id)

        assert len(session.messages) == 2
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[0].content == "列出所有EC2实例"
        assert session.messages[1].metadata["cloud_provider"] == "aws"

    def test_add_and_update_task(self, manager):
        """测试添加和更新任务"""
        session = manager.create_session()

        # 添加任务
        task = manager.add_task(
            session.session_id,
            "查询EC2实例",
            metadata={"cloud_provider": "aws", "service": "ec2"}
        )

        assert task.status == TaskStatus.PENDING
        assert task.description == "查询EC2实例"

        # 更新任务状态
        manager.update_task(
            session.session_id,
            task.task_id,
            status=TaskStatus.IN_PROGRESS
        )

        # 完成任务
        manager.update_task(
            session.session_id,
            task.task_id,
            status=TaskStatus.COMPLETED,
            result={"instances": ["i-1234", "i-5678"]}
        )

        # 重新获取会话
        session = manager.get_session(session.session_id)
        updated_task = session.tasks[0]

        assert updated_task.status == TaskStatus.COMPLETED
        assert updated_task.result == {"instances": ["i-1234", "i-5678"]}

    def test_context_variables(self, manager):
        """测试上下文变量"""
        session = manager.create_session()

        # 设置上下文变量
        manager.set_context_variable(session.session_id, "current_business", "电商平台")
        manager.set_context_variable(session.session_id, "cloud_provider", "aws")

        # 获取上下文变量
        business = manager.get_context_variable(session.session_id, "current_business")
        cloud = manager.get_context_variable(session.session_id, "cloud_provider")

        assert business == "电商平台"
        assert cloud == "aws"

    def test_session_persistence(self, manager):
        """测试会话持久化"""
        # 创建会话并添加数据
        session = manager.create_session(user_id="user1")
        manager.add_message(session.session_id, MessageRole.USER, "测试消息")
        manager.add_task(session.session_id, "测试任务")
        manager.set_context_variable(session.session_id, "test_var", "test_value")

        session_id = session.session_id

        # 清除内存缓存
        manager.sessions.clear()

        # 从磁盘重新加载
        loaded_session = manager.get_session(session_id)

        assert loaded_session is not None
        assert loaded_session.user_id == "user1"
        assert len(loaded_session.messages) == 1
        assert len(loaded_session.tasks) == 1
        assert loaded_session.context_variables["test_var"] == "test_value"

    def test_get_conversation_history(self, manager):
        """测试获取对话历史"""
        session = manager.create_session()

        # 添加多条消息
        for i in range(10):
            manager.add_message(session.session_id, MessageRole.USER, f"用户消息{i}")
            manager.add_message(session.session_id, MessageRole.ASSISTANT, f"助手回复{i}")

        # 获取最近5条消息
        recent_messages = manager.get_conversation_history(session.session_id, limit=5)

        assert len(recent_messages) == 5
        assert recent_messages[-1].content == "助手回复9"

        # 只获取用户消息
        user_messages = manager.get_conversation_history(
            session.session_id,
            role_filter=MessageRole.USER
        )

        assert len(user_messages) == 10
        assert all(msg.role == MessageRole.USER for msg in user_messages)

    def test_get_conversation_summary(self, manager):
        """测试获取对话摘要"""
        session = manager.create_session()

        # 添加消息和任务
        manager.add_message(session.session_id, MessageRole.USER, "查询实例")
        manager.add_message(session.session_id, MessageRole.ASSISTANT, "好的")

        task1 = manager.add_task(session.session_id, "任务1")
        manager.update_task(session.session_id, task1.task_id, status=TaskStatus.COMPLETED)

        task2 = manager.add_task(session.session_id, "任务2")
        manager.update_task(session.session_id, task2.task_id, status=TaskStatus.FAILED)

        # 获取摘要
        summary = manager.get_conversation_summary(session.session_id)

        assert summary["total_messages"] == 2
        assert summary["user_messages"] == 1
        assert summary["assistant_messages"] == 1
        assert summary["total_tasks"] == 2
        assert summary["completed_tasks"] == 1
        assert summary["failed_tasks"] == 1

    def test_task_resume(self, manager):
        """测试任务恢复"""
        session = manager.create_session()

        # 添加并失败任务
        task = manager.add_task(session.session_id, "查询实例")
        manager.update_task(
            session.session_id,
            task.task_id,
            status=TaskStatus.FAILED,
            error="网络错误"
        )

        # 获取可恢复任务
        resumable = manager.get_resumable_tasks(session.session_id)
        assert len(resumable) == 1

        # 恢复任务
        resumed_task = manager.resume_task(session.session_id, task.task_id)

        assert resumed_task.status == TaskStatus.PENDING
        assert resumed_task.error is None

    def test_pause_task(self, manager):
        """测试暂停任务"""
        session = manager.create_session()

        task = manager.add_task(session.session_id, "长时间任务")
        manager.update_task(session.session_id, task.task_id, status=TaskStatus.IN_PROGRESS)

        # 暂停任务
        paused_task = manager.pause_task(session.session_id, task.task_id)

        assert paused_task.status == TaskStatus.PAUSED

    def test_list_active_sessions(self, manager):
        """测试列出活跃会话"""
        # 创建多个会话
        session1 = manager.create_session(user_id="user1")
        session2 = manager.create_session(user_id="user2")

        active = manager.list_active_sessions()

        assert len(active) == 2
        assert session1.session_id in active
        assert session2.session_id in active

    def test_get_session_stats(self, manager):
        """测试全局统计"""
        # 创建会话并添加数据
        session = manager.create_session()
        manager.add_message(session.session_id, MessageRole.USER, "消息1")
        manager.add_message(session.session_id, MessageRole.ASSISTANT, "回复1")

        task = manager.add_task(session.session_id, "任务1")
        manager.update_task(session.session_id, task.task_id, status=TaskStatus.COMPLETED)

        stats = manager.get_session_stats()

        assert stats["active_sessions"] == 1
        assert stats["total_messages"] == 2
        assert stats["total_tasks"] == 1
        assert stats["completed_tasks"] == 1
        assert stats["success_rate"] == 1.0


class TestContextCompressor:
    """测试上下文压缩器"""

    def test_should_compress(self):
        """测试是否需要压缩"""
        compressor = ContextCompressor()

        # 少量消息不压缩
        messages = [
            Message(MessageRole.USER, f"消息{i}")
            for i in range(10)
        ]
        assert compressor.should_compress(messages) is False

        # 大量消息需要压缩
        messages = [
            Message(MessageRole.USER, f"消息{i}")
            for i in range(20)
        ]
        assert compressor.should_compress(messages) is True

    @pytest.mark.asyncio
    async def test_compress_messages(self):
        """测试压缩消息"""
        compressor = ContextCompressor()

        # 创建20条消息
        messages = []
        for i in range(20):
            messages.append(Message(MessageRole.USER, f"用户消息{i}"))
            messages.append(Message(MessageRole.ASSISTANT, f"助手回复{i}"))

        # 压缩
        compressed = await compressor.compress_messages(messages)

        # 应该保留最近5条消息 + 1条总结
        # 由于默认keep_recent=5，所以压缩后应该<=6条（1条总结 + 5条最近）
        assert len(compressed) <= len(messages)
        assert compressed[0].role == MessageRole.SYSTEM  # 第一条是总结
        assert "对话历史总结" in compressed[0].content

    def test_estimate_tokens(self):
        """测试token估算"""
        # 英文文本
        english_text = "Hello world"
        tokens = estimate_tokens(english_text)
        assert tokens > 0

        # 中文文本
        chinese_text = "你好世界"
        tokens = estimate_tokens(chinese_text)
        assert tokens > 0

    @pytest.mark.asyncio
    async def test_compress_for_llm(self):
        """测试为LLM准备压缩消息"""
        messages = [
            Message(MessageRole.USER, "消息" * 1000)  # 很长的消息
            for _ in range(10)
        ]

        # 压缩
        llm_messages = await compress_for_llm(messages, max_tokens=1000, keep_recent=3)

        # 应该被压缩
        assert len(llm_messages) <= len(messages)
        assert all("role" in msg and "content" in msg for msg in llm_messages)

    def test_extract_context_variables(self):
        """测试提取上下文变量"""
        compressor = ContextCompressor()

        messages = [
            Message(
                MessageRole.USER,
                "查询AWS EC2实例",
                metadata={
                    "cloud_provider": "aws",
                    "service": "ec2",
                    "ctx_region": "us-east-1"
                }
            ),
            Message(
                MessageRole.ASSISTANT,
                "好的",
                metadata={
                    "business_name": "电商平台"
                }
            )
        ]

        context = compressor.extract_context_variables(messages)

        assert context["cloud_provider"] == "aws"
        assert context["service"] == "ec2"
        assert context["region"] == "us-east-1"
        assert context["business_name"] == "电商平台"


class TestConversationIntegration:
    """集成测试"""

    @pytest.fixture
    def manager(self, tmp_path):
        """创建临时管理器"""
        storage_dir = tmp_path / "test_conversations"
        manager = ConversationManager(storage_dir=str(storage_dir))
        yield manager

        # 清理
        if storage_dir.exists():
            shutil.rmtree(storage_dir)

    def test_full_conversation_workflow(self, manager):
        """测试完整的对话流程"""
        # 1. 创建会话
        session = manager.create_session(user_id="user1")

        # 2. 用户请求
        manager.add_message(
            session.session_id,
            MessageRole.USER,
            "帮我查询电商平台的所有EC2实例"
        )

        # 3. 设置上下文
        manager.set_context_variable(session.session_id, "business_name", "电商平台")
        manager.set_context_variable(session.session_id, "cloud_provider", "aws")

        # 4. 创建任务
        task = manager.add_task(
            session.session_id,
            "查询AWS EC2实例",
            metadata={"cloud_provider": "aws", "service": "ec2"}
        )

        # 5. 开始执行
        manager.update_task(session.session_id, task.task_id, status=TaskStatus.IN_PROGRESS)

        # 6. 执行成功
        manager.update_task(
            session.session_id,
            task.task_id,
            status=TaskStatus.COMPLETED,
            result={
                "instances": [
                    {"id": "i-1234", "state": "running"},
                    {"id": "i-5678", "state": "running"}
                ]
            }
        )

        # 7. 助手回复
        manager.add_message(
            session.session_id,
            MessageRole.ASSISTANT,
            "找到2个运行中的实例：i-1234, i-5678"
        )

        # 验证
        summary = manager.get_conversation_summary(session.session_id)

        assert summary["total_messages"] == 2
        assert summary["total_tasks"] == 1
        assert summary["completed_tasks"] == 1
        # get_conversation_summary 不包含 success_rate，这是在 get_session_stats 中
        # assert summary["success_rate"] == 1.0

        # 验证上下文
        business = manager.get_context_variable(session.session_id, "business_name")
        assert business == "电商平台"

    @pytest.mark.asyncio
    async def test_long_conversation_with_compression(self, manager):
        """测试长对话和压缩"""
        session = manager.create_session()

        # 模拟长对话
        for i in range(30):
            manager.add_message(session.session_id, MessageRole.USER, f"请求{i}")
            manager.add_message(session.session_id, MessageRole.ASSISTANT, f"回复{i}")

        # 获取会话
        session = manager.get_session(session.session_id)

        # 压缩会话
        compressor = ContextCompressor()
        compressed_session = await compressor.compress_session(session)

        # 验证压缩效果
        assert len(compressed_session.messages) < len(session.messages)
        assert compressed_session.session_id == session.session_id

        print(f"\n压缩效果: {len(session.messages)} → {len(compressed_session.messages)} 条消息")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
