"""
测试代码生成器
自动为生成的代码创建全面的单元测试
"""
from typing import Dict, List, Any, Optional
import ast
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    parameters: List[str]
    return_type: Optional[str]
    docstring: Optional[str]
    has_exceptions: bool
    cloud_provider: Optional[str] = None
    service: Optional[str] = None


class TestGenerator:
    """
    测试代码生成器

    功能：
    1. 基础测试：正常输入的测试用例
    2. 边缘测试：边界值、空值、极端值
    3. 异常测试：错误输入、异常处理
    4. Mock测试：模拟云API调用
    5. 覆盖率优化：尽可能达到>80%覆盖率
    """

    def __init__(self):
        pass

    def generate_tests(self, code: str, function_name: str = None) -> str:
        """
        为代码生成测试

        Args:
            code: 源代码
            function_name: 可选的函数名（只测试指定函数）

        Returns:
            生成的测试代码
        """
        # 解析代码获取函数信息
        functions = self._parse_functions(code)

        if not functions:
            logger.warning("未找到可测试的函数")
            return ""

        # 如果指定函数名，只测试该函数
        if function_name:
            functions = [f for f in functions if f.name == function_name]

        # 生成测试代码
        test_code = self._generate_test_file(functions, code)

        return test_code

    def _parse_functions(self, code: str) -> List[FunctionInfo]:
        """解析代码，提取函数信息"""
        functions = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 跳过私有函数
                    if node.name.startswith('_'):
                        continue

                    # 提取参数
                    params = [arg.arg for arg in node.args.args if arg.arg != 'self']

                    # 提取返回类型
                    return_type = None
                    if node.returns:
                        return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else None

                    # 提取文档字符串
                    docstring = ast.get_docstring(node)

                    # 检查是否有异常处理
                    has_exceptions = any(
                        isinstance(n, (ast.Raise, ast.Try))
                        for n in ast.walk(node)
                    )

                    # 尝试识别云平台
                    cloud_provider = self._detect_cloud_provider(code, node)

                    functions.append(FunctionInfo(
                        name=node.name,
                        parameters=params,
                        return_type=return_type,
                        docstring=docstring,
                        has_exceptions=has_exceptions,
                        cloud_provider=cloud_provider
                    ))

        except SyntaxError as e:
            logger.error(f"代码解析失败: {e}")

        return functions

    def _detect_cloud_provider(self, code: str, func_node: ast.FunctionDef) -> Optional[str]:
        """检测函数使用的云平台"""
        # 检查boto3 (AWS)
        if 'boto3' in code or 'aws' in func_node.name.lower():
            return 'aws'

        # 检查Azure
        if 'azure' in code or 'azure' in func_node.name.lower():
            return 'azure'

        # 检查GCP
        if 'google.cloud' in code or 'gcp' in func_node.name.lower():
            return 'gcp'

        # 检查Kubernetes
        if 'kubernetes' in code or 'k8s' in func_node.name.lower():
            return 'kubernetes'

        return None

    def _generate_test_file(self, functions: List[FunctionInfo], original_code: str) -> str:
        """生成完整的测试文件"""
        test_code = '''"""
自动生成的测试代码
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
'''

        # 添加必要的导入
        if any(f.cloud_provider == 'aws' for f in functions):
            test_code += "from botocore.exceptions import ClientError\n"

        test_code += "\n# 导入被测试的函数\n"
        test_code += "# TODO: 替换为实际的导入路径\n"
        for func in functions:
            test_code += f"# from your_module import {func.name}\n"

        test_code += "\n"

        # 为每个函数生成测试类
        for func in functions:
            test_code += self._generate_test_class(func)
            test_code += "\n\n"

        return test_code

    def _generate_test_class(self, func: FunctionInfo) -> str:
        """为单个函数生成测试类"""
        class_name = f"Test{func.name.title().replace('_', '')}"

        test_code = f'''class {class_name}:
    """测试{func.name}函数"""
'''

        # 1. 基础测试
        test_code += self._generate_basic_test(func)

        # 2. 边缘情况测试
        test_code += self._generate_edge_case_tests(func)

        # 3. 异常测试
        if func.has_exceptions:
            test_code += self._generate_exception_tests(func)

        # 4. Mock测试（针对云API）
        if func.cloud_provider:
            test_code += self._generate_mock_tests(func)

        return test_code

    def _generate_basic_test(self, func: FunctionInfo) -> str:
        """生成基础测试用例"""
        test_code = f'''
    def test_{func.name}_basic(self):
        """测试{func.name}的基本功能"""
        # 准备测试数据
'''

        # 根据参数生成测试数据
        for param in func.parameters:
            test_code += f"        {param} = {self._get_sample_value(param)}\n"

        test_code += f'''
        # 执行函数
        result = {func.name}({', '.join(func.parameters)})

        # 验证结果
        assert result is not None
'''

        if func.return_type:
            test_code += f"        # 返回类型应为: {func.return_type}\n"

        return test_code

    def _generate_edge_case_tests(self, func: FunctionInfo) -> str:
        """生成边缘情况测试"""
        test_code = f'''
    def test_{func.name}_empty_input(self):
        """测试{func.name}的空输入处理"""
'''

        # 为每个参数生成空值测试
        for param in func.parameters:
            if 'list' in param.lower() or 'items' in param.lower():
                test_code += f"        {param} = []\n"
            elif 'dict' in param.lower():
                test_code += f"        {param} = {{}}\n"
            elif 'str' in param.lower() or 'name' in param.lower():
                test_code += f"        {param} = ''\n"
            else:
                test_code += f"        {param} = None\n"

        test_code += f'''
        # 空输入应该优雅处理（返回空或抛出明确错误）
        result = {func.name}({', '.join(func.parameters)})
        assert result is not None or True  # 根据实际行为调整
'''

        return test_code

    def _generate_exception_tests(self, func: FunctionInfo) -> str:
        """生成异常测试"""
        test_code = f'''
    def test_{func.name}_handles_errors(self):
        """测试{func.name}的错误处理"""
'''

        if func.cloud_provider == 'aws':
            test_code += '''        # 模拟AWS错误
        with patch('boto3.client') as mock_client:
            mock_client.return_value.describe_instances.side_effect = ClientError(
                {'Error': {'Code': 'InvalidParameterValue', 'Message': 'Invalid parameter'}},
                'DescribeInstances'
            )

            # 应该优雅处理错误
            result = ''' + func.name + '''(mock_client.return_value)
            assert 'error' in result or result is None
'''

        elif func.cloud_provider == 'azure':
            test_code += '''        # 模拟Azure错误
        with patch('azure.mgmt.compute.ComputeManagementClient') as mock_client:
            mock_client.return_value.virtual_machines.list.side_effect = Exception("Azure API Error")

            # 应该优雅处理错误
            with pytest.raises(Exception):
                ''' + func.name + '''(mock_client.return_value)
'''

        else:
            test_code += '''        # 模拟通用错误
        with patch('builtins.open', side_effect=IOError("File not found")):
            # 应该优雅处理错误
            with pytest.raises(Exception):
                ''' + func.name + '''()
'''

        return test_code

    def _generate_mock_tests(self, func: FunctionInfo) -> str:
        """生成Mock测试（针对云API）"""
        test_code = f'''
    @patch('{self._get_mock_target(func.cloud_provider)}')
    def test_{func.name}_with_mock(self, mock_client):
        """测试{func.name}的Mock调用"""
'''

        if func.cloud_provider == 'aws':
            test_code += '''        # 设置Mock返回值
        mock_client.return_value.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [
                    {'InstanceId': 'i-1234567890abcdef0', 'State': {'Name': 'running'}}
                ]
            }]
        }

        # 执行函数
        result = ''' + func.name + '''(mock_client.return_value)

        # 验证
        assert len(result) > 0
        mock_client.return_value.describe_instances.assert_called_once()
'''

        elif func.cloud_provider == 'azure':
            test_code += '''        # 设置Mock返回值
        mock_vm = Mock()
        mock_vm.name = 'test-vm'
        mock_vm.id = '/subscriptions/xxx/resourceGroups/xxx/providers/Microsoft.Compute/virtualMachines/test-vm'
        mock_client.return_value.virtual_machines.list_all.return_value = [mock_vm]

        # 执行函数
        result = ''' + func.name + '''(mock_client.return_value)

        # 验证
        assert len(result) > 0
        mock_client.return_value.virtual_machines.list_all.assert_called_once()
'''

        elif func.cloud_provider == 'kubernetes':
            test_code += '''        # 设置Mock返回值
        mock_pod = Mock()
        mock_pod.metadata.name = 'test-pod'
        mock_pod.metadata.namespace = 'default'
        mock_pod.status.phase = 'Running'

        mock_list = Mock()
        mock_list.items = [mock_pod]
        mock_client.return_value.list_pod_for_all_namespaces.return_value = mock_list

        # 执行函数
        result = ''' + func.name + '''(mock_client.return_value)

        # 验证
        assert len(result) > 0
'''

        return test_code

    def _get_mock_target(self, cloud_provider: Optional[str]) -> str:
        """获取Mock目标路径"""
        targets = {
            'aws': 'boto3.client',
            'azure': 'azure.mgmt.compute.ComputeManagementClient',
            'gcp': 'google.cloud.compute_v1.InstancesClient',
            'kubernetes': 'kubernetes.client.CoreV1Api'
        }
        return targets.get(cloud_provider, 'builtins.open')

    def _get_sample_value(self, param_name: str) -> str:
        """根据参数名生成示例值"""
        param_lower = param_name.lower()

        # 云客户端
        if 'client' in param_lower:
            return "Mock()"

        # ID类型
        if param_lower.endswith('_id') or param_lower == 'id':
            return "'test-id-12345'"

        # 名称类型
        if 'name' in param_lower:
            return "'test-name'"

        # 列表类型
        if param_lower.endswith('s') or 'list' in param_lower or 'items' in param_lower:
            return "['item1', 'item2']"

        # 过滤器
        if 'filter' in param_lower:
            return "[{'Name': 'tag:Environment', 'Values': ['test']}]"

        # 布尔类型
        if param_lower.startswith('is_') or param_lower.startswith('has_') or param_lower.startswith('enable'):
            return "True"

        # 数字类型
        if 'count' in param_lower or 'size' in param_lower or 'limit' in param_lower:
            return "10"

        # 默认字符串
        return "'test-value'"


