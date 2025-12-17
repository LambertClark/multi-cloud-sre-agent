"""
增强版CodeGeneratorAgent ReAct测试
测试更多实际场景和错误恢复能力
"""
import asyncio
import sys
import os
import io
import time

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.code_generator_agent import CodeGeneratorAgent


async def test_simple_success():
    """场景1：简单需求，一次成功"""
    print("\n" + "=" * 70)
    print("场景1：简单需求 - 应该1次通过")
    print("=" * 70)

    agent = CodeGeneratorAgent()

    result = await agent.process_with_react({
        "requirement": "实现一个函数sum_list(numbers)，计算列表所有数字的和",
        "operation": "sum_list",
        "cloud_provider": "general",
        "service": "math",
        "parameters": {"numbers": [1, 2, 3, 4, 5]},
        "language": "python",
        "enable_auto_test": True
    })

    print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"迭代次数: {result.data.get('iterations') if result.data else 'N/A'}")

    if result.success:
        print(f"生成的代码长度: {len(result.data['code'])} 字符")
        assert result.data['iterations'] <= 2, "简单需求应该在2次内完成"
        print("✅ 场景1通过")
    else:
        error_msg = result.message or result.error or "Unknown error"
        print(f"失败原因: {error_msg}")
        print("⚠️ 场景1未通过（可能是API问题）")

    return result.success


async def test_no_auto_test():
    """场景2：禁用自动测试"""
    print("\n" + "=" * 70)
    print("场景2：禁用自动测试 - 应该直接返回")
    print("=" * 70)

    agent = CodeGeneratorAgent()

    result = await agent.process_with_react({
        "requirement": "实现一个函数max_value(numbers)，返回列表中的最大值",
        "operation": "max_value",
        "cloud_provider": "general",
        "service": "math",
        "parameters": {"numbers": [5, 2, 8, 1, 9]},
        "language": "python",
        "enable_auto_test": False  # 禁用测试
    })

    print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")

    if result.success:
        print(f"迭代次数: {result.data.get('iterations')}")
        assert result.data['iterations'] == 1, "禁用测试应该1次返回"
        print("✅ 场景2通过")
    else:
        error_msg = result.message or result.error or "Unknown error"
        print(f"失败原因: {error_msg}")
        print("⚠️ 场景2未通过")

    return result.success


async def test_react_history_tracking():
    """场景3：ReAct历史记录追踪"""
    print("\n" + "=" * 70)
    print("场景3：ReAct历史记录 - 验证记录完整性")
    print("=" * 70)

    agent = CodeGeneratorAgent()

    result = await agent.process_with_react({
        "requirement": "实现一个函数reverse_string(s)，反转字符串",
        "operation": "reverse_string",
        "cloud_provider": "general",
        "service": "string",
        "parameters": {"s": "hello"},
        "language": "python",
        "enable_auto_test": True
    })

    print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")

    if result.data and result.data.get("react_history"):
        history = result.data["react_history"]
        print(f"ReAct历史记录: {len(history)} 次迭代")

        for i, h in enumerate(history, 1):
            print(f"\n  迭代 {i}:")
            print(f"    Thought: {h['thought'][:80]}...")
            print(f"    Action: 代码{h['action']['code_length']}字符, 测试{h['action']['test_length']}字符")
            print(f"    Observation: {h['observation']['status']}")

            # 验证必要字段
            assert 'thought' in h, "缺少thought字段"
            assert 'action' in h, "缺少action字段"
            assert 'observation' in h, "缺少observation字段"
            assert 'iteration' in h, "缺少iteration字段"

        print("\n✅ 场景3通过 - 历史记录完整")
        return True
    else:
        print("⚠️ 场景3未通过 - 无历史记录")
        return False


async def test_medium_complexity():
    """场景4：中等复杂度需求"""
    print("\n" + "=" * 70)
    print("场景4：中等复杂度 - 排序和去重")
    print("=" * 70)

    agent = CodeGeneratorAgent()

    result = await agent.process_with_react({
        "requirement": "实现一个函数unique_sorted(numbers)，返回去重后的升序列表",
        "operation": "unique_sorted",
        "cloud_provider": "general",
        "service": "data",
        "parameters": {"numbers": [3, 1, 4, 1, 5, 9, 2, 6, 5]},
        "language": "python",
        "enable_auto_test": True
    })

    print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"迭代次数: {result.data.get('iterations') if result.data else 'N/A'}")

    if result.success:
        print(f"生成的代码预览:")
        print("-" * 50)
        print(result.data['code'][:300] + "...")
        print("-" * 50)
        assert result.data['iterations'] <= 3, "中等复杂度应该在3次内完成"
        print("✅ 场景4通过")
    else:
        error_msg = result.message or result.error or "Unknown error"
        print(f"失败原因: {error_msg}")
        print("⚠️ 场景4未通过")

    return result.success


