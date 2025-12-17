"""
Manager Agent ReAct单元测试
Mock LLM，快速验证逻辑
"""
import asyncio
import sys
import io
from unittest.mock import AsyncMock, MagicMock, patch

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.manager_agent import ManagerAgent
from agents.base_agent import AgentResponse


async def test_manager_react_iteration_control():
    """测试1：验证ReAct迭代控制逻辑"""
    print("\n=== 测试1：Manager Agent ReAct迭代控制 ===")

    manager = ManagerAgent()

    # Mock LLM返回：第一次调用返回"生成代码"，第二次调用返回"完成"
    mock_responses = [
        # 第1次迭代 - Thought
        MagicMock(content='```json\n{"thought": "需要生成代码", "action": {"type": "generate_code", "target": "code_generator", "parameters": {"operation": "add"}}, "is_final": false}\n```'),
        # 第2次迭代 - Thought
        MagicMock(content='```json\n{"thought": "任务完成", "action": {"type": "finish"}, "is_final": true}\n```'),
        # Final report
        MagicMock(content='任务已完成'),
    ]

    # Mock CodeGeneratorAgent.process
    mock_code_response = AgentResponse(
        success=True,
        data={"code": "def add(a, b): return a + b"}
    )

    with patch.object(manager, '_invoke_llm_with_retry', side_effect=mock_responses), \
         patch.object(manager.sub_agents['code_generator'], 'process', return_value=mock_code_response):

        result = await manager.process_with_react({
            "user_request": "生成加法函数"
        })

        print(f"结果: {result.success}")
        print(f"迭代次数: {result.data.get('iterations')}")

        assert result.success, "应该成功"
        assert result.data['iterations'] == 2, "应该2次迭代完成"
        assert len(result.data['react_history']) == 2, "应该有2条历史"

        print("✅ 测试1通过：ReAct迭代控制正确")


async def test_manager_max_iterations():
    """测试2：验证最大迭代次数限制"""
    print("\n=== 测试2：最大迭代次数限制 ===")

    manager = ManagerAgent()

    # Mock LLM总是返回"继续"动作，永不完成
    mock_response = MagicMock(content='```json\n{"thought": "继续分析", "action": {"type": "analyze", "parameters": {}}, "is_final": false}\n```')

    with patch.object(manager, '_invoke_llm_with_retry', return_value=mock_response):

        result = await manager.process_with_react({
            "user_request": "无尽任务",
            "max_iterations": 3
        })

        print(f"结果: {result.success}")
        print(f"迭代次数: {result.data.get('iterations')}")

        assert not result.success, "应该失败（达到最大迭代）"
        assert result.data['iterations'] == 3, "应该尝试3次"

        print("✅ 测试2通过：正确限制最大迭代次数")


async def test_manager_action_execution():
    """测试3：验证Action执行"""
    print("\n=== 测试3：Action执行 ===")

    manager = ManagerAgent()

    # Mock返回：生成代码 → 完成
    mock_responses = [
        MagicMock(content='```json\n{"thought": "生成代码", "action": {"type": "generate_code", "target": "code_generator", "parameters": {"operation": "test"}}, "is_final": false}\n```'),
        MagicMock(content='```json\n{"thought": "完成", "action": {"type": "finish"}, "is_final": true}\n```'),
        MagicMock(content='测试完成'),
    ]

    mock_code_response = AgentResponse(
        success=True,
        data={"code": "test_code"}
    )

    process_called = []

    async def mock_process(params):
        process_called.append(params)
        return mock_code_response

    with patch.object(manager, '_invoke_llm_with_retry', side_effect=mock_responses), \
         patch.object(manager.sub_agents['code_generator'], 'process', side_effect=mock_process):

        result = await manager.process_with_react({
            "user_request": "测试"
        })

        print(f"CodeGeneratorAgent被调用: {len(process_called)} 次")
        print(f"参数: {process_called}")

        assert len(process_called) == 1, "CodeGeneratorAgent应该被调用1次"
        assert result.success, "应该成功"

        print("✅ 测试3通过：Action执行正确")


async def test_manager_history_structure():
    """测试4：验证历史记录结构"""
    print("\n=== 测试4：历史记录结构 ===")

    manager = ManagerAgent()

    mock_responses = [
        MagicMock(content='```json\n{"thought": "思考内容", "action": {"type": "analyze", "parameters": {}}, "is_final": false}\n```'),
        MagicMock(content='```json\n{"thought": "完成", "action": {"type": "finish"}, "is_final": true}\n```'),
        MagicMock(content='分析结果'),
        MagicMock(content='报告'),
    ]

    with patch.object(manager, '_invoke_llm_with_retry', side_effect=mock_responses):

        result = await manager.process_with_react({
            "user_request": "测试历史"
        })

        history = result.data['react_history']

        # 验证第一条历史
        assert 'iteration' in history[0], "缺少iteration"
        assert 'thought' in history[0], "缺少thought"
        assert 'action' in history[0], "缺少action"
        assert 'observation' in history[0], "缺少observation"

        print(f"历史记录结构: {list(history[0].keys())}")
        print("✅ 测试4通过：历史记录结构完整")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("Manager Agent ReAct 单元测试")
    print("=" * 70)
    print("\n⚡ 快速测试（不需要LLM）")

    tests = [
        ("ReAct迭代控制", test_manager_react_iteration_control),
        ("最大迭代限制", test_manager_max_iterations),
        ("Action执行", test_manager_action_execution),
        ("历史记录结构", test_manager_history_structure),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ 测试失败: {name}")
            print(f"   原因: {str(e)}")
            failed += 1
        except Exception as e:
            print(f"❌ 测试异常: {name}")
            print(f"   错误: {str(e)}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("🎉 所有单元测试通过！Manager Agent ReAct逻辑正确")
    else:
        print(f"⚠️  有 {failed} 个测试失败")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
