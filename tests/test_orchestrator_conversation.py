"""
测试Orchestrator与ConversationManager的集成
"""
import pytest
import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import shutil

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import MultiCloudOrchestrator
from services.conversation_manager import MessageRole, TaskStatus


class TestOrchestratorConversationIntegration:
    """测试Orchestrator与ConversationManager的集成"""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """创建测试用的Orchestrator实例"""
        # 使用临时目录存储会话
        storage_dir = tmp_path / "conversations"

        with patch.object(MultiCloudOrchestrator, '__init__', lambda self: None):
            orch = MultiCloudOrchestrator()

            # 手动初始化必要的组件
            from services.conversation_manager import ConversationManager
            from config import get_config

            orch.config = get_config()
            orch.conversation_manager = ConversationManager(storage_dir=str(storage_dir))

            # Mock其他组件
            orch.manager_agent = Mock()
            orch.manager_agent.safe_process = AsyncMock(return_value=Mock(
                success=True,
                data={
                    "intent": {
                        "cloud_provider": "aws",
                        "service": "ec2",
                        "operation": "list_instances"
                    },
                    "execution_plan": {
                        "has_existing_api": True,
                        "requires_spec_fetch": False
                    }
                }
            ))

            orch.tool_registry = Mock()
            orch.tool_registry.call = AsyncMock(return_value={
                "success": True,
                "instances": ["i-1234", "i-5678"]
            })

            yield orch

            # 清理
            if storage_dir.exists():
                shutil.rmtree(storage_dir)

    @pytest.mark.asyncio
    async def test_process_request_creates_session(self, orchestrator):
        """测试处理请求时创建会话"""
        # 不提供session_id，应该自动创建
        result = await orchestrator.process_request(
            "列出所有EC2实例",
            user_id="test_user"
        )

        assert result["success"] is True
        assert "session_id" in result

        # 验证会话已创建
        session = orchestrator.conversation_manager.get_session(result["session_id"])
        assert session is not None
        assert session.user_id == "test_user"

    @pytest.mark.asyncio
    async def test_process_request_adds_messages(self, orchestrator):
        """测试处理请求时添加消息"""
        result = await orchestrator.process_request("列出所有EC2实例")

        session_id = result["session_id"]
        messages = orchestrator.conversation_manager.get_conversation_history(session_id)

        # 应该有2条消息：用户消息 + 助手回复
        assert len(messages) == 2
        assert messages[0].role == MessageRole.USER
        assert messages[0].content == "列出所有EC2实例"
        assert messages[1].role == MessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_process_request_reuses_session(self, orchestrator):
        """测试重用现有会话"""
        # 第一次请求
        result1 = await orchestrator.process_request("列出所有EC2实例")
        session_id = result1["session_id"]

        # 第二次请求，使用相同session_id
        result2 = await orchestrator.process_request(
            "停止实例i-1234",
            session_id=session_id
        )

        # 应该使用同一个会话
        assert result2["session_id"] == session_id

        # 会话中应该有4条消息
        messages = orchestrator.conversation_manager.get_conversation_history(session_id)
        assert len(messages) == 4

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, orchestrator):
        """测试获取对话历史"""
        # 创建会话并发送消息
        result = await orchestrator.process_request("列出所有EC2实例")
        session_id = result["session_id"]

        # 获取历史
        history = orchestrator.get_conversation_history(session_id)

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert "timestamp" in history[0]
        assert "metadata" in history[0]

    @pytest.mark.asyncio
    async def test_get_conversation_history_with_limit(self, orchestrator):
        """测试限制返回的对话历史数量"""
        result = await orchestrator.process_request("列出所有EC2实例")
        session_id = result["session_id"]

        # 再发送一次请求
        await orchestrator.process_request("停止实例i-1234", session_id=session_id)

        # 只获取最近1条消息
        history = orchestrator.get_conversation_history(session_id, limit=1)

        assert len(history) == 1
        assert history[0]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_health_check_includes_conversation_stats(self, orchestrator):
        """测试健康检查包含会话统计"""
        # 创建一些会话
        await orchestrator.process_request("测试消息1")
        await orchestrator.process_request("测试消息2")

        # 直接调用conversation_manager的统计方法
        stats = orchestrator.conversation_manager.get_session_stats()

        assert stats["active_sessions"] == 2
        assert stats["total_messages"] == 4  # 每个会话2条消息
        assert stats["total_tasks"] == 0  # 使用现有API不创建任务

    @pytest.mark.asyncio
    async def test_get_session(self, orchestrator):
        """测试获取会话"""
        result = await orchestrator.process_request("测试消息")
        session_id = result["session_id"]

        session = orchestrator.get_session(session_id)

        assert session is not None
        assert session.session_id == session_id
        assert len(session.messages) == 2

    @pytest.mark.asyncio
    async def test_error_handling_adds_error_message(self, orchestrator):
        """测试错误处理时添加错误消息"""
        # Mock manager_agent抛出异常
        orchestrator.manager_agent.safe_process = AsyncMock(side_effect=Exception("测试错误"))

        result = await orchestrator.process_request("测试消息")

        assert result["success"] is False
        assert "session_id" in result

        # 检查会话中的消息
        messages = orchestrator.conversation_manager.get_conversation_history(result["session_id"])

        # 应该有2条消息：用户消息 + 错误消息
        assert len(messages) == 2
        assert messages[0].role == MessageRole.USER
        assert messages[1].role == MessageRole.ASSISTANT
        assert "错误" in messages[1].content


