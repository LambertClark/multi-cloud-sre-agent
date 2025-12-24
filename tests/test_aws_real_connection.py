"""
测试AWS真实连接和数据获取
不通过系统，直接用boto3测试
"""
import sys
import io
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 70)
print("AWS真实连接测试")
print("=" * 70)

# 检查环境变量
aws_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION', 'us-east-1')

print(f"\n环境变量检查:")
print(f"  AWS_ACCESS_KEY_ID: {'✅ 已配置' if aws_key else '❌ 未配置'}")
print(f"  AWS_SECRET_ACCESS_KEY: {'✅ 已配置' if aws_secret else '❌ 未配置'}")
print(f"  AWS_REGION: {aws_region}")

if not aws_key or not aws_secret:
    print("\n❌ AWS凭证未配置")
    sys.exit(1)

import boto3

# 测试1: CloudWatch - 列出指标
print("\n" + "=" * 70)
print("测试1: CloudWatch - 列出指标")
print("=" * 70)

try:
    cloudwatch = boto3.client(
        'cloudwatch',
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=aws_region
    )

    print(f"\n✓ CloudWatch客户端创建成功")
    print(f"  区域: {aws_region}")

    # 列出所有命名空间的指标（不限定EC2）
    print("\n✓ 查询所有CloudWatch指标...")
    response = cloudwatch.list_metrics()

    all_metrics = response.get('Metrics', [])
    print(f"\n✅ 成功！找到 {len(all_metrics)} 个指标")

    # 按命名空间分组统计
    namespaces = {}
    for metric in all_metrics:
        ns = metric.get('Namespace', 'Unknown')
        namespaces[ns] = namespaces.get(ns, 0) + 1

    print(f"\n指标分布（按命名空间）:")
    for ns, count in sorted(namespaces.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {ns}: {count} 个指标")

    # 显示前5个指标的详细信息
    if all_metrics:
        print(f"\n前5个指标详情:")
        for i, metric in enumerate(all_metrics[:5], 1):
            print(f"\n  {i}. {metric.get('Namespace', 'N/A')} / {metric.get('MetricName', 'N/A')}")
            dimensions = metric.get('Dimensions', [])
            if dimensions:
                dim_str = ', '.join([f"{d['Name']}={d['Value']}" for d in dimensions])
                print(f"     维度: {dim_str}")

    test1_success = True

except Exception as e:
    print(f"\n❌ CloudWatch测试失败: {str(e)}")
    test1_success = False


# 测试2: 列出告警
print("\n" + "=" * 70)
print("测试2: CloudWatch - 列出告警")
print("=" * 70)

try:
    print("\n✓ 查询CloudWatch告警...")
    response = cloudwatch.describe_alarms()

    alarms = response.get('MetricAlarms', [])
    print(f"\n✅ 成功！找到 {len(alarms)} 个告警")

    if alarms:
        print(f"\n告警列表:")
        for i, alarm in enumerate(alarms[:5], 1):
            print(f"  {i}. {alarm.get('AlarmName', 'N/A')}")
            print(f"     状态: {alarm.get('StateValue', 'N/A')}")
            print(f"     指标: {alarm.get('MetricName', 'N/A')}")
    else:
        print("  ⚠️  当前账号没有配置CloudWatch告警")

    test2_success = True

except Exception as e:
    print(f"\n❌ 告警查询失败: {str(e)}")
    test2_success = False


# 测试3: 获取账号信息（STS）
print("\n" + "=" * 70)
print("测试3: STS - 获取账号信息")
print("=" * 70)

try:
    sts = boto3.client(
        'sts',
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=aws_region
    )

    print("\n✓ 获取调用者身份...")
    response = sts.get_caller_identity()

    print(f"\n✅ 成功！")
    print(f"  账号ID: {response.get('Account', 'N/A')}")
    print(f"  用户ARN: {response.get('Arn', 'N/A')}")
    print(f"  用户ID: {response.get('UserId', 'N/A')}")

    test3_success = True

except Exception as e:
    print(f"\n❌ STS测试失败: {str(e)}")
    test3_success = False


# 测试4: 列出S3桶（如果有权限）
print("\n" + "=" * 70)
print("测试4: S3 - 列出存储桶（如果有权限）")
print("=" * 70)

try:
    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=aws_region
    )

    print("\n✓ 查询S3存储桶...")
    response = s3.list_buckets()

    buckets = response.get('Buckets', [])
    print(f"\n✅ 成功！找到 {len(buckets)} 个S3存储桶")

    if buckets:
        print(f"\nS3存储桶列表:")
        for i, bucket in enumerate(buckets[:10], 1):
            print(f"  {i}. {bucket.get('Name', 'N/A')}")
            print(f"     创建时间: {bucket.get('CreationDate', 'N/A')}")
    else:
        print("  ⚠️  当前账号没有S3存储桶")

    test4_success = True

except Exception as e:
    error_msg = str(e)
    if "AccessDenied" in error_msg or "403" in error_msg:
        print(f"\n⚠️  S3权限不足（预期内）: {error_msg[:100]}")
        test4_success = "no_permission"
    else:
        print(f"\n❌ S3测试失败: {error_msg[:200]}")
        test4_success = False


# 测试5: EC2 - 列出区域
print("\n" + "=" * 70)
print("测试5: EC2 - 列出可用区域")
print("=" * 70)

try:
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=aws_region
    )

    print("\n✓ 查询EC2可用区域...")
    response = ec2.describe_regions()

    regions = response.get('Regions', [])
    print(f"\n✅ 成功！找到 {len(regions)} 个AWS区域")

    if regions:
        print(f"\nAWS区域列表:")
        for i, region in enumerate(regions[:10], 1):
            print(f"  {i}. {region.get('RegionName', 'N/A')}")
            print(f"     端点: {region.get('Endpoint', 'N/A')}")

    test5_success = True

except Exception as e:
    error_msg = str(e)
    if "UnauthorizedOperation" in error_msg or "403" in error_msg:
        print(f"\n⚠️  EC2权限不足（预期内）: {error_msg[:100]}")
        test5_success = "no_permission"
    else:
        print(f"\n❌ EC2测试失败: {error_msg[:200]}")
        test5_success = False


# 总结
print("\n" + "=" * 70)
print("测试总结")
print("=" * 70)

results = [
    ("CloudWatch列出指标", test1_success),
    ("CloudWatch列出告警", test2_success),
    ("STS获取账号信息", test3_success),
    ("S3列出存储桶", test4_success),
    ("EC2列出区域", test5_success),
]

print("\n测试结果:")
for name, result in results:
    if result == True:
        status = "✅ 成功"
    elif result == "no_permission":
        status = "⚠️  无权限（预期内）"
    else:
        status = "❌ 失败"
    print(f"  {status} - {name}")

# 计算成功率
success_count = sum(1 for _, r in results if r == True)
partial_count = sum(1 for _, r in results if r == "no_permission")
total_count = len(results)

print(f"\n✅ 完全成功: {success_count}/{total_count}")
print(f"⚠️  权限限制: {partial_count}/{total_count}")

if success_count >= 2:
    print("\n🎉 AWS连接正常！至少有 {0} 个服务可用！".format(success_count))
    print("\n可用的AWS服务:")
    for name, result in results:
        if result == True:
            print(f"  ✅ {name}")
else:
    print("\n⚠️  AWS连接有限，部分服务不可用")

print("\n" + "=" * 70)
