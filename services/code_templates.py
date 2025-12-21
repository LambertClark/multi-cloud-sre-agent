"""
代码模板库
提供常见的云API操作模式，减少重复代码和错误
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CloudProvider(Enum):
    """云平台枚举"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"
    VOLCENGINE = "volcengine"


class TemplateCategory(Enum):
    """模板分类"""
    PAGINATION = "pagination"  # 分页查询
    RETRY = "retry"  # 重试机制
    BATCH = "batch"  # 批量操作
    ERROR_HANDLING = "error_handling"  # 错误处理
    RESOURCE_CLEANUP = "resource_cleanup"  # 资源清理
    FILTERING = "filtering"  # 过滤筛选
    MONITORING = "monitoring"  # 监控指标


@dataclass
class CodeTemplate:
    """代码模板"""
    name: str
    category: TemplateCategory
    cloud_provider: CloudProvider
    description: str
    code_template: str
    parameters: List[str]
    example: str
    best_practices: List[str]
    common_pitfalls: List[str]


class CodeTemplateLibrary:
    """
    代码模板库

    提供常见的云API操作模式：
    1. 分页查询 - 处理大量数据的分页逻辑
    2. 重试机制 - 处理临时错误和限流
    3. 批量操作 - 高效处理多个资源
    4. 错误处理 - 统一的异常处理模式
    5. 资源清理 - 确保资源正确释放
    6. 过滤筛选 - 常见的数据过滤逻辑
    """

    def __init__(self):
        self.templates: Dict[str, CodeTemplate] = {}
        self._register_all_templates()

    def _register_all_templates(self):
        """注册所有模板"""
        # AWS模板
        self._register_aws_pagination_templates()
        self._register_aws_retry_templates()
        self._register_aws_batch_templates()
        self._register_aws_error_handling_templates()

        # Azure模板
        self._register_azure_pagination_templates()

        # Kubernetes模板
        self._register_k8s_templates()

        # 通用模板
        self._register_common_templates()

    def get_template(self, name: str) -> Optional[CodeTemplate]:
        """获取模板"""
        return self.templates.get(name)

    def search_templates(
        self,
        category: Optional[TemplateCategory] = None,
        cloud_provider: Optional[CloudProvider] = None,
        keyword: Optional[str] = None
    ) -> List[CodeTemplate]:
        """搜索模板"""
        results = list(self.templates.values())

        if category:
            results = [t for t in results if t.category == category]

        if cloud_provider:
            results = [t for t in results if t.cloud_provider == cloud_provider]

        if keyword:
            keyword_lower = keyword.lower()
            results = [
                t for t in results
                if keyword_lower in t.name.lower() or keyword_lower in t.description.lower()
            ]

        return results

    def _register_template(self, template: CodeTemplate):
        """注册模板"""
        self.templates[template.name] = template

    # ==================== AWS模板 ====================

    def _register_aws_pagination_templates(self):
        """注册AWS分页模板"""

        # EC2分页查询
        self._register_template(CodeTemplate(
            name="aws_ec2_pagination",
            category=TemplateCategory.PAGINATION,
            cloud_provider=CloudProvider.AWS,
            description="AWS EC2分页查询所有实例",
            code_template='''
def list_all_ec2_instances(ec2_client, filters=None):
    """
    列出所有EC2实例（处理分页）

    Args:
        ec2_client: boto3 EC2 client
        filters: 可选的过滤条件

    Returns:
        所有实例的列表
    """
    instances = []
    paginator = ec2_client.get_paginator('describe_instances')

    page_iterator = paginator.paginate(
        Filters=filters or [],
        PaginationConfig={'PageSize': 100}
    )

    for page in page_iterator:
        for reservation in page['Reservations']:
            instances.extend(reservation['Instances'])

    return instances
''',
            parameters=["ec2_client", "filters"],
            example='''
import boto3

ec2 = boto3.client('ec2', region_name='us-east-1')

# 查询所有运行中的实例
running_filters = [{'Name': 'instance-state-name', 'Values': ['running']}]
instances = list_all_ec2_instances(ec2, filters=running_filters)

print(f"找到 {len(instances)} 个运行中的实例")
''',
            best_practices=[
                "使用paginator而不是手动处理NextToken",
                "设置合理的PageSize（通常100-1000）",
                "对大量数据使用生成器而不是列表",
                "添加过滤条件减少数据量"
            ],
            common_pitfalls=[
                "忘记处理分页，只获取第一页数据",
                "PageSize设置过大导致超时",
                "没有错误处理导致部分失败时数据丢失"
            ]
        ))

        # S3分页查询
        self._register_template(CodeTemplate(
            name="aws_s3_pagination",
            category=TemplateCategory.PAGINATION,
            cloud_provider=CloudProvider.AWS,
            description="AWS S3分页列出对象",
            code_template='''
def list_all_s3_objects(s3_client, bucket_name, prefix=''):
    """
    列出S3桶中的所有对象（处理分页）

    Args:
        s3_client: boto3 S3 client
        bucket_name: 桶名称
        prefix: 对象前缀

    Returns:
        所有对象的列表
    """
    objects = []
    paginator = s3_client.get_paginator('list_objects_v2')

    page_iterator = paginator.paginate(
        Bucket=bucket_name,
        Prefix=prefix,
        PaginationConfig={'PageSize': 1000}
    )

    for page in page_iterator:
        if 'Contents' in page:
            objects.extend(page['Contents'])

    return objects
''',
            parameters=["s3_client", "bucket_name", "prefix"],
            example='''
import boto3

s3 = boto3.client('s3')
objects = list_all_s3_objects(s3, 'my-bucket', prefix='logs/')
print(f"找到 {len(objects)} 个对象")
''',
            best_practices=[
                "使用list_objects_v2而不是已废弃的list_objects",
                "使用prefix参数缩小范围",
                "检查'Contents'键是否存在（空桶没有这个键）"
            ],
            common_pitfalls=[
                "使用list_objects（已废弃）",
                "没有检查Contents键导致KeyError",
                "没有处理大量对象导致内存溢出"
            ]
        ))

    def _register_aws_retry_templates(self):
        """注册AWS重试模板"""

        self._register_template(CodeTemplate(
            name="aws_exponential_backoff",
            category=TemplateCategory.RETRY,
            cloud_provider=CloudProvider.AWS,
            description="AWS API调用指数退避重试",
            code_template='''
import time
from botocore.exceptions import ClientError

def retry_with_exponential_backoff(func, max_retries=3, base_delay=1, max_delay=60):
    """
    使用指数退避重试AWS API调用

    Args:
        func: 要执行的函数
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）

    Returns:
        函数执行结果

    Raises:
        最后一次的异常
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except ClientError as e:
            error_code = e.response['Error']['Code']

            # 不可重试的错误直接抛出
            if error_code in ['InvalidParameterValue', 'AccessDenied']:
                raise

            # 最后一次重试失败
            if attempt == max_retries:
                raise

            # 计算延迟时间（指数增长）
            delay = min(base_delay * (2 ** attempt), max_delay)

            print(f"API调用失败 ({error_code})，{delay}秒后重试...")
            time.sleep(delay)

    raise Exception("重试失败")
''',
            parameters=["func", "max_retries", "base_delay", "max_delay"],
            example='''
import boto3

ec2 = boto3.client('ec2')

def describe_instances():
    return ec2.describe_instances()

# 使用重试机制
result = retry_with_exponential_backoff(describe_instances, max_retries=5)
''',
            best_practices=[
                "区分可重试错误和不可重试错误",
                "使用指数退避避免压垮服务",
                "设置最大延迟上限",
                "记录重试日志便于调试"
            ],
            common_pitfalls=[
                "所有错误都重试（包括参数错误）",
                "固定延迟导致雪崩效应",
                "无限重试耗尽资源"
            ]
        ))

    def _register_aws_batch_templates(self):
        """注册AWS批量操作模板"""

        self._register_template(CodeTemplate(
            name="aws_batch_operation",
            category=TemplateCategory.BATCH,
            cloud_provider=CloudProvider.AWS,
            description="AWS批量操作资源",
            code_template='''
def batch_operation(client, operation_name, items, batch_size=100, **kwargs):
    """
    批量执行AWS操作

    Args:
        client: boto3 client
        operation_name: 操作名称（如'delete_objects'）
        items: 要处理的项目列表
        batch_size: 每批大小
        **kwargs: 传递给操作的额外参数

    Returns:
        {'success': 成功数量, 'failed': 失败数量, 'errors': 错误列表}
    """
    results = {'success': 0, 'failed': 0, 'errors': []}

    # 分批处理
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]

        try:
            # 动态调用操作
            operation = getattr(client, operation_name)
            response = operation(items=batch, **kwargs)

            # 处理响应
            if 'Successful' in response:
                results['success'] += len(response['Successful'])
            if 'Failed' in response:
                results['failed'] += len(response['Failed'])
                results['errors'].extend(response['Failed'])

        except Exception as e:
            results['failed'] += len(batch)
            results['errors'].append({
                'batch': batch,
                'error': str(e)
            })

    return results
''',
            parameters=["client", "operation_name", "items", "batch_size"],
            example='''
import boto3

s3 = boto3.client('s3')

# 批量删除对象
objects = [{'Key': f'file{i}.txt'} for i in range(1000)]
result = batch_operation(
    s3,
    'delete_objects',
    objects,
    batch_size=1000,
    Bucket='my-bucket'
)

print(f"成功: {result['success']}, 失败: {result['failed']}")
''',
            best_practices=[
                "遵守AWS批量操作的大小限制（通常1000）",
                "收集失败项目便于重试",
                "显示进度条提升用户体验",
                "对大批量操作添加延迟避免限流"
            ],
            common_pitfalls=[
                "超过API的批量大小限制",
                "没有错误处理导致部分失败不可见",
                "不收集失败项目无法重试"
            ]
        ))

    def _register_aws_error_handling_templates(self):
        """注册AWS错误处理模板"""

        self._register_template(CodeTemplate(
            name="aws_error_handling",
            category=TemplateCategory.ERROR_HANDLING,
            cloud_provider=CloudProvider.AWS,
            description="AWS API调用统一错误处理",
            code_template='''
from botocore.exceptions import ClientError, BotoCoreError
import logging

logger = logging.getLogger(__name__)

def handle_aws_error(func):
    """
    AWS错误处理装饰器

    捕获并处理常见的AWS错误
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            # 常见错误的友好提示
            error_hints = {
                'InvalidParameterValue': '参数值无效，请检查输入',
                'ResourceNotFoundException': '资源不存在',
                'AccessDenied': '权限不足，请检查IAM策略',
                'ThrottlingException': 'API调用频率过高，请稍后重试',
                'ServiceUnavailable': 'AWS服务暂时不可用',
            }

            hint = error_hints.get(error_code, error_message)
            logger.error(f"AWS错误 [{error_code}]: {hint}")

            return {
                'success': False,
                'error_code': error_code,
                'error_message': hint,
                'original_message': error_message
            }

        except BotoCoreError as e:
            logger.error(f"Boto核心错误: {str(e)}")
            return {
                'success': False,
                'error_code': 'BotoCoreError',
                'error_message': '底层连接错误，请检查网络或凭证'
            }

        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            return {
                'success': False,
                'error_code': 'UnknownError',
                'error_message': str(e)
            }

    return wrapper
''',
            parameters=["func"],
            example='''
@handle_aws_error
def get_instance_info(instance_id):
    ec2 = boto3.client('ec2')
    response = ec2.describe_instances(InstanceIds=[instance_id])
    return response['Reservations'][0]['Instances'][0]

result = get_instance_info('i-1234567890abcdef0')
if result.get('success') is False:
    print(f"错误: {result['error_message']}")
''',
            best_practices=[
                "区分不同类型的错误",
                "提供用户友好的错误信息",
                "记录详细日志便于调试",
                "对可恢复错误提供重试建议"
            ],
            common_pitfalls=[
                "吞掉所有异常不报错",
                "错误信息过于技术化",
                "没有日志导致问题难以排查"
            ]
        ))

    # ==================== Azure模板 ====================

    def _register_azure_pagination_templates(self):
        """注册Azure分页模板"""

        self._register_template(CodeTemplate(
            name="azure_vm_pagination",
            category=TemplateCategory.PAGINATION,
            cloud_provider=CloudProvider.AZURE,
            description="Azure虚拟机分页查询",
            code_template='''
def list_all_azure_vms(compute_client, resource_group=None):
    """
    列出所有Azure虚拟机（处理分页）

    Args:
        compute_client: Azure ComputeManagementClient
        resource_group: 可选的资源组名称

    Returns:
        所有虚拟机的列表
    """
    vms = []

    if resource_group:
        # 列出指定资源组的VM
        vm_list = compute_client.virtual_machines.list(resource_group)
    else:
        # 列出所有资源组的VM
        vm_list = compute_client.virtual_machines.list_all()

    # Azure SDK自动处理分页
    for vm in vm_list:
        vms.append({
            'name': vm.name,
            'id': vm.id,
            'location': vm.location,
            'vm_size': vm.hardware_profile.vm_size,
            'provisioning_state': vm.provisioning_state
        })

    return vms
''',
            parameters=["compute_client", "resource_group"],
            example='''
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient

credential = DefaultAzureCredential()
subscription_id = "your-subscription-id"
compute_client = ComputeManagementClient(credential, subscription_id)

# 列出所有VM
vms = list_all_azure_vms(compute_client)
print(f"找到 {len(vms)} 个虚拟机")
''',
            best_practices=[
                "Azure SDK自动处理分页，直接迭代即可",
                "使用list()限定资源组减少数据量",
                "提取需要的字段避免返回整个对象"
            ],
            common_pitfalls=[
                "忘记Azure自动分页特性手动处理",
                "返回完整对象导致内存占用过大"
            ]
        ))

    # ==================== Kubernetes模板 ====================

    def _register_k8s_templates(self):
        """注册Kubernetes模板"""

        self._register_template(CodeTemplate(
            name="k8s_list_pods_all_namespaces",
            category=TemplateCategory.PAGINATION,
            cloud_provider=CloudProvider.KUBERNETES,
            description="K8s列出所有命名空间的Pods",
            code_template='''
def list_all_pods(v1_client, namespace=None, label_selector=None):
    """
    列出所有Pods（支持过滤）

    Args:
        v1_client: Kubernetes CoreV1Api client
        namespace: 可选的命名空间（None表示所有命名空间）
        label_selector: 可选的标签选择器

    Returns:
        所有Pods的列表
    """
    pods = []

    if namespace:
        # 列出指定命名空间的Pods
        pod_list = v1_client.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector or ''
        )
    else:
        # 列出所有命名空间的Pods
        pod_list = v1_client.list_pod_for_all_namespaces(
            label_selector=label_selector or ''
        )

    for pod in pod_list.items:
        pods.append({
            'name': pod.metadata.name,
            'namespace': pod.metadata.namespace,
            'status': pod.status.phase,
            'node': pod.spec.node_name,
            'ip': pod.status.pod_ip
        })

    return pods
''',
            parameters=["v1_client", "namespace", "label_selector"],
            example='''
from kubernetes import client, config

config.load_kube_config()
v1 = client.CoreV1Api()

# 列出所有运行中的Pods
pods = list_all_pods(v1, label_selector='app=nginx')
print(f"找到 {len(pods)} 个Pods")
''',
            best_practices=[
                "使用label_selector过滤减少数据量",
                "提取关键字段避免返回整个对象",
                "区分namespaced和all_namespaces两种场景"
            ],
            common_pitfalls=[
                "不指定namespace导致权限错误",
                "label_selector语法错误"
            ]
        ))

    # ==================== 通用模板 ====================

    def _register_common_templates(self):
        """注册通用模板"""

        # 资源清理模板
        self._register_template(CodeTemplate(
            name="resource_cleanup_context_manager",
            category=TemplateCategory.RESOURCE_CLEANUP,
            cloud_provider=CloudProvider.AWS,  # 可用于所有云
            description="资源自动清理上下文管理器",
            code_template='''
from contextlib import contextmanager

@contextmanager
def cloud_resource_context(create_func, cleanup_func):
    """
    云资源上下文管理器，确保资源自动清理

    Args:
        create_func: 创建资源的函数
        cleanup_func: 清理资源的函数

    Yields:
        创建的资源
    """
    resource = None
    try:
        # 创建资源
        resource = create_func()
        yield resource
    finally:
        # 无论成功失败都清理
        if resource is not None:
            try:
                cleanup_func(resource)
            except Exception as e:
                print(f"资源清理失败: {e}")
''',
            parameters=["create_func", "cleanup_func"],
            example='''
import boto3

ec2 = boto3.client('ec2')

def create_temp_instance():
    response = ec2.run_instances(ImageId='ami-12345', MinCount=1, MaxCount=1)
    return response['Instances'][0]['InstanceId']

def terminate_instance(instance_id):
    ec2.terminate_instances(InstanceIds=[instance_id])

# 使用上下文管理器
with cloud_resource_context(create_temp_instance, terminate_instance) as instance_id:
    print(f"临时实例: {instance_id}")
    # 执行测试操作
# 自动清理
''',
            best_practices=[
                "始终在finally块中清理资源",
                "捕获清理过程的异常避免掩盖原始错误",
                "记录清理失败的日志"
            ],
            common_pitfalls=[
                "忘记清理导致资源泄漏",
                "清理失败掩盖了原始错误",
                "清理顺序错误导致依赖问题"
            ]
        ))

        # 数据过滤模板
        self._register_template(CodeTemplate(
            name="resource_filtering",
            category=TemplateCategory.FILTERING,
            cloud_provider=CloudProvider.AWS,
            description="资源过滤和筛选",
            code_template='''
def filter_resources(resources, conditions):
    """
    根据条件过滤资源

    Args:
        resources: 资源列表
        conditions: 过滤条件字典
                   支持：
                   - 'eq': 等于
                   - 'ne': 不等于
                   - 'in': 包含在列表中
                   - 'contains': 字符串包含

    Returns:
        过滤后的资源列表
    """
    filtered = resources

    for field, condition in conditions.items():
        operator = condition.get('operator', 'eq')
        value = condition.get('value')

        if operator == 'eq':
            filtered = [r for r in filtered if r.get(field) == value]
        elif operator == 'ne':
            filtered = [r for r in filtered if r.get(field) != value]
        elif operator == 'in':
            filtered = [r for r in filtered if r.get(field) in value]
        elif operator == 'contains':
            filtered = [r for r in filtered if value in str(r.get(field, ''))]

    return filtered
''',
            parameters=["resources", "conditions"],
            example='''
instances = [
    {'id': 'i-1', 'state': 'running', 'type': 't2.micro'},
    {'id': 'i-2', 'state': 'stopped', 'type': 't2.small'},
    {'id': 'i-3', 'state': 'running', 'type': 't2.micro'},
]

# 筛选运行中的t2.micro实例
conditions = {
    'state': {'operator': 'eq', 'value': 'running'},
    'type': {'operator': 'in', 'value': ['t2.micro', 't2.small']}
}

result = filter_resources(instances, conditions)
print(f"找到 {len(result)} 个匹配的实例")
''',
            best_practices=[
                "支持多种操作符提升灵活性",
                "处理字段不存在的情况",
                "考虑性能，先用API过滤再用代码过滤"
            ],
            common_pitfalls=[
                "在代码中过滤大量数据影响性能",
                "字段不存在导致KeyError",
                "操作符逻辑错误"
            ]
        ))


def get_template_library() -> CodeTemplateLibrary:
    """获取代码模板库单例"""
    return CodeTemplateLibrary()


def generate_code_from_template(template: CodeTemplate, **params) -> str:
    """
    从模板生成代码

    Args:
        template: 代码模板
        **params: 模板参数

    Returns:
        生成的代码
    """
    # 简单的字符串替换（后续可以改用Jinja2等模板引擎）
    code = template.code_template

    for param_name, param_value in params.items():
        placeholder = f"{{{param_name}}}"
        code = code.replace(placeholder, str(param_value))

    return code