class TestOrchestratorTaskIntegration:
    """测试Orchestrator中的任务管理"""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """创建测试用的Orchestrator实例（代码生成场景）"""
        storage_dir = tmp_path / "conversations"

        with patch.object(MultiCloudOrchestrator, '__init__', lambda self: None):
            orch = MultiCloudOrchestrator()

            from services.conversation_manager import ConversationManager
            from config import get_config

            orch.config = get_config()
            orch.conversation_manager = ConversationManager(storage_dir=str(storage_dir))

            # Mock manager_agent返回需要代码生成的执行计划
            orch.manager_agent = Mock()
            orch.manager_agent.safe_process = AsyncMock(return_value=Mock(
                success=True,
                data={
                    "intent": {
                        "cloud_provider": "aws",
                        "service": "s3",
                        "operation": "upload_file",
                        "parameters": {"bucket": "test-bucket"}
                    },
                    "execution_plan": {
                        "has_existing_api": False,  # 需要代码生成
                        "requires_spec_fetch": True
                    }
                }
            ))

            # Mock spec_doc_agent
            orch.spec_doc_agent = Mock()
            orch.spec_doc_agent.safe_process = AsyncMock(return_value=Mock(
                success=True,
                data={"specifications": {"operations": []}}
            ))

            # Mock rag_system
            orch.rag_system = Mock()
            orch.rag_system.index_documents = AsyncMock(return_value={"success": True})

            # Mock code_gen_agent
            orch.code_gen_agent = Mock()
            orch.code_gen_agent.safe_process = AsyncMock(return_value=Mock(
                success=True,
                data={"code": "print('test')"}
            ))

            # Mock sandbox
            orch.sandbox = Mock()
            orch.sandbox.test_code = AsyncMock(return_value={"success": True})
            orch.sandbox.execute_code = AsyncMock(return_value={
                "success": True,
                "output": "执行成功"
            })

            yield orch

            if storage_dir.exists():
                shutil.rmtree(storage_dir)

    @pytest.mark.asyncio
    async def test_code_generation_creates_task(self, orchestrator):
        """测试代码生成时创建任务"""
        result = await orchestrator.process_request("上传文件到S3")

        session_id = result["session_id"]
        session = orchestrator.conversation_manager.get_session(session_id)

        # 应该创建了1个任务
        assert len(session.tasks) == 1

        task = session.tasks[0]
        assert task.status == TaskStatus.COMPLETED
        assert "aws" in task.description.lower()
        assert "s3" in task.description.lower()

    @pytest.mark.asyncio
    async def test_code_generation_task_success(self, orchestrator):
        """测试代码生成任务成功完成"""
        result = await orchestrator.process_request("上传文件到S3")

        session_id = result["session_id"]
        session = orchestrator.conversation_manager.get_session(session_id)

        task = session.tasks[0]
        assert task.status == TaskStatus.COMPLETED
        assert task.result is not None
        assert "output" in task.result

    @pytest.mark.asyncio
    async def test_code_generation_task_failure(self, orchestrator):
        """测试代码生成任务失败"""
        # Mock代码执行失败
        orchestrator.sandbox.execute_code = AsyncMock(return_value={
            "success": False,
            "error": "执行失败"
        })

        result = await orchestrator.process_request("上传文件到S3")

        session_id = result["session_id"]
        session = orchestrator.conversation_manager.get_session(session_id)

        task = session.tasks[0]
        assert task.status == TaskStatus.FAILED
        assert task.error is not None

    @pytest.mark.asyncio
    async def test_get_resumable_tasks(self, orchestrator):
        """测试获取可恢复任务"""
        # Mock代码执行失败
        orchestrator.sandbox.execute_code = AsyncMock(return_value={
            "success": False,
            "error": "执行失败"
        })

        result = await orchestrator.process_request("上传文件到S3")
        session_id = result["session_id"]

        # 获取可恢复任务
        resumable = orchestrator.get_resumable_tasks(session_id)

        assert len(resumable) == 1
        assert resumable[0]["status"] == "failed"
        assert "执行失败" in resumable[0]["error"]

    @pytest.mark.asyncio
    async def test_resume_task(self, orchestrator):
        """测试恢复任务"""
        # 先创建一个失败的任务
        orchestrator.sandbox.execute_code = AsyncMock(return_value={
            "success": False,
            "error": "执行失败"
        })

        result = await orchestrator.process_request("上传文件到S3")
        session_id = result["session_id"]

        resumable = orchestrator.get_resumable_tasks(session_id)
        task_id = resumable[0]["task_id"]

        # 恢复任务
        resume_result = await orchestrator.resume_task(session_id, task_id)

        assert resume_result["success"] is True
        assert "task" in resume_result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