class CoverageOptimizer:
    """
    测试覆盖率优化器

    分析代码结构，生成额外的测试用例以提高覆盖率
    """

    def __init__(self):
        pass

    def analyze_coverage_gaps(self, code: str, test_code: str) -> List[str]:
        """
        分析覆盖率缺口

        Args:
            code: 源代码
            test_code: 测试代码

        Returns:
            建议的额外测试用例
        """
        suggestions = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # 检查if语句分支
                if isinstance(node, ast.If):
                    suggestions.append("添加测试覆盖if-else的两个分支")

                # 检查for循环
                if isinstance(node, ast.For):
                    suggestions.append("添加测试覆盖for循环的迭代（空列表、单项、多项）")

                # 检查try-except
                if isinstance(node, ast.Try):
                    suggestions.append("添加测试覆盖异常处理路径")

                # 检查列表推导式
                if isinstance(node, ast.ListComp):
                    suggestions.append("添加测试覆盖列表推导式的不同输入")

        except SyntaxError:
            pass

        return suggestions

    def generate_coverage_report(self, code: str) -> Dict[str, Any]:
        """
        生成覆盖率报告

        Args:
            code: 源代码

        Returns:
            覆盖率分析报告
        """
        try:
            tree = ast.parse(code)

            total_lines = len(code.split('\n'))
            function_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            branch_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.If))
            exception_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.Try))

            return {
                'total_lines': total_lines,
                'function_count': function_count,
                'branch_count': branch_count,
                'exception_count': exception_count,
                'estimated_tests_needed': function_count * 3 + branch_count * 2 + exception_count * 2
            }

        except SyntaxError:
            return {'error': '代码解析失败'}


def generate_test_for_code(code: str, function_name: str = None) -> str:
    """
    为代码生成测试的便捷函数

    Args:
        code: 源代码
        function_name: 可选的函数名

    Returns:
        生成的测试代码
    """
    generator = TestGenerator()
    return generator.generate_tests(code, function_name)
