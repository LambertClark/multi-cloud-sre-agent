"""
多云SRE Agent主程序 - 新版本
使用编排器协调各个Agent完成完整工作流
"""
import asyncio
import argparse
import json
import sys
import os
from typing import Dict, Any
import logging

# Windows编码设置
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from orchestrator import get_orchestrator
from config import get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def query_command(query: str, output_file: str = None):
    """处理查询命令"""
    print(f"\n{'='*60}")
    print(f"🤖 Processing Query")
    print(f"{'='*60}")
    print(f"Query: {query}\n")

    orchestrator = get_orchestrator()

    # 处理请求
    result = await orchestrator.process_request(query)

    # 打印结果
    if result.get("success"):
        print(f"✅ Success!")
        print(f"\nDuration: {result.get('duration', 0):.2f}s")

        # 打印意图分析
        intent = result.get("intent", {})
        print(f"\n📋 Intent Analysis:")
        print(f"  Cloud: {intent.get('cloud_provider', 'N/A')}")
        print(f"  Service: {intent.get('service', 'N/A')}")
        print(f"  Operation: {intent.get('operation', 'N/A')}")

        # 打印执行计划
        plan = result.get("execution_plan", {})
        print(f"\n📝 Execution Plan:")
        print(f"  Has Existing API: {plan.get('has_existing_api', False)}")
        print(f"  Steps: {len(plan.get('steps', []))}")

        # 打印执行日志
        print(f"\n📊 Execution Log:")
        for log_entry in result.get("execution_log", []):
            print(f"  [{log_entry.get('step')}] {log_entry.get('status', 'N/A')}")

        # 打印结果
        final_result = result.get("result", {})
        print(f"\n🎯 Result:")
        if final_result.get("code"):
            print(f"  Generated Code: {len(final_result['code'])} characters")
        if final_result.get("output"):
            print(f"  Output:\n{final_result['output'][:500]}")
        if final_result.get("data"):
            print(f"  Data: {json.dumps(final_result['data'], indent=2)[:500]}")

    else:
        print(f"❌ Failed!")
        print(f"Error: {result.get('error')}")
        print(f"\nExecution Log:")
        for log_entry in result.get("execution_log", []):
            print(f"  [{log_entry.get('step')}] {log_entry.get('timestamp')}")

    # 保存结果到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Result saved to: {output_file}")

    return result


async def health_check_command():
    """健康检查命令"""
    print(f"\n{'='*60}")
    print(f"🏥 Health Check")
    print(f"{'='*60}\n")

    orchestrator = get_orchestrator()
    health = await orchestrator.health_check()

    print(f"Status: {health.get('status')}")
    print(f"\nComponents:")

    for component, info in health.get("components", {}).items():
        status_icon = "✅" if info.get("status") == "ok" else "❌"
        print(f"  {status_icon} {component}: {info.get('status')}")

        if "capabilities" in info:
            print(f"      Capabilities: {info['capabilities']}")
        if "indices_count" in info:
            print(f"      Indices: {info['indices_count']}")
        if "tools_count" in info:
            print(f"      Tools: {info['tools_count']}")

    return health


async def interactive_mode():
    """交互模式"""
    print(f"\n{'='*60}")
    print(f"🚀 多云SRE Agent - 交互模式")
    print(f"{'='*60}\n")

    orchestrator = get_orchestrator()

    print("Commands:")
    print("  - 输入查询语句（如：查询AWS EC2的CPU使用率）")
    print("  - /health - 健康检查")
    print("  - /exit - 退出")
    print()

    while True:
        try:
            query = input("Query> ").strip()

            if not query:
                continue

            if query == "/exit":
                print("👋 Goodbye!")
                break

            if query == "/health":
                await health_check_command()
                continue

            # 处理查询
            await query_command(query)

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in interactive mode: {str(e)}")
            print(f"❌ Error: {str(e)}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="多云SRE Agent - 智能云服务管理助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 交互模式
  python main_new.py --mode interactive

  # 查询模式
  python main_new.py --mode query --query "查询AWS EC2的CPU使用率"

  # 健康检查
  python main_new.py --mode health

  # 查询示例
  python main_new.py -q "获取AWS CloudWatch告警状态"
  python main_new.py -q "查询AWS日志组列表"
  python main_new.py -q "获取AWS X-Ray追踪摘要"
        """
    )

    parser.add_argument(
        '--mode', '-m',
        choices=['interactive', 'query', 'health'],
        default='interactive',
        help='运行模式'
    )

    parser.add_argument(
        '--query', '-q',
        help='查询语句（用于query模式）'
    )

    parser.add_argument(
        '--output', '-o',
        help='输出文件路径'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )

    args = parser.parse_args()

    # 如果指定了--query但没有指定mode,自动切换到query模式
    if args.query and args.mode == 'interactive':
        args.mode = 'query'

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.mode == 'interactive':
            await interactive_mode()

        elif args.mode == 'query':
            if not args.query:
                print("❌ --query is required in query mode")
                sys.exit(1)
            await query_command(args.query, args.output)

        elif args.mode == 'health':
            await health_check_command()

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
