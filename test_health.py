"""
测试健康检查（禁用代理）
"""
import os
import sys
import asyncio

# Windows编码设置
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 禁用代理环境变量
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('all_proxy', None)

from orchestrator import get_orchestrator


async def main():
    print("=" * 60)
    print("健康检查测试")
    print("=" * 60)
    print()

    orchestrator = get_orchestrator()
    health = await orchestrator.health_check()

    print(f"状态: {health.get('status')}")
    print(f"\n组件状态:")

    for component, info in health.get("components", {}).items():
        status_icon = "✅" if info.get("status") == "ok" else "❌"
        print(f"  {status_icon} {component}: {info.get('status')}")

        # 打印详细信息
        for key, value in info.items():
            if key != "status":
                print(f"      {key}: {value}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
