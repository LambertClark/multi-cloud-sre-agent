"""
CodeGeneratorAgent ReAct单元测试
不依赖LLM，快速验证核心逻辑
"""
import asyncio
import sys
import os
import io
from unittest.mock import AsyncMock, MagicMock, patch

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.code_generator_agent import CodeGeneratorAgent
from agents.base_agent import AgentResponse


async def test_react_iteration_control():
    """测试1：验证ReAct迭代控制逻辑"""
    print("\n=== 测试1：ReAct迭代控制 ===")

    agent = CodeGeneratorAgent()

    # Mock process方法（生成代码）
    mock_code_response = AgentResponse(
        success=True,
        data={
            "code": "def test(): return 42",
            "language": "python"
        }
    )

    # Mock generate_test_code方法
    mock_test_response = AgentResponse(
        success=True,
        data={
            "test_code": "def test_test(): assert test() == 42"
        }
    )

    with patch.object(agent, 'process', return_value=mock_code_response), \
         patch.object(agent, 'generate_test_code', return_value=mock_test_response), \
         patch.object(agent, '_react_thought', return_value="Mock thought"), \
         patch.object(agent, '_react_observation', return_value={"status": "success"}):

        result = await agent.process_with_react({
            "requirement": "测试需求",
            "operation": "test_op",
            "enable_auto_test": True
        })

        print(f"结果: {result.success}")
        print(f"迭代次数: {result.data.get('iterations')}")

        assert result.success, "应该成功"
        assert result.data['iterations'] == 1, "成功应该只需1次迭代"
        assert len(result.data['react_history']) == 1, "应该有1条历史记录"

        print("✅ 测试1通过：迭代控制正确")


async def test_react_max_iterations():
    """测试2：验证最大迭代次数限制"""
    print("\n=== 测试2：最大迭代次数限制 ===")

    agent = CodeGeneratorAgent()

    # Mock总是返回测试失败
    mock_code_response = AgentResponse(
        success=True,
        data={"code": "def test(): return 1", "language": "python"}
    )

    mock_test_response = AgentResponse(
        success=True,
        data={"test_code": "def test_test(): assert False"}
    )

    with patch.object(agent, 'process', return_value=mock_code_response), \
         patch.object(agent, 'generate_test_code', return_value=mock_test_response), \
         patch.object(agent, '_react_thought', return_value="Mock thought"), \
         patch.object(agent, '_react_observation', return_value={"status": "failed", "error": "Test failed"}):

        result = await agent.process_with_react({
            "requirement": "测试需求",
            "operation": "test_op",
            "enable_auto_test": True
        })

        print(f"结果: {result.success}")
        print(f"迭代次数: {result.data.get('iterations')}")

        assert not result.success, "应该失败（达到最大迭代）"
        assert result.data['iterations'] == 3, "应该尝试3次"
        assert len(result.data['react_history']) == 3, "应该有3条历史记录"

        print("✅ 测试2通过：正确限制最大迭代次数")


async def test_react_disable_auto_test():
    """测试3：禁用自动测试模式"""
    print("\n=== 测试3：禁用自动测试 ===")

    agent = CodeGeneratorAgent()

    mock_code_response = AgentResponse(
        success=True,
        data={"code": "def test(): return 1", "language": "python"}
    )

    mock_test_response = AgentResponse(
        success=True,
        data={"test_code": "def test_test(): pass"}
    )

    with patch.object(agent, 'process', return_value=mock_code_response), \
         patch.object(agent, 'generate_test_code', return_value=mock_test_response), \
         patch.object(agent, '_react_thought', return_value="Mock thought"):

        result = await agent.process_with_react({
            "requirement": "测试需求",
            "operation": "test_op",
            "enable_auto_test": False  # 禁用测试
        })

        print(f"结果: {result.success}")
        print(f"迭代次数: {result.data.get('iterations')}")

        assert result.success, "禁用测试应该成功"
        assert result.data['iterations'] == 1, "禁用测试应该1次返回"

        # 验证observation是skipped
        assert result.data['react_history'][0]['observation']['status'] == 'skipped'

        print("✅ 测试3通过：禁用测试模式正确")


