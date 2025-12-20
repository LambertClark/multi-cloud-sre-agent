"""
所有云平台SDK内省综合测试
"""
import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.spec_doc_agent import SpecDocAgent


async def main():
    """综合测试所有支持的云平台"""
    print("=" * 70)
    print("多云平台SDK内省综合测试")
    print("=" * 70)

    spec_agent = SpecDocAgent()

    platforms = [
        ("AWS CloudWatch", "aws", "cloudwatch"),
        ("AWS S3", "aws", "s3"),
        ("AWS EC2", "aws", "ec2"),
        ("Azure Monitor", "azure", "monitor"),
        ("GCP Monitoring", "gcp", "monitoring"),
        ("Kubernetes Core", "kubernetes", "core"),
    ]

    results = []

    for name, provider, service in platforms:
        print(f"\n{name}:")
        result = await spec_agent.process({
            "cloud_provider": provider,
            "service": service
        })

        if result.success:
            specs = result.data.get("specifications", {})
            ops_count = len(specs.get("operations", []))
            source = result.data.get("source", "unknown")

            print(f"  数据来源: {source}")
            print(f"  API操作数: {ops_count}")

            if ops_count > 0:
                print(f"  状态: ✅ 成功")
                results.append((name, ops_count, source, True))
            else:
                print(f"  状态: ⚠️  无操作（可能是SDK未安装）")
                results.append((name, ops_count, source, False))
        else:
            print(f"  状态: ❌ 失败 - {result.error}")
            results.append((name, 0, "error", False))

    # 打印总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    success_count = sum(1 for _, _, _, success in results if success)
    total_ops = sum(count for _, count, _, _ in results)

    print(f"\n成功平台: {success_count}/{len(platforms)}")
    print(f"总API操作数: {total_ops}")

    print("\n详细统计:")
    for name, count, source, success in results:
        status = "✅" if success else ("⚠️ " if count == 0 else "❌")
        print(f"  {status} {name}: {count} 操作 ({source})")

    print("\n数据来源说明:")
    print("  - sdk_introspection: 从云SDK内省提取（最可靠）")
    print("  - openapi_spec: 从OpenAPI/Swagger规格解析")
    print("  - unknown: 未找到数据源")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
