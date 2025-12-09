"""
测试凭证注入功能
验证环境变量能否正确注入到沙箱环境
"""
import asyncio
import os
import sys

# Windows编码设置
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from wasm_sandbox import get_sandbox


async def test_aws_credentials():
    """测试AWS凭证注入"""
    print("=" * 60)
    print("测试AWS凭证注入")
    print("=" * 60)

    # 检查环境变量是否已配置
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        print("⚠️  AWS凭证未配置，跳过测试")
        print("   请在 .env 文件中配置 AWS_ACCESS_KEY_ID 和 AWS_SECRET_ACCESS_KEY")
        return

    # 测试代码：读取环境变量
    test_code = """
import os
import json

# 检查环境变量
credentials = {
    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "NOT_SET"),
    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "NOT_SET")[:10] + "...",  # 只显示前10位
    "AWS_REGION": os.getenv("AWS_REGION", "NOT_SET"),
}

print(json.dumps(credentials, indent=2))
"""

    sandbox = get_sandbox()
    result = await sandbox.execute_code(test_code, "python", {})

    if result.get("success"):
        print("✅ 凭证注入成功")
        print("\n环境变量内容:")
        print(result.get("output"))
    else:
        print("❌ 凭证注入失败")
        print(f"错误: {result.get('error')}")


async def test_boto3_import():
    """测试boto3能否导入"""
    print("\n" + "=" * 60)
    print("测试boto3导入")
    print("=" * 60)

    test_code = """
try:
    import boto3
    print("✅ boto3导入成功")
    print(f"boto3版本: {boto3.__version__}")

    # 尝试创建客户端（不实际调用API）
    import os
    if os.getenv("AWS_ACCESS_KEY_ID"):
        client = boto3.client('cloudwatch')
        print("✅ CloudWatch客户端创建成功")
    else:
        print("⚠️  未配置AWS凭证，跳过客户端创建")

except ImportError as e:
    print(f"❌ boto3导入失败: {e}")
    print("   请运行: pip install boto3")
except Exception as e:
    print(f"⚠️  其他错误: {e}")
"""

    sandbox = get_sandbox()
    result = await sandbox.execute_code(test_code, "python", {})

    print(result.get("output") or result.get("error"))


async def test_multi_cloud_credentials():
    """测试多云凭证注入"""
    print("\n" + "=" * 60)
    print("测试多云凭证注入")
    print("=" * 60)

    test_code = """
import os
import json

# 检查所有云平台凭证
clouds = {
    "AWS": {
        "access_key": bool(os.getenv("AWS_ACCESS_KEY_ID")),
        "region": os.getenv("AWS_REGION", "未设置")
    },
    "Azure": {
        "subscription_id": bool(os.getenv("AZURE_SUBSCRIPTION_ID")),
        "tenant_id": os.getenv("AZURE_TENANT_ID", "未设置")[:10] + "..." if os.getenv("AZURE_TENANT_ID") else "未设置"
    },
    "GCP": {
        "project_id": os.getenv("GCP_PROJECT_ID", "未设置")
    },
    "Aliyun": {
        "access_key": bool(os.getenv("ALIYUN_ACCESS_KEY_ID")),
        "region": os.getenv("ALIYUN_REGION", "未设置")
    },
    "Volcano": {
        "access_key": bool(os.getenv("VOLC_ACCESS_KEY")),
        "region": os.getenv("VOLC_REGION", "未设置")
    }
}

print("云平台凭证配置状态:")
print(json.dumps(clouds, indent=2, ensure_ascii=False))
"""

    sandbox = get_sandbox()
    result = await sandbox.execute_code(test_code, "python", {})

    if result.get("success"):
        print(result.get("output"))
    else:
        print(f"错误: {result.get('error')}")


async def main():
    """主测试函数"""
    print("\n🧪 凭证注入功能测试\n")

    # 测试1: AWS凭证注入
    await test_aws_credentials()

    # 测试2: boto3导入
    await test_boto3_import()

    # 测试3: 多云凭证
    await test_multi_cloud_credentials()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
