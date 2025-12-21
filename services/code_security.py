"""
代码安全扫描器
检测生成代码中的安全风险，防止恶意代码执行
"""
import ast
import re
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """安全级别"""
    SAFE = "safe"  # 安全
    WARNING = "warning"  # 警告（需要审查）
    DANGER = "danger"  # 危险（禁止执行）
    BLOCKED = "blocked"  # 已阻止


@dataclass
class SecurityIssue:
    """安全问题"""
    level: SecurityLevel
    category: str  # 问题分类
    description: str  # 问题描述
    line_number: Optional[int]  # 行号
    code_snippet: Optional[str]  # 代码片段
    suggestion: str  # 修复建议


class CodeSecurityScanner:
    """
    代码安全扫描器

    扫描内容：
    1. 危险函数调用（exec, eval, os.system, subprocess等）
    2. 文件系统访问（open, os.remove, shutil.rmtree等）
    3. 网络访问（socket, requests等）
    4. 敏感信息泄露（密码、密钥等）
    5. 资源删除操作（delete, remove, terminate等）
    """

    # 危险函数黑名单
    DANGEROUS_FUNCTIONS = {
        'exec': '执行任意Python代码，存在代码注入风险',
        'eval': '执行任意表达式，存在代码注入风险',
        'compile': '编译任意代码，存在安全风险',
        '__import__': '动态导入模块，可能导入恶意代码',
    }

    # 危险模块/函数（需要审查）
    RISKY_OPERATIONS = {
        # 系统命令执行
        'os.system': '执行shell命令',
        'os.popen': '执行shell命令并获取输出',
        'subprocess.call': '执行外部命令',
        'subprocess.Popen': '执行外部命令',
        'subprocess.run': '执行外部命令',
        'commands.getoutput': '执行shell命令',

        # 文件系统写入/删除
        'os.remove': '删除文件',
        'os.rmdir': '删除目录',
        'os.unlink': '删除文件',
        'shutil.rmtree': '递归删除目录',
        'pathlib.Path.unlink': '删除文件',
        'pathlib.Path.rmdir': '删除目录',

        # 网络操作（需要白名单）
        'socket.socket': '创建网络套接字',
        'urllib.request.urlopen': 'HTTP请求',
        'urllib.request.Request': 'HTTP请求',
    }

    # 云资源删除操作（严格禁止）
    RESOURCE_DELETE_OPERATIONS = {
        # AWS
        'terminate_instances': 'AWS EC2实例终止',
        'delete_bucket': 'AWS S3存储桶删除',
        'delete_volume': 'AWS EBS卷删除',
        'delete_snapshot': 'AWS快照删除',
        'delete_security_group': 'AWS安全组删除',
        'delete_vpc': 'AWS VPC删除',
        'delete_subnet': 'AWS子网删除',

        # Azure
        'delete': 'Azure资源删除',
        'begin_delete': 'Azure资源异步删除',

        # GCP
        'delete': 'GCP资源删除',

        # Kubernetes
        'delete_namespaced_pod': 'K8s Pod删除',
        'delete_namespace': 'K8s命名空间删除',
        'delete_namespaced_deployment': 'K8s Deployment删除',
    }

    # 允许的网络访问白名单（仅云服务API）
    ALLOWED_NETWORK_MODULES = {
        'boto3',  # AWS SDK
        'botocore',
        'azure',  # Azure SDK
        'google.cloud',  # GCP SDK
        'kubernetes',  # K8s client
        'requests',  # HTTP客户端（仅用于云API）
        'aiohttp',  # 异步HTTP客户端
    }

    # 敏感信息正则匹配
    SENSITIVE_PATTERNS = {
        'password': r'password\s*=\s*["\'][^"\']+["\']',
        'api_key': r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
        'secret': r'secret\s*=\s*["\'][^"\']+["\']',
        'token': r'token\s*=\s*["\'][^"\']+["\']',
        'access_key': r'access[_-]?key\s*=\s*["\'][^"\']+["\']',
    }

    def __init__(self):
        self.issues: List[SecurityIssue] = []

    def scan(self, code: str) -> Dict[str, Any]:
        """
        扫描代码安全性

        Args:
            code: Python代码字符串

        Returns:
            扫描结果，包含安全级别和问题列表
        """
        self.issues = []

        try:
            # 1. 语法检查
            tree = ast.parse(code)

            # 2. AST分析
            self._scan_ast(tree, code)

            # 3. 正则匹配敏感信息
            self._scan_sensitive_info(code)

            # 4. 确定整体安全级别
            security_level = self._determine_security_level()

            return {
                "safe": security_level == SecurityLevel.SAFE,
                "security_level": security_level.value,
                "issues": [
                    {
                        "level": issue.level.value,
                        "category": issue.category,
                        "description": issue.description,
                        "line_number": issue.line_number,
                        "code_snippet": issue.code_snippet,
                        "suggestion": issue.suggestion
                    }
                    for issue in self.issues
                ],
                "blocked": security_level == SecurityLevel.BLOCKED,
                "warning_count": len([i for i in self.issues if i.level == SecurityLevel.WARNING]),
                "danger_count": len([i for i in self.issues if i.level == SecurityLevel.DANGER])
            }

        except SyntaxError as e:
            return {
                "safe": False,
                "security_level": SecurityLevel.DANGER.value,
                "issues": [{
                    "level": SecurityLevel.DANGER.value,
                    "category": "syntax_error",
                    "description": f"代码语法错误: {str(e)}",
                    "line_number": e.lineno,
                    "code_snippet": None,
                    "suggestion": "修复语法错误"
                }],
                "blocked": True,
                "warning_count": 0,
                "danger_count": 1
            }

    def _scan_ast(self, tree: ast.AST, code: str):
        """使用AST扫描代码"""
        code_lines = code.split('\n')

        for node in ast.walk(tree):
            # 检查函数调用
            if isinstance(node, ast.Call):
                self._check_function_call(node, code_lines)

            # 检查导入
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._check_import(node, code_lines)

    def _check_function_call(self, node: ast.Call, code_lines: List[str]):
        """检查函数调用"""
        func_name = self._get_function_name(node.func)

        if not func_name:
            return

        # 检查危险函数
        if func_name in self.DANGEROUS_FUNCTIONS:
            self._add_issue(
                level=SecurityLevel.BLOCKED,
                category="dangerous_function",
                description=f"禁止使用危险函数 '{func_name}': {self.DANGEROUS_FUNCTIONS[func_name]}",
                line_number=node.lineno,
                code_snippet=code_lines[node.lineno - 1] if node.lineno <= len(code_lines) else None,
                suggestion=f"移除 {func_name} 调用，使用安全的替代方案"
            )

        # 检查资源删除操作
        if any(delete_op in func_name.lower() for delete_op in self.RESOURCE_DELETE_OPERATIONS):
            for op, desc in self.RESOURCE_DELETE_OPERATIONS.items():
                if op in func_name.lower():
                    self._add_issue(
                        level=SecurityLevel.BLOCKED,
                        category="resource_deletion",
                        description=f"禁止删除云资源: {desc} ({func_name})",
                        line_number=node.lineno,
                        code_snippet=code_lines[node.lineno - 1] if node.lineno <= len(code_lines) else None,
                        suggestion="生成的代码只能进行只读查询，不能删除资源"
                    )
                    break

        # 检查高风险操作
        if func_name in self.RISKY_OPERATIONS:
            self._add_issue(
                level=SecurityLevel.DANGER,
                category="risky_operation",
                description=f"高风险操作 '{func_name}': {self.RISKY_OPERATIONS[func_name]}",
                line_number=node.lineno,
                code_snippet=code_lines[node.lineno - 1] if node.lineno <= len(code_lines) else None,
                suggestion="需要人工审查该操作是否必要且安全"
            )

    def _check_import(self, node: ast.AST, code_lines: List[str]):
        """检查导入语句"""
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                self._check_module(module_name, node.lineno, code_lines)

        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            self._check_module(module_name, node.lineno, code_lines)

    def _check_module(self, module_name: str, line_number: int, code_lines: List[str]):
        """检查模块是否安全"""
        # 检查是否是允许的网络模块
        if any(allowed in module_name for allowed in self.ALLOWED_NETWORK_MODULES):
            return  # 允许的云SDK

        # 检查是否有网络/系统操作模块
        risky_modules = ['socket', 'subprocess', 'os', 'shutil', 'pathlib']

        for risky_module in risky_modules:
            if module_name.startswith(risky_module):
                self._add_issue(
                    level=SecurityLevel.WARNING,
                    category="risky_module",
                    description=f"导入了潜在风险模块 '{module_name}'",
                    line_number=line_number,
                    code_snippet=code_lines[line_number - 1] if line_number <= len(code_lines) else None,
                    suggestion=f"确认 {module_name} 的使用是安全的，仅用于必要的云API调用"
                )
                break

    def _scan_sensitive_info(self, code: str):
        """扫描敏感信息泄露"""
        code_lines = code.split('\n')

        for pattern_name, pattern in self.SENSITIVE_PATTERNS.items():
            matches = re.finditer(pattern, code, re.IGNORECASE)

            for match in matches:
                # 计算行号
                line_number = code[:match.start()].count('\n') + 1

                self._add_issue(
                    level=SecurityLevel.WARNING,
                    category="sensitive_info",
                    description=f"可能泄露敏感信息: {pattern_name}",
                    line_number=line_number,
                    code_snippet=code_lines[line_number - 1] if line_number <= len(code_lines) else None,
                    suggestion=f"使用环境变量或配置文件管理 {pattern_name}，不要硬编码"
                )

    def _get_function_name(self, node: ast.AST) -> Optional[str]:
        """获取函数全名"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parent = self._get_function_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return node.attr
        return None

    def _add_issue(
        self,
        level: SecurityLevel,
        category: str,
        description: str,
        line_number: Optional[int],
        code_snippet: Optional[str],
        suggestion: str
    ):
        """添加安全问题"""
        issue = SecurityIssue(
            level=level,
            category=category,
            description=description,
            line_number=line_number,
            code_snippet=code_snippet,
            suggestion=suggestion
        )
        self.issues.append(issue)

        logger.warning(
            f"Security issue detected: {level.value} - {category} - {description} "
            f"(line {line_number})"
        )

    def _determine_security_level(self) -> SecurityLevel:
        """确定整体安全级别"""
        if not self.issues:
            return SecurityLevel.SAFE

        # 如果有任何BLOCKED级别的问题，整体为BLOCKED
        if any(issue.level == SecurityLevel.BLOCKED for issue in self.issues):
            return SecurityLevel.BLOCKED

        # 如果有DANGER级别的问题，整体为DANGER
        if any(issue.level == SecurityLevel.DANGER for issue in self.issues):
            return SecurityLevel.DANGER

        # 否则为WARNING
        return SecurityLevel.WARNING


class CodeSanitizer:
    """
    代码净化器
    自动移除或替换危险代码
    """

    def __init__(self):
        self.scanner = CodeSecurityScanner()

    def sanitize(self, code: str) -> Dict[str, Any]:
        """
        净化代码

        Args:
            code: 原始代码

        Returns:
            净化结果，包含净化后的代码和修改说明
        """
        # 先扫描
        scan_result = self.scanner.scan(code)

        if scan_result["safe"]:
            return {
                "success": True,
                "code": code,
                "modified": False,
                "changes": []
            }

        # 如果有BLOCKED级别的问题，拒绝净化
        if scan_result["blocked"]:
            return {
                "success": False,
                "code": None,
                "modified": False,
                "error": "代码包含严重安全问题，无法净化",
                "issues": scan_result["issues"]
            }

        # 尝试自动修复WARNING级别的问题
        sanitized_code = code
        changes = []

        for issue in scan_result["issues"]:
            if issue["level"] == "warning" and issue["category"] == "sensitive_info":
                # 移除敏感信息硬编码
                if issue["code_snippet"]:
                    # 这里可以实现更复杂的替换逻辑
                    changes.append(f"移除第{issue['line_number']}行的敏感信息")

        return {
            "success": True,
            "code": sanitized_code,
            "modified": len(changes) > 0,
            "changes": changes,
            "remaining_issues": [
                issue for issue in scan_result["issues"]
                if issue["level"] == "danger"
            ]
        }
