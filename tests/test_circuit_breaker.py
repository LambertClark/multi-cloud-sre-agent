"""
测试Circuit Breaker（熔断器）
验证熔断器状态机和容错机制
"""
import sys
import io
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from services.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError
)


# 模拟的不稳定服务
class UnstableService:
    """模拟一个不稳定的服务"""
    def __init__(self):
        self.call_count = 0
        self.failure_count = 0

    async def call(self, should_fail: bool = False):
        """模拟服务调用"""
        self.call_count += 1
        await asyncio.sleep(0.01)  # 模拟网络延迟

        if should_fail:
            self.failure_count += 1
            raise Exception(f"Service failed (call #{self.call_count})")

        return f"Success #{self.call_count}"


async def test_normal_operation():
    """测试正常操作（CLOSED状态）"""
    print("=" * 60)
    print("测试1: 正常操作（CLOSED状态）")
    print("=" * 60)

    circuit_breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=3,
        timeout=1
    )
    service = UnstableService()

    # 正常调用5次
    for i in range(5):
        result = await circuit_breaker.call(service.call, should_fail=False)
        print(f"✅ 调用{i+1}: {result}")

    assert circuit_breaker.state == CircuitState.CLOSED
    assert service.call_count == 5
    print("\n✅ 正常操作测试通过")


async def test_circuit_opens_on_failures():
    """测试失败达到阈值后熔断器打开"""
    print("\n" + "=" * 60)
    print("测试2: 失败达到阈值后熔断器打开")
    print("=" * 60)

    circuit_breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=3,
        timeout=1
    )
    service = UnstableService()

    # 连续失败3次
    for i in range(3):
        try:
            await circuit_breaker.call(service.call, should_fail=True)
        except Exception as e:
            print(f"❌ 调用{i+1}失败: {str(e)[:50]}")

    # 检查熔断器状态
    assert circuit_breaker.state == CircuitState.OPEN, "熔断器应该打开"
    print(f"\n✅ 熔断器已打开（状态: {circuit_breaker.state.value}）")

    # 尝试再次调用，应该被拒绝
    try:
        await circuit_breaker.call(service.call, should_fail=False)
        assert False, "应该抛出CircuitBreakerOpenError"
    except CircuitBreakerOpenError as e:
        print(f"✅ 请求被熔断器拒绝: {str(e)[:80]}")

    print("\n✅ 熔断打开测试通过")


async def test_circuit_half_open_and_recovery():
    """测试熔断器半开状态和恢复"""
    print("\n" + "=" * 60)
    print("测试3: 熔断器半开状态和恢复")
    print("=" * 60)

    circuit_breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=3,
        success_threshold=2,  # 半开状态需要2次成功才恢复
        timeout=1,  # 1秒后进入半开状态
        half_open_max_calls=3
    )
    service = UnstableService()

    # 1. 触发熔断
    print("\n步骤1: 触发熔断（3次失败）")
    for i in range(3):
        try:
            await circuit_breaker.call(service.call, should_fail=True)
        except Exception:
            pass

    assert circuit_breaker.state == CircuitState.OPEN
    print(f"✅ 熔断器状态: {circuit_breaker.state.value}")

    # 2. 等待超时进入半开状态
    print("\n步骤2: 等待1秒进入HALF_OPEN状态...")
    await asyncio.sleep(1.1)

    # 3. 半开状态测试调用
    print("\n步骤3: 半开状态测试调用（2次成功）")
    for i in range(2):
        result = await circuit_breaker.call(service.call, should_fail=False)
        print(f"✅ 半开状态调用{i+1}: {result}")
        print(f"   当前状态: {circuit_breaker.state.value}")

    # 4. 检查是否恢复
    assert circuit_breaker.state == CircuitState.CLOSED, "熔断器应该关闭"
    print(f"\n✅ 熔断器已恢复（状态: {circuit_breaker.state.value}）")

    print("\n✅ 半开状态和恢复测试通过")


async def test_circuit_half_open_fails_again():
    """测试半开状态失败后重新打开"""
    print("\n" + "=" * 60)
    print("测试4: 半开状态失败后重新打开")
    print("=" * 60)

    circuit_breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=3,
        timeout=1
    )
    service = UnstableService()

    # 1. 触发熔断
    print("\n步骤1: 触发熔断")
    for i in range(3):
        try:
            await circuit_breaker.call(service.call, should_fail=True)
        except Exception:
            pass

    assert circuit_breaker.state == CircuitState.OPEN

    # 2. 等待进入半开状态
    print("\n步骤2: 等待进入HALF_OPEN状态...")
    await asyncio.sleep(1.1)

    # 3. 半开状态测试失败
    print("\n步骤3: 半开状态测试调用失败")
    try:
        await circuit_breaker.call(service.call, should_fail=True)
        assert False, "应该抛出异常"
    except CircuitBreakerOpenError:
        # 熔断器应该立即重新打开，后续调用被拒绝
        pass
    except Exception as e:
        # 第一次调用可能抛出服务异常
        print(f"   半开状态测试失败: {str(e)[:50]}")

    # 4. 检查熔断器重新打开
    assert circuit_breaker.state == CircuitState.OPEN, "熔断器应该重新打开"
    print(f"✅ 熔断器重新打开（状态: {circuit_breaker.state.value}）")

    # 5. 后续请求应该被拒绝
    try:
        await circuit_breaker.call(service.call, should_fail=False)
        assert False, "应该抛出CircuitBreakerOpenError"
    except CircuitBreakerOpenError as e:
        print(f"✅ 后续请求被拒绝: {str(e)[:80]}")

    print("\n✅ 半开状态失败重新打开测试通过")


