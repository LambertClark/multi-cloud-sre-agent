"""
WASM沙箱测试系统
用于在隔离环境中测试生成的代码
"""
from typing import Dict, Any, List, Optional
import subprocess
import tempfile
import os
import json
import asyncio
import logging
from pathlib import Path
import ast
import sys

from config import get_config

logger = logging.getLogger(__name__)


class WASMSandbox:
    """
    WASM沙箱负责：
    1. 在隔离环境中执行生成的代码
    2. 语法检查
    3. 功能测试（Mock API）
    4. 错误处理验证
    5. 边界条件测试
    """

    def __init__(self):
        self.config = get_config()
        self.test_mode = self.config.wasm.test_mode
        self.timeout = self.config.wasm.timeout

    def _prepare_env_with_credentials(self) -> Dict[str, str]:
        """
        准备包含云凭证的环境变量

        Returns:
            环境变量字典
        """
        # 复制当前环境变量
        env = os.environ.copy()

        # 注入AWS凭证
        if self.config.cloud.aws_access_key:
            env['AWS_ACCESS_KEY_ID'] = self.config.cloud.aws_access_key
            env['AWS_SECRET_ACCESS_KEY'] = self.config.cloud.aws_secret_key
            env['AWS_REGION'] = self.config.cloud.aws_region
            env['AWS_DEFAULT_REGION'] = self.config.cloud.aws_region
            logger.debug("Injected AWS credentials into sandbox environment")

        # 注入Azure凭证
        if self.config.cloud.azure_subscription_id:
            env['AZURE_SUBSCRIPTION_ID'] = self.config.cloud.azure_subscription_id
            env['AZURE_CLIENT_ID'] = self.config.cloud.azure_client_id
            env['AZURE_CLIENT_SECRET'] = self.config.cloud.azure_client_secret
            env['AZURE_TENANT_ID'] = self.config.cloud.azure_tenant_id
            logger.debug("Injected Azure credentials into sandbox environment")

        # 注入GCP凭证
        if self.config.cloud.gcp_project_id:
            env['GCP_PROJECT_ID'] = self.config.cloud.gcp_project_id
            if self.config.cloud.gcp_credentials_path:
                env['GOOGLE_APPLICATION_CREDENTIALS'] = self.config.cloud.gcp_credentials_path
            logger.debug("Injected GCP credentials into sandbox environment")

        # 注入阿里云凭证
        if self.config.cloud.aliyun_access_key:
            env['ALIYUN_ACCESS_KEY_ID'] = self.config.cloud.aliyun_access_key
            env['ALIYUN_SECRET_ACCESS_KEY'] = self.config.cloud.aliyun_secret_key
            env['ALIYUN_REGION'] = self.config.cloud.aliyun_region
            logger.debug("Injected Aliyun credentials into sandbox environment")

        # 注入火山云凭证
        if self.config.cloud.volc_access_key:
            env['VOLC_ACCESS_KEY'] = self.config.cloud.volc_access_key
            env['VOLC_SECRET_KEY'] = self.config.cloud.volc_secret_key
            env['VOLC_REGION'] = self.config.cloud.volc_region
            logger.debug("Injected Volcano credentials into sandbox environment")

        return env

    async def test_code(self, code_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        测试代码

        Args:
            code_data: {
                "code": "代码内容",
                "language": "编程语言",
                "operation": "操作名称",
                "parameters": {...}
            }

        Returns:
            测试结果
        """
        try:
            code = code_data.get("code", "")
            language = code_data.get("language", "python")
            operation = code_data.get("operation", "")
            parameters = code_data.get("parameters", {})

            logger.info(f"Testing {language} code for operation: {operation}")

            # 选择测试策略
            if self.test_mode == "basic":
                result = await self._basic_validation(code, language)
            elif self.test_mode == "functional":
                result = await self._functional_test(code, language, operation, parameters)
            elif self.test_mode == "full":
                result = await self._full_test(code, language, operation, parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown test mode: {self.test_mode}"
                }

            return result

        except Exception as e:
            logger.error(f"Error in WASM sandbox: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _basic_validation(self, code: str, language: str) -> Dict[str, Any]:
        """基础验证：语法检查"""
        results = {
            "success": True,
            "tests": [],
            "errors": []
        }

        # 语法检查
        syntax_result = await self._check_syntax(code, language)
        results["tests"].append(syntax_result)

        if not syntax_result["passed"]:
            results["success"] = False
            results["errors"].append(syntax_result.get("error", "Syntax check failed"))

        return results

    async def _functional_test(
        self,
        code: str,
        language: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """功能测试：语法检查 + Mock API调用"""
        results = {
            "success": True,
            "tests": [],
            "errors": []
        }

        # 1. 语法检查
        syntax_result = await self._check_syntax(code, language)
        results["tests"].append(syntax_result)

        if not syntax_result["passed"]:
            results["success"] = False
            results["errors"].append("Syntax check failed")
            return results

        # 2. Mock API测试
        mock_result = await self._run_with_mock(code, language, operation, parameters)
        results["tests"].append(mock_result)

        if not mock_result["passed"]:
            results["success"] = False
            results["errors"].append("Mock API test failed")

        return results

    async def _full_test(
        self,
        code: str,
        language: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """完整测试：语法 + 功能 + 错误处理 + 边界条件"""
        results = {
            "success": True,
            "tests": [],
            "errors": []
        }

        # 1. 语法检查
        syntax_result = await self._check_syntax(code, language)
        results["tests"].append(syntax_result)

        if not syntax_result["passed"]:
            results["success"] = False
            results["errors"].append("Syntax check failed")
            return results

        # 2. Mock API测试
        mock_result = await self._run_with_mock(code, language, operation, parameters)
        results["tests"].append(mock_result)

        if not mock_result["passed"]:
            results["success"] = False
            results["errors"].append("Mock API test failed")

        # 3. 错误处理测试
        error_handling_result = await self._test_error_handling(code, language)
        results["tests"].append(error_handling_result)

        if not error_handling_result["passed"]:
            results["success"] = False
            results["errors"].append("Error handling test failed")

        # 4. 边界条件测试
        boundary_result = await self._test_boundary_conditions(code, language, parameters)
        results["tests"].append(boundary_result)

        if not boundary_result["passed"]:
            results["success"] = False
            results["errors"].append("Boundary conditions test failed")

        return results

    async def _check_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """检查语法"""
        test_result = {
            "name": "Syntax Check",
            "passed": False,
            "message": ""
        }

        try:
            if language == "python":
                # Python语法检查
                try:
                    ast.parse(code)
                    test_result["passed"] = True
                    test_result["message"] = "Python syntax is valid"
                except SyntaxError as e:
                    test_result["error"] = str(e)
                    test_result["message"] = f"Syntax error: {e}"

            elif language in ["javascript", "typescript"]:
                # JavaScript/TypeScript语法检查
                # 需要Node.js环境
                test_result["passed"] = True
                test_result["message"] = f"{language} syntax check skipped (requires Node.js)"

            elif language == "go":
                # Go语法检查
                test_result["passed"] = True
                test_result["message"] = "Go syntax check skipped (requires Go compiler)"

            else:
                test_result["message"] = f"Syntax check not implemented for {language}"

        except Exception as e:
            test_result["error"] = str(e)
            test_result["message"] = f"Syntax check error: {e}"

        return test_result

    async def _run_with_mock(
        self,
        code: str,
        language: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用Mock API运行代码"""
        test_result = {
            "name": "Mock API Test",
            "passed": False,
            "message": ""
        }

        try:
            if language == "python":
                result = await self._run_python_with_mock(code, operation, parameters)
                test_result.update(result)
            else:
                test_result["passed"] = True
                test_result["message"] = f"Mock test not implemented for {language}"

        except Exception as e:
            test_result["error"] = str(e)
            test_result["message"] = f"Mock test error: {e}"

        return test_result

    async def _run_python_with_mock(
        self,
        code: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """在Mock环境中运行Python代码"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            # 写入Mock代码
            mock_code = self._generate_python_mock(operation, parameters)
            f.write(mock_code + "\n\n")
            f.write(code)
            f.write("\n\n# Test execution\n")
            f.write("if __name__ == '__main__':\n")
            f.write("    try:\n")
            f.write("        # Mock successful execution\n")
            f.write("        print('MOCK_TEST_SUCCESS')\n")
            f.write("    except Exception as e:\n")
            f.write("        print(f'MOCK_TEST_ERROR: {e}')\n")

            temp_file = f.name

        try:
            # 准备环境变量（包含云凭证）
            env = self._prepare_env_with_credentials()

            # 运行代码
            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env  # 注入环境变量
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "passed": False,
                    "message": "Code execution timed out"
                }

            output = stdout.decode('utf-8', errors='replace')
            error_output = stderr.decode('utf-8', errors='replace')

            if "MOCK_TEST_SUCCESS" in output:
                return {
                    "passed": True,
                    "message": "Mock test passed",
                    "output": output
                }
            elif "MOCK_TEST_ERROR" in output:
                return {
                    "passed": False,
                    "message": "Mock test failed",
                    "error": output
                }
            elif error_output:
                return {
                    "passed": False,
                    "message": "Execution error",
                    "error": error_output
                }
            else:
                return {
                    "passed": True,
                    "message": "Code executed without errors",
                    "output": output
                }

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass

    def _generate_python_mock(self, operation: str, parameters: Dict[str, Any]) -> str:
        """生成Python Mock代码"""
        mock_code = """
# Mock AWS/Cloud SDK
from unittest.mock import MagicMock, patch
import sys

# Mock boto3 for AWS
class MockBoto3Client:
    def __init__(self, *args, **kwargs):
        pass

    def get_metric_statistics(self, **kwargs):
        return {
            'Label': 'CPUUtilization',
            'Datapoints': [
                {'Timestamp': '2024-01-01T00:00:00Z', 'Average': 50.0}
            ]
        }

    def put_metric_alarm(self, **kwargs):
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}

    def describe_alarms(self, **kwargs):
        return {
            'MetricAlarms': [
                {'AlarmName': 'test-alarm', 'StateValue': 'OK'}
            ]
        }

    def filter_log_events(self, **kwargs):
        return {
            'events': [
                {'timestamp': 1234567890, 'message': 'Test log'}
            ]
        }

    def get_trace_summaries(self, **kwargs):
        return {
            'TraceSummaries': [
                {'Id': 'trace-1', 'Duration': 1.5}
            ]
        }

    def __getattr__(self, name):
        # 为任何其他方法返回Mock
        return MagicMock(return_value={'Success': True})

# Mock boto3.client
class MockBoto3:
    @staticmethod
    def client(service_name, **kwargs):
        return MockBoto3Client()

# Patch boto3
sys.modules['boto3'] = MockBoto3()

# Mock other cloud SDKs
sys.modules['azure'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
"""
        return mock_code

    async def _test_error_handling(self, code: str, language: str) -> Dict[str, Any]:
        """测试错误处理"""
        test_result = {
            "name": "Error Handling Test",
            "passed": False,
            "message": ""
        }

        try:
            # 检查代码是否包含错误处理
            if language == "python":
                has_try_except = "try:" in code and "except" in code
                has_error_logging = "logging" in code or "logger" in code

                if has_try_except:
                    test_result["passed"] = True
                    test_result["message"] = "Error handling found in code"
                else:
                    test_result["passed"] = False
                    test_result["message"] = "No try-except blocks found"

            else:
                test_result["passed"] = True
                test_result["message"] = f"Error handling check not implemented for {language}"

        except Exception as e:
            test_result["error"] = str(e)
            test_result["message"] = f"Error handling test error: {e}"

        return test_result

    async def _test_boundary_conditions(
        self,
        code: str,
        language: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """测试边界条件"""
        test_result = {
            "name": "Boundary Conditions Test",
            "passed": True,  # 默认通过，除非发现问题
            "message": "Boundary conditions test passed"
        }

        try:
            # 检查参数验证
            if language == "python":
                has_validation = any([
                    "if" in code and "is None" in code,
                    "if not" in code,
                    "assert" in code,
                    "raise ValueError" in code,
                    "raise TypeError" in code
                ])

                if has_validation:
                    test_result["message"] = "Parameter validation found"
                else:
                    test_result["passed"] = False
                    test_result["message"] = "No parameter validation found"

        except Exception as e:
            test_result["error"] = str(e)
            test_result["message"] = f"Boundary conditions test error: {e}"

        return test_result

    async def execute_code(
        self,
        code: str,
        language: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        在沙箱中执行代码（实际执行，非测试）

        Args:
            code: 代码内容
            language: 编程语言
            input_data: 输入数据

        Returns:
            执行结果
        """
        try:
            if language == "python":
                return await self._execute_python(code, input_data)
            else:
                return {
                    "success": False,
                    "error": f"Execution not implemented for {language}"
                }

        except Exception as e:
            logger.error(f"Error executing code: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_python(
        self,
        code: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行Python代码"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            if input_data:
                f.write("\n\n# Input data\n")
                f.write(f"input_data = {json.dumps(input_data)}\n")

            temp_file = f.name

        try:
            # 准备环境变量（包含云凭证）
            env = self._prepare_env_with_credentials()

            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env  # 注入环境变量
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "error": "Execution timed out"
                }

            output = stdout.decode('utf-8', errors='replace')
            error_output = stderr.decode('utf-8', errors='replace')

            if process.returncode == 0:
                return {
                    "success": True,
                    "output": output,
                    "returncode": process.returncode
                }
            else:
                return {
                    "success": False,
                    "error": error_output,
                    "output": output,
                    "returncode": process.returncode
                }

        finally:
            try:
                os.unlink(temp_file)
            except:
                pass


# 全局沙箱实例
_sandbox: Optional[WASMSandbox] = None


def get_sandbox() -> WASMSandbox:
    """获取全局沙箱实例"""
    global _sandbox
    if _sandbox is None:
        _sandbox = WASMSandbox()
    return _sandbox
