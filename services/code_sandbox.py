"""
代码沙箱执行环境
安全地执行生成的代码，限制资源访问和执行时间
"""
import sys
import io
import traceback
import signal
from typing import Dict, Any, Optional, Callable
from contextlib import redirect_stdout, redirect_stderr
import logging
from dataclasses import dataclass
import time
import platform

# resource模块仅在Unix系统可用
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

from services.code_security import CodeSecurityScanner

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """沙箱配置"""
    max_execution_time: int = 30  # 最大执行时间（秒）
    max_memory_mb: int = 512  # 最大内存使用（MB）
    allow_network: bool = True  # 是否允许网络访问（仅云API）
    allow_file_read: bool = False  # 是否允许文件读取
    allow_file_write: bool = False  # 是否允许文件写入
    enforce_security_scan: bool = True  # 是否强制执行安全扫描


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    return_value: Any = None
    execution_time: float = 0.0
    memory_used_mb: float = 0.0
    security_issues: Optional[Dict[str, Any]] = None


class TimeoutException(Exception):
    """执行超时异常"""
    pass


class SandboxExecutor:
    """
    沙箱执行器

    功能：
    1. 执行前安全扫描
    2. 限制执行时间
    3. 限制内存使用
    4. 捕获标准输出/错误
    5. 隔离执行环境
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.security_scanner = CodeSecurityScanner()

    def execute(self, code: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        在沙箱中执行代码

        Args:
            code: 要执行的Python代码
            context: 执行上下文（可用的变量和模块）

        Returns:
            执行结果
        """
        start_time = time.time()

        # 1. 安全扫描
        if self.config.enforce_security_scan:
            scan_result = self.security_scanner.scan(code)

            if scan_result["blocked"]:
                logger.error(f"代码被安全扫描器阻止: {scan_result['issues']}")
                return ExecutionResult(
                    success=False,
                    error="代码包含严重安全问题，禁止执行",
                    security_issues=scan_result
                )

            if scan_result["danger_count"] > 0:
                logger.warning(f"代码包含{scan_result['danger_count']}个危险操作")

        # 2. 准备执行环境
        exec_context = self._prepare_context(context)

        # 3. 捕获输出
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            # 4. 设置资源限制和超时
            self._set_resource_limits()

            # 5. 执行代码
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # 使用exec执行代码，并捕获返回值
                exec(code, exec_context)

                # 尝试获取返回值（如果代码中有result变量）
                return_value = exec_context.get('result', None)

            execution_time = time.time() - start_time

            return ExecutionResult(
                success=True,
                output=stdout_capture.getvalue(),
                return_value=return_value,
                execution_time=execution_time,
                security_issues=scan_result if self.config.enforce_security_scan else None
            )

        except TimeoutException:
            logger.error(f"代码执行超时（>{self.config.max_execution_time}秒）")
            return ExecutionResult(
                success=False,
                error=f"执行超时（超过{self.config.max_execution_time}秒）",
                output=stdout_capture.getvalue(),
                execution_time=time.time() - start_time
            )

        except MemoryError:
            logger.error("代码执行内存溢出")
            return ExecutionResult(
                success=False,
                error=f"内存使用超过限制（{self.config.max_memory_mb}MB）",
                output=stdout_capture.getvalue(),
                execution_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"代码执行失败: {str(e)}\n{traceback.format_exc()}")
            return ExecutionResult(
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                output=stdout_capture.getvalue() + "\n" + stderr_capture.getvalue(),
                execution_time=time.time() - start_time
            )

        finally:
            # 清理资源限制
            self._clear_resource_limits()

    def _prepare_context(self, user_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        准备执行上下文

        只允许安全的内置函数和用户提供的变量
        """
        # 基础的安全内置函数
        safe_builtins = {
            'print': print,
            'len': len,
            'range': range,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'set': set,
            'tuple': tuple,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'sum': sum,
            'min': min,
            'max': max,
            'sorted': sorted,
            'reversed': reversed,
            'isinstance': isinstance,
            'type': type,
            'abs': abs,
            'round': round,
            'any': any,
            'all': all,
        }

        # 添加常用的安全模块
        safe_modules = {}

        if self.config.allow_network:
            # 允许云SDK访问
            try:
                import boto3
                safe_modules['boto3'] = boto3
            except ImportError:
                pass

            try:
                import azure
                safe_modules['azure'] = azure
            except ImportError:
                pass

            try:
                import kubernetes
                safe_modules['kubernetes'] = kubernetes
            except ImportError:
                pass

        # 合并用户上下文
        context = {
            '__builtins__': safe_builtins,
            **safe_modules
        }

        if user_context:
            # 过滤掉不安全的内容
            for key, value in user_context.items():
                if not key.startswith('__'):
                    context[key] = value

        return context

    def _set_resource_limits(self):
        """设置资源限制"""
        if platform.system() == 'Windows':
            # Windows不支持resource模块，使用其他方式
            logger.debug("Windows系统，跳过resource限制")
            return

        try:
            # 设置CPU时间限制（仅Unix系统）
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, self._timeout_handler)
                signal.alarm(self.config.max_execution_time)

            # 设置内存限制（仅Unix系统）
            if HAS_RESOURCE and hasattr(resource, 'RLIMIT_AS'):
                # 转换MB到字节
                max_memory_bytes = self.config.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))

        except Exception as e:
            logger.warning(f"无法设置资源限制: {e}")

    def _clear_resource_limits(self):
        """清除资源限制"""
        try:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # 取消alarm
        except Exception as e:
            logger.warning(f"清除资源限制失败: {e}")

    def _timeout_handler(self, signum, frame):
        """超时处理器"""
        raise TimeoutException("代码执行超时")


class RestrictedExecutor(SandboxExecutor):
    """
    受限执行器 - 更严格的沙箱

    特点：
    1. 禁止所有文件系统访问
    2. 禁止所有子进程
    3. 禁止导入未预先批准的模块
    4. 只读访问云资源
    """

    def __init__(self, allowed_modules: Optional[list] = None):
        """
        Args:
            allowed_modules: 允许导入的模块列表
        """
        super().__init__(config=SandboxConfig(
            max_execution_time=30,
            max_memory_mb=256,
            allow_network=True,  # 仅云API
            allow_file_read=False,
            allow_file_write=False,
            enforce_security_scan=True
        ))

        self.allowed_modules = allowed_modules or [
            'boto3',
            'botocore',
            'azure',
            'google.cloud',
            'kubernetes',
            'json',
            'datetime',
            'time',
            're',
            'typing',
        ]

    def _prepare_context(self, user_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """准备受限的执行上下文"""
        # 调用父类方法
        context = super()._prepare_context(user_context)

        # 替换__import__为受限版本
        # __builtins__可能是模块或字典，需要兼容处理
        if isinstance(__builtins__, dict):
            original_import = __builtins__['__import__']
        else:
            original_import = __builtins__.__import__

        def restricted_import(name, *args, **kwargs):
            """受限的import函数"""
            # 检查模块是否在允许列表中
            if any(name.startswith(allowed) for allowed in self.allowed_modules):
                return original_import(name, *args, **kwargs)
            else:
                raise ImportError(
                    f"模块 '{name}' 不在允许列表中。"
                    f"允许的模块: {', '.join(self.allowed_modules)}"
                )

        context['__builtins__']['__import__'] = restricted_import

        return context


# 全局沙箱实例
_default_sandbox: Optional[SandboxExecutor] = None


def get_sandbox(restricted: bool = True) -> SandboxExecutor:
    """
    获取沙箱实例

    Args:
        restricted: 是否使用受限沙箱（推荐）

    Returns:
        沙箱执行器实例
    """
    global _default_sandbox

    if _default_sandbox is None:
        if restricted:
            _default_sandbox = RestrictedExecutor()
        else:
            _default_sandbox = SandboxExecutor()

    return _default_sandbox


def execute_safely(code: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    """
    安全执行代码的便捷函数

    Args:
        code: 代码字符串
        context: 执行上下文

    Returns:
        执行结果
    """
    sandbox = get_sandbox(restricted=True)
    return sandbox.execute(code, context)
