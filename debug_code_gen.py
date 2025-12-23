"""调试代码生成"""
import asyncio
import sys
import os

# Windows编码设置
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 禁用代理
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)

from orchestrator import get_orchestrator


async def main():
    orchestrator = get_orchestrator()

    print("开始代码生成测试...\n")

    result = await orchestrator.process_request("列出AWS CloudWatch指标")

    if not result.get("success"):
        print(f"❌ 执行失败: {result.get('error')}")
        return

    # 提取生成的代码
    final_result = result.get("result", {})
    code = final_result.get("code", "")

    if not code:
        print("❌ 没有生成代码")
        return

    print("\n" + "="*80)
    print("生成的代码:")
    print("="*80)
    print(code)
    print("="*80)

    # 检查代码特征
    print("\n代码特征分析:")
    print(f"  - 包含try-except: {'try:' in code and 'except' in code}")
    print(f"  - 包含参数验证(if...is None): {'if' in code and 'is None' in code}")
    print(f"  - 包含参数验证(if not): {'if not' in code}")
    print(f"  - 包含assert: {'assert' in code}")
    print(f"  - 包含raise ValueError: {'raise ValueError' in code}")
    print(f"  - 包含import boto3: {'import boto3' in code}")
    print(f"  - 包含函数定义: {'def ' in code}")
    print(f"  - 代码长度: {len(code)} 字符")

    # 检查执行日志
    print("\n执行日志:")
    for log in result.get("execution_log", []):
        step = log.get("step", "")
        status = log.get("status", "")
        if step.startswith("test_code"):
            print(f"  {step}: {status}")
            if "tests" in log:
                for test in log["tests"]:
                    if isinstance(test, dict):
                        print(f"    - {test.get('name')}: {'✅' if test.get('passed') else '❌'}")
                        if not test.get('passed'):
                            print(f"      Message: {test.get('message', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(main())