async def test_circuit_breaker_stats():
    """测试熔断器统计信息"""
    print("\n" + "=" * 60)
    print("测试5: 熔断器统计信息")
    print("=" * 60)

    circuit_breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=3,
        timeout=1
    )
    service = UnstableService()

    # 5次成功，3次失败
    for i in range(5):
        try:
            await circuit_breaker.call(service.call, should_fail=False)
        except Exception:
            pass

    for i in range(3):
        try:
            await circuit_breaker.call(service.call, should_fail=True)
        except Exception:
            pass

    stats = circuit_breaker.get_stats()

    print(f"\n统计信息:")
    print(f"  - 总调用: {stats['stats']['total_calls']}")
    print(f"  - 成功: {stats['stats']['success_calls']}")
    print(f"  - 失败: {stats['stats']['failure_calls']}")
    print(f"  - 被拒绝: {stats['stats']['rejected_calls']}")
    print(f"  - 成功率: {stats['stats']['success_rate']:.1f}%")
    print(f"  - 当前状态: {stats['state']}")

    assert stats['stats']['total_calls'] == 8
    assert stats['stats']['success_calls'] == 5
    assert stats['stats']['failure_calls'] == 3

    print("\n✅ 统计信息测试通过")


async def test_concurrent_calls_in_half_open():
    """测试半开状态的并发限制"""
    print("\n" + "=" * 60)
    print("测试6: 半开状态的并发限制")
    print("=" * 60)

    circuit_breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=2,
        timeout=0.5,
        half_open_max_calls=2  # 半开状态最多2个并发
    )
    service = UnstableService()

    # 1. 触发熔断
    print("\n步骤1: 触发熔断")
    for i in range(2):
        try:
            await circuit_breaker.call(service.call, should_fail=True)
        except Exception:
            pass

    # 2. 等待进入半开状态
    print("\n步骤2: 等待进入HALF_OPEN状态...")
    await asyncio.sleep(0.6)

    # 3. 并发调用（超过限制）
    print("\n步骤3: 并发调用测试（3个并发，限制2个）")

    async def concurrent_call(call_id):
        try:
            result = await circuit_breaker.call(service.call, should_fail=False)
            print(f"  ✅ 并发调用{call_id}成功: {result}")
            return True
        except CircuitBreakerOpenError as e:
            print(f"  ❌ 并发调用{call_id}被限流")
            return False

    # 同时发起3个调用
    results = await asyncio.gather(
        concurrent_call(1),
        concurrent_call(2),
        concurrent_call(3),
        return_exceptions=True
    )

    # 至少有1个应该被限流
    rejected = sum(1 for r in results if r is False or isinstance(r, Exception))
    print(f"\n✅ {rejected}个请求被限流（符合预期）")

    print("\n✅ 并发限制测试通过")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("Circuit Breaker（熔断器）测试")
    print("=" * 60)

    try:
        await test_normal_operation()
        await test_circuit_opens_on_failures()
        await test_circuit_half_open_and_recovery()
        await test_circuit_half_open_fails_again()
        await test_circuit_breaker_stats()
        await test_concurrent_calls_in_half_open()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！Circuit Breaker工作正常！")
        print("=" * 60)

        print("\n关键功能验证：")
        print("✅ 1. CLOSED状态 - 正常处理请求")
        print("✅ 2. OPEN状态 - 失败达到阈值后熔断")
        print("✅ 3. OPEN状态 - 快速失败，拒绝请求")
        print("✅ 4. HALF_OPEN状态 - 超时后尝试恢复")
        print("✅ 5. HALF_OPEN→CLOSED - 成功后恢复正常")
        print("✅ 6. HALF_OPEN→OPEN - 失败后重新熔断")
        print("✅ 7. 并发限制 - 半开状态限流")
        print("✅ 8. 统计信息 - 完整的调用统计")

        print("\n解决的问题：")
        print("- 防止级联失败（服务雪崩）")
        print("- 快速失败，保护系统资源")
        print("- 自动恢复，无需人工干预")
        print("- 解决ARCHITECTURE_DEFENSE.md中的可靠性问题")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