async def test_react_history_structure():
    """测试4：验证ReAct历史记录结构"""
    print("\n=== 测试4：ReAct历史记录结构 ===")

    agent = CodeGeneratorAgent()

    mock_code_response = AgentResponse(
        success=True,
        data={"code": "def test(): return 1", "language": "python"}
    )

    mock_test_response = AgentResponse(
        success=True,
        data={"test_code": "def test_test(): pass"}
    )

    with patch.object(agent, 'process', return_value=mock_code_response), \
         patch.object(agent, 'generate_test_code', return_value=mock_test_response), \
         patch.object(agent, '_react_thought', return_value="思考内容"), \
         patch.object(agent, '_react_observation', return_value={"status": "success", "message": "测试通过"}):

        result = await agent.process_with_react({
            "requirement": "测试需求",
            "operation": "test_op",
            "enable_auto_test": True
        })

        history = result.data['react_history'][0]

        # 验证必要字段
        assert 'iteration' in history, "缺少iteration字段"
        assert 'thought' in history, "缺少thought字段"
        assert 'action' in history, "缺少action字段"
        assert 'observation' in history, "缺少observation字段"

        # 验证字段内容
        assert history['iteration'] == 1, "iteration应该是1"
        assert history['thought'] == "思考内容", "thought内容不正确"
        assert 'code_length' in history['action'], "action缺少code_length"
        assert 'test_length' in history['action'], "action缺少test_length"
        assert history['observation']['status'] == 'success', "observation状态不正确"

        print(f"历史记录结构: {list(history.keys())}")
        print("✅ 测试4通过：历史记录结构完整")


async def test_react_retry_context():
    """测试5：验证重试时使用retry_context"""
    print("\n=== 测试5：重试上下文传递 ===")

    agent = CodeGeneratorAgent()

    process_calls = []

    async def mock_process(input_data):
        process_calls.append(input_data)
        return AgentResponse(
            success=True,
            data={"code": "def test(): return 1", "language": "python"}
        )

    mock_test_response = AgentResponse(
        success=True,
        data={"test_code": "def test_test(): pass"}
    )

    # 第一次失败，第二次成功
    observation_count = [0]

    def mock_observation(code, test_code, language):
        observation_count[0] += 1
        if observation_count[0] == 1:
            return {"status": "failed", "error": "测试失败"}
        else:
            return {"status": "success"}

    with patch.object(agent, 'process', side_effect=mock_process), \
         patch.object(agent, 'generate_test_code', return_value=mock_test_response), \
         patch.object(agent, '_react_thought', return_value="Mock thought"), \
         patch.object(agent, '_react_observation', side_effect=mock_observation):

        result = await agent.process_with_react({
            "requirement": "测试需求",
            "operation": "test_op",
            "enable_auto_test": True
        })

        print(f"process调用次数: {len(process_calls)}")
        print(f"迭代次数: {result.data.get('iterations')}")

        assert len(process_calls) == 2, "应该调用process两次"
        assert result.data['iterations'] == 2, "应该迭代2次"

        # 验证第二次调用有retry_context
        second_call = process_calls[1]
        assert 'retry_context' in second_call, "第二次调用应该包含retry_context"
        assert 'previous_code' in second_call['retry_context'], "retry_context应该包含previous_code"
        assert 'error_summary' in second_call['retry_context'], "retry_context应该包含error_summary"

        print("✅ 测试5通过：正确传递retry_context")


async def main():
    """运行所有单元测试"""
    print("=" * 70)
    print("CodeGeneratorAgent ReAct 单元测试")
    print("=" * 70)
    print("\n⚡ 快速测试（不需要LLM）")

    tests = [
        ("迭代控制", test_react_iteration_control),
        ("最大迭代限制", test_react_max_iterations),
        ("禁用测试模式", test_react_disable_auto_test),
        ("历史记录结构", test_react_history_structure),
        ("重试上下文", test_react_retry_context),
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
        print("🎉 所有单元测试通过！")
    else:
        print(f"⚠️  有 {failed} 个测试失败")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
