"""
Circuit Breaker（熔断器）
防止级联失败，实现快速失败和自动恢复
"""
import time
import asyncio
import logging
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"          # 正常状态，允许请求通过
    OPEN = "open"              # 熔断状态，拒绝请求（快速失败）
    HALF_OPEN = "half_open"    # 半开状态，允许少量请求测试服务是否恢复


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass


@dataclass
class CircuitBreakerStats:
    """熔断器统计信息"""
    total_calls: int = 0
    success_calls: int = 0
    failure_calls: int = 0
    rejected_calls: int = 0  # 被熔断器拒绝的调用
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changed_at: Optional[datetime] = None


class CircuitBreaker:
    """
    Circuit Breaker（熔断器）模式

    防止系统雪崩：
    1. 当失败次数达到阈值时，打开熔断器（OPEN）
    2. 熔断器打开后，直接拒绝请求（快速失败，不消耗资源）
    3. 超时后进入半开状态（HALF_OPEN），允许少量请求测试服务
    4. 测试成功后关闭熔断器（CLOSED），恢复正常

    使用示例：
    ```python
    circuit_breaker = CircuitBreaker(
        name="llm_service",
        failure_threshold=5,  # 5次失败后熔断
        timeout=60            # 熔断60秒后尝试恢复
    )

    async def call_llm():
        return await circuit_breaker.call(llm.ainvoke, messages)
    ```
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,       # 失败阈值：连续失败多少次后熔断
        success_threshold: int = 2,       # 成功阈值：半开状态下成功多少次后关闭
        timeout: int = 60,                # 熔断超时（秒）：多久后从OPEN进入HALF_OPEN
        half_open_max_calls: int = 3,     # 半开状态最大并发请求数
        excluded_exceptions: tuple = ()   # 不计入失败的异常类型
    ):
        """
        初始化熔断器

        Args:
            name: 熔断器名称（用于日志）
            failure_threshold: 失败阈值
            success_threshold: 恢复阈值
            timeout: 熔断超时（秒）
            half_open_max_calls: 半开状态最大请求数
            excluded_exceptions: 不触发熔断的异常（如参数错误）
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        self.excluded_exceptions = excluded_exceptions

        # 状态
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0  # 半开状态下的并发请求数

        # 统计
        self.stats = CircuitBreakerStats(
            state_changed_at=datetime.now()
        )

        # 锁（保护状态变更）
        self._lock = asyncio.Lock()

        logger.info(
            f"熔断器 '{self.name}' 已初始化 "
            f"(failure_threshold={failure_threshold}, timeout={timeout}s)"
        )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器调用函数

        Args:
            func: 要调用的函数（可以是async函数）
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器打开时
            原始异常: 函数执行失败时
        """
        # 检查熔断器状态
        await self._check_state()

        if self.state == CircuitState.OPEN:
            # 熔断器打开，直接拒绝
            self.stats.rejected_calls += 1
            logger.warning(
                f"熔断器 '{self.name}' 处于OPEN状态，拒绝请求 "
                f"(已拒绝 {self.stats.rejected_calls} 次)"
            )
            raise CircuitBreakerOpenError(
                f"熔断器 '{self.name}' 打开，服务不可用 "
                f"(将在 {self._get_remaining_timeout():.1f}秒后尝试恢复)"
            )

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态，限制并发
            async with self._lock:
                if self.half_open_calls >= self.half_open_max_calls:
                    self.stats.rejected_calls += 1
                    logger.warning(
                        f"熔断器 '{self.name}' 处于HALF_OPEN状态，"
                        f"并发已达上限 ({self.half_open_max_calls})，拒绝请求"
                    )
                    raise CircuitBreakerOpenError(
                        f"熔断器 '{self.name}' 半开状态，请求限流"
                    )
                self.half_open_calls += 1

        # 执行调用
        try:
            self.stats.total_calls += 1
            start_time = time.time()

            # 支持同步和异步函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            elapsed = time.time() - start_time
            await self._on_success(elapsed)

            return result

        except Exception as e:
            # 检查是否是排除的异常
            if isinstance(e, self.excluded_exceptions):
                logger.debug(f"熔断器 '{self.name}': 排除异常 {type(e).__name__}，不计入失败")
                raise

            # 记录失败
            await self._on_failure(e)
            raise

        finally:
            # 减少半开状态的并发计数
            if self.state == CircuitState.HALF_OPEN:
                async with self._lock:
                    self.half_open_calls = max(0, self.half_open_calls - 1)

    async def _check_state(self):
        """检查并更新熔断器状态"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                # 检查是否到了恢复时间
                if self.stats.last_failure_time:
                    elapsed = (datetime.now() - self.stats.last_failure_time).total_seconds()
                    if elapsed >= self.timeout:
                        # 进入半开状态
                        self._transition_to(CircuitState.HALF_OPEN)

    async def _on_success(self, elapsed: float):
        """处理成功调用"""
        async with self._lock:
            self.stats.success_calls += 1
            self.stats.last_success_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                # 半开状态下的成功
                self.success_count += 1
                logger.info(
                    f"熔断器 '{self.name}' 半开状态测试成功 "
                    f"({self.success_count}/{self.success_threshold})"
                )

                if self.success_count >= self.success_threshold:
                    # 成功次数达到阈值，关闭熔断器
                    self._transition_to(CircuitState.CLOSED)
                    self.failure_count = 0
                    self.success_count = 0

            elif self.state == CircuitState.CLOSED:
                # 正常状态下的成功，重置失败计数
                self.failure_count = 0

    async def _on_failure(self, exception: Exception):
        """处理失败调用"""
        async with self._lock:
            self.stats.failure_calls += 1
            self.stats.last_failure_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即重新打开熔断器
                logger.warning(
                    f"熔断器 '{self.name}' 半开状态测试失败: {type(exception).__name__}"
                )
                self._transition_to(CircuitState.OPEN)
                self.success_count = 0

            elif self.state == CircuitState.CLOSED:
                # 正常状态下失败
                self.failure_count += 1
                logger.warning(
                    f"熔断器 '{self.name}' 调用失败 "
                    f"({self.failure_count}/{self.failure_threshold}): "
                    f"{type(exception).__name__}: {str(exception)[:100]}"
                )

                if self.failure_count >= self.failure_threshold:
                    # 失败次数达到阈值，打开熔断器
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        old_state = self.state
        self.state = new_state
        self.stats.state_changed_at = datetime.now()

        logger.warning(
            f"熔断器 '{self.name}' 状态变更: {old_state.value} → {new_state.value}"
        )

        if new_state == CircuitState.OPEN:
            logger.error(
                f"🔴 熔断器 '{self.name}' 已打开！"
                f"连续失败 {self.failure_count} 次，"
                f"将在 {self.timeout}秒后尝试恢复"
            )
        elif new_state == CircuitState.HALF_OPEN:
            logger.info(
                f"🟡 熔断器 '{self.name}' 进入半开状态，"
                f"允许最多 {self.half_open_max_calls} 个请求测试服务"
            )
        elif new_state == CircuitState.CLOSED:
            logger.info(
                f"🟢 熔断器 '{self.name}' 已关闭，服务恢复正常"
            )

    def _get_remaining_timeout(self) -> float:
        """获取剩余的熔断时间"""
        if self.stats.last_failure_time:
            elapsed = (datetime.now() - self.stats.last_failure_time).total_seconds()
            return max(0, self.timeout - elapsed)
        return 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "stats": {
                "total_calls": self.stats.total_calls,
                "success_calls": self.stats.success_calls,
                "failure_calls": self.stats.failure_calls,
                "rejected_calls": self.stats.rejected_calls,
                "success_rate": (
                    self.stats.success_calls / self.stats.total_calls * 100
                    if self.stats.total_calls > 0 else 0
                ),
            },
            "last_failure_time": (
                self.stats.last_failure_time.isoformat()
                if self.stats.last_failure_time else None
            ),
            "last_success_time": (
                self.stats.last_success_time.isoformat()
                if self.stats.last_success_time else None
            ),
            "state_changed_at": (
                self.stats.state_changed_at.isoformat()
                if self.stats.state_changed_at else None
            ),
            "remaining_timeout": self._get_remaining_timeout(),
        }

    def reset(self):
        """重置熔断器（用于测试或手动恢复）"""
        logger.info(f"手动重置熔断器 '{self.name}'")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.stats = CircuitBreakerStats(state_changed_at=datetime.now())
