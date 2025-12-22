"""
对话管理器
支持多轮对话、上下文管理和任务续传
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import json
import logging
import uuid
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    description: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskContext':
        """从字典创建"""
        return cls(
            task_id=data["task_id"],
            description=data["description"],
            status=TaskStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class ConversationSession:
    """对话会话"""
    session_id: str
    user_id: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tasks: List[TaskContext] = field(default_factory=list)
    context_variables: Dict[str, Any] = field(default_factory=dict)  # 上下文变量
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: MessageRole, content: str, metadata: Optional[Dict[str, Any]] = None):
        """添加消息"""
        message = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(message)
        self.updated_at = datetime.now()

    def add_task(self, description: str, task_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> TaskContext:
        """添加任务"""
        task = TaskContext(
            task_id=task_id or str(uuid.uuid4()),
            description=description,
            status=TaskStatus.PENDING,
            metadata=metadata or {}
        )
        self.tasks.append(task)
        self.updated_at = datetime.now()
        return task

    def update_task(self, task_id: str, status: Optional[TaskStatus] = None,
                   result: Optional[Any] = None, error: Optional[str] = None):
        """更新任务状态"""
        for task in self.tasks:
            if task.task_id == task_id:
                if status:
                    task.status = status
                if result is not None:
                    task.result = result
                if error:
                    task.error = error
                task.updated_at = datetime.now()
                self.updated_at = datetime.now()
                return task
        raise ValueError(f"Task {task_id} not found")

    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """获取最近的n条消息"""
        return self.messages[-n:]

    def get_pending_tasks(self) -> List[TaskContext]:
        """获取待处理任务"""
        return [task for task in self.tasks if task.status == TaskStatus.PENDING]

    def get_active_context(self) -> Dict[str, Any]:
        """获取活跃上下文（最近的消息和任务）"""
        return {
            "recent_messages": [msg.to_dict() for msg in self.get_recent_messages(5)],
            "pending_tasks": [task.to_dict() for task in self.get_pending_tasks()],
            "context_variables": self.context_variables
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "tasks": [task.to_dict() for task in self.tasks],
            "context_variables": self.context_variables,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationSession':
        """从字典创建"""
        return cls(
            session_id=data["session_id"],
            user_id=data.get("user_id"),
            messages=[Message.from_dict(msg) for msg in data.get("messages", [])],
            tasks=[TaskContext.from_dict(task) for task in data.get("tasks", [])],
            context_variables=data.get("context_variables", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {})
        )


class ConversationManager:
    """
    对话管理器

    功能：
    1. 管理多个用户的会话
    2. 跟踪对话历史
    3. 上下文变量管理
    4. 任务状态跟踪
    5. 会话持久化
    """

    def __init__(self, storage_dir: str = "data/conversations"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 内存中的会话缓存
        self.sessions: Dict[str, ConversationSession] = {}

        # 会话过期时间（默认24小时）
        self.session_ttl = timedelta(hours=24)

    def create_session(self, user_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ConversationSession:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = ConversationSession(
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {}
        )

        self.sessions[session_id] = session
        self._save_session(session)

        logger.info(f"创建新会话: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """获取会话"""
        # 先从内存缓存获取
        if session_id in self.sessions:
            session = self.sessions[session_id]

            # 检查是否过期
            if datetime.now() - session.updated_at > self.session_ttl:
                logger.warning(f"会话 {session_id} 已过期")
                return None

            return session

        # 从磁盘加载
        session = self._load_session(session_id)
        if session:
            # 检查是否过期
            if datetime.now() - session.updated_at > self.session_ttl:
                logger.warning(f"会话 {session_id} 已过期")
                return None

            self.sessions[session_id] = session

        return session

    def get_or_create_session(self, session_id: Optional[str] = None, user_id: Optional[str] = None) -> ConversationSession:
        """获取或创建会话"""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session

        # 创建新会话
        return self.create_session(user_id=user_id)

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """添加消息到会话"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or expired")

        session.add_message(role, content, metadata)
        self._save_session(session)

    def add_task(
        self,
        session_id: str,
        description: str,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TaskContext:
        """添加任务到会话"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or expired")

        task = session.add_task(description, task_id, metadata)
        self._save_session(session)
        return task

    def update_task(
        self,
        session_id: str,
        task_id: str,
        status: Optional[TaskStatus] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ):
        """更新任务状态"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or expired")

        task = session.update_task(task_id, status, result, error)
        self._save_session(session)
        return task

    def set_context_variable(self, session_id: str, key: str, value: Any):
        """设置上下文变量"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or expired")

        session.context_variables[key] = value
        session.updated_at = datetime.now()
        self._save_session(session)

    def get_context_variable(self, session_id: str, key: str, default: Any = None) -> Any:
        """获取上下文变量"""
        session = self.get_session(session_id)
        if not session:
            return default

        return session.context_variables.get(key, default)

    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
        role_filter: Optional[MessageRole] = None
    ) -> List[Message]:
        """获取对话历史"""
        session = self.get_session(session_id)
        if not session:
            return []

        messages = session.messages

        # 按角色过滤
        if role_filter:
            messages = [msg for msg in messages if msg.role == role_filter]

        # 限制数量
        if limit:
            messages = messages[-limit:]

        return messages

    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """获取对话摘要"""
        session = self.get_session(session_id)
        if not session:
            return {}

        total_messages = len(session.messages)
        user_messages = len([m for m in session.messages if m.role == MessageRole.USER])
        assistant_messages = len([m for m in session.messages if m.role == MessageRole.ASSISTANT])

        total_tasks = len(session.tasks)
        completed_tasks = len([t for t in session.tasks if t.status == TaskStatus.COMPLETED])
        failed_tasks = len([t for t in session.tasks if t.status == TaskStatus.FAILED])

        return {
            "session_id": session_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "total_messages": total_messages,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "pending_tasks": total_tasks - completed_tasks - failed_tasks
        }

    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]

        # 删除持久化文件
        session_file = self.storage_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()

        logger.info(f"清除会话: {session_id}")

    def list_active_sessions(self) -> List[str]:
        """列出活跃会话"""
        active_sessions = []

        # 扫描存储目录
        for session_file in self.storage_dir.glob("*.json"):
            session_id = session_file.stem
            session = self._load_session(session_id)

            if session and datetime.now() - session.updated_at <= self.session_ttl:
                active_sessions.append(session_id)

        return active_sessions

    def get_resumable_tasks(self, session_id: str) -> List[TaskContext]:
        """
        获取可恢复的任务（失败或暂停的任务）

        Args:
            session_id: 会话ID

        Returns:
            可恢复的任务列表
        """
        session = self.get_session(session_id)
        if not session:
            return []

        return [
            task for task in session.tasks
            if task.status in [TaskStatus.FAILED, TaskStatus.PAUSED]
        ]

    def resume_task(
        self,
        session_id: str,
        task_id: str,
        reset_error: bool = True
    ) -> Optional[TaskContext]:
        """
        恢复任务执行

        Args:
            session_id: 会话ID
            task_id: 任务ID
            reset_error: 是否清除之前的错误

        Returns:
            更新后的任务，如果任务不存在返回None
        """
        session = self.get_session(session_id)
        if not session:
            return None

        for task in session.tasks:
            if task.task_id == task_id:
                # 只能恢复失败或暂停的任务
                if task.status not in [TaskStatus.FAILED, TaskStatus.PAUSED]:
                    logger.warning(f"任务 {task_id} 状态为 {task.status.value}，无法恢复")
                    return None

                # 重置状态
                task.status = TaskStatus.PENDING
                if reset_error:
                    task.error = None
                task.updated_at = datetime.now()

                session.updated_at = datetime.now()
                self._save_session(session)

                logger.info(f"恢复任务 {task_id}")
                return task

        return None

    def pause_task(self, session_id: str, task_id: str) -> Optional[TaskContext]:
        """
        暂停任务

        Args:
            session_id: 会话ID
            task_id: 任务ID

        Returns:
            更新后的任务
        """
        return self.update_task(session_id, task_id, status=TaskStatus.PAUSED)

    def get_session_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        active_sessions = self.list_active_sessions()

        total_messages = 0
        total_tasks = 0
        completed_tasks = 0
        failed_tasks = 0

        for session_id in active_sessions:
            session = self.get_session(session_id)
            if session:
                total_messages += len(session.messages)
                total_tasks += len(session.tasks)
                completed_tasks += len([t for t in session.tasks if t.status == TaskStatus.COMPLETED])
                failed_tasks += len([t for t in session.tasks if t.status == TaskStatus.FAILED])

        return {
            "active_sessions": len(active_sessions),
            "total_messages": total_messages,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": completed_tasks / total_tasks if total_tasks > 0 else 0
        }

    def _save_session(self, session: ConversationSession):
        """保存会话到磁盘"""
        session_file = self.storage_dir / f"{session.session_id}.json"

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存会话失败: {e}")

    def _load_session(self, session_id: str) -> Optional[ConversationSession]:
        """从磁盘加载会话"""
        session_file = self.storage_dir / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return ConversationSession.from_dict(data)
        except Exception as e:
            logger.error(f"加载会话失败: {e}")
            return None


# 全局会话管理器实例
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """获取全局会话管理器"""
    global _conversation_manager

    if _conversation_manager is None:
        _conversation_manager = ConversationManager()

    return _conversation_manager