async def test_error_recovery():
    """场景5：测试错误恢复（如果前面失败会重试）"""
    print("\n" + "=" * 70)
    print("场景5：错误恢复能力测试")
    print("=" * 70)

    agent = CodeGeneratorAgent()

    # 这个需求可能需要多次迭代
    result = await agent.process_with_react({
        "requirement": "实现一个函数is_palindrome(s)，判断字符串是否为回文（忽略大小写和空格）",
        "operation": "is_palindrome",
        "cloud_provider": "general",
        "service": "string",
        "parameters": {"s": "A man a plan a canal Panama"},
        "language": "python",
        "enable_auto_test": True
    })

    print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")

    if result.data:
        print(f"迭代次数: {result.data.get('iterations')}")

        if result.data.get('react_history'):
            print(f"\nReAct过程:")
            for h in result.data['react_history']:
                status = h['observation']['status']
                emoji = "✓" if status == "success" else "✗"
                print(f"  迭代{h['iteration']}: {emoji} {status}")

        if result.success:
            print("✅ 场景5通过 - 成功恢复")
        else:
            print(f"⚠️ 场景5未完全通过 - 达到最大迭代次数")

    return result.success


async def test_performance_metrics():
    """场景6：性能指标统计"""
    print("\n" + "=" * 70)
    print("场景6：性能指标统计")
    print("=" * 70)

    agent = CodeGeneratorAgent()

    start_time = time.time()

    result = await agent.process_with_react({
        "requirement": "实现一个函数factorial(n)，计算n的阶乘",
        "operation": "factorial",
        "cloud_provider": "general",
        "service": "math",
        "parameters": {"n": 5},
        "language": "python",
        "enable_auto_test": True
    })

    elapsed = time.time() - start_time

    print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"总耗时: {elapsed:.2f} 秒")

    if result.data:
        iterations = result.data.get('iterations', 0)
        print(f"迭代次数: {iterations}")
        print(f"平均每次迭代: {elapsed/iterations:.2f} 秒")

        if result.success:
            code_len = len(result.data['code'])
            test_len = len(result.data.get('test_code', ''))
            print(f"代码量: {code_len} 字符")
            print(f"测试代码量: {test_len} 字符")
            print(f"代码/测试比: {code_len/test_len:.2f}" if test_len > 0 else "N/A")

        print("✅ 场景6通过")

    return result.success


async def main():
    """运行所有增强测试"""
    print("=" * 70)
    print("CodeGeneratorAgent ReAct 增强测试套件")
    print("=" * 70)
    print("\n⚠️  提示：测试需要LLM API，可能需要3-5分钟")
    print("⚠️  为避免API频率限制，测试间会有短暂延迟")

    results = {
        "场景1_简单需求": False,
        "场景2_禁用测试": False,
        "场景3_历史记录": False,
        "场景4_中等复杂": False,
        "场景5_错误恢复": False,
        "场景6_性能指标": False,
    }

    try:
        # 场景1：简单需求
        results["场景1_简单需求"] = await test_simple_success()
        await asyncio.sleep(2)  # 避免API频率限制

        # 场景2：禁用自动测试
        results["场景2_禁用测试"] = await test_no_auto_test()
        await asyncio.sleep(2)

        # 场景3：历史记录
        results["场景3_历史记录"] = await test_react_history_tracking()
        await asyncio.sleep(2)

        # 场景4：中等复杂度
        results["场景4_中等复杂"] = await test_medium_complexity()
        await asyncio.sleep(2)

        # 场景5：错误恢复
        results["场景5_错误恢复"] = await test_error_recovery()
        await asyncio.sleep(2)

        # 场景6：性能指标
        results["场景6_性能指标"] = await test_performance_metrics()

    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()

    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for scenario, result in results.items():
        status = "✅ 通过" if result else "❌ 未通过"
        print(f"  {scenario}: {status}")

    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 所有测试通过！")
    elif passed >= total * 0.7:
        print(f"\n✅ 大部分测试通过 ({passed}/{total})")
    else:
        print(f"\n⚠️  多个测试未通过 ({passed}/{total})")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
