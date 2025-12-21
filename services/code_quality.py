"""
代码质量分析工具
使用多种静态分析工具检查生成代码的质量
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import tempfile
import subprocess
import os
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """代码质量问题"""
    tool: str  # 工具名称（pylint/flake8/mypy）
    severity: str  # 严重程度（error/warning/info）
    line: int  # 行号
    column: int  # 列号
    message: str  # 问题描述
    code: str  # 错误代码（如E501）
    suggestion: Optional[str] = None  # 修复建议


class CodeQualityAnalyzer:
    """
    代码质量分析器

    集成多种静态分析工具：
    1. Flake8：代码风格检查（PEP8）
    2. Pylint：代码质量检查
    3. Mypy：类型检查（可选）
    """

    def __init__(self, enable_mypy: bool = False):
        """
        Args:
            enable_mypy: 是否启用mypy类型检查（较严格）
        """
        self.enable_mypy = enable_mypy

    def analyze(self, code: str, filename: str = "generated_code.py") -> Dict[str, Any]:
        """
        分析代码质量

        Args:
            code: Python代码
            filename: 文件名（用于报告）

        Returns:
            分析结果
        """
        issues = []

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name

        try:
            # 1. Flake8检查
            flake8_issues = self._run_flake8(temp_file)
            issues.extend(flake8_issues)

            # 2. Pylint检查（更宽松的配置）
            pylint_issues = self._run_pylint(temp_file)
            issues.extend(pylint_issues)

            # 3. Mypy类型检查（可选）
            if self.enable_mypy:
                mypy_issues = self._run_mypy(temp_file)
                issues.extend(mypy_issues)

            # 统计
            error_count = sum(1 for i in issues if i.severity == 'error')
            warning_count = sum(1 for i in issues if i.severity == 'warning')
            info_count = sum(1 for i in issues if i.severity == 'info')

            # 计算质量分数（0-100）
            quality_score = self._calculate_score(issues, code)

            return {
                "success": True,
                "quality_score": quality_score,
                "total_issues": len(issues),
                "error_count": error_count,
                "warning_count": warning_count,
                "info_count": info_count,
                "issues": [
                    {
                        "tool": i.tool,
                        "severity": i.severity,
                        "line": i.line,
                        "column": i.column,
                        "message": i.message,
                        "code": i.code,
                        "suggestion": i.suggestion
                    }
                    for i in issues
                ],
                "passed": error_count == 0 and quality_score >= 60
            }

        except Exception as e:
            logger.error(f"代码质量分析失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

        finally:
            # 删除临时文件
            try:
                os.unlink(temp_file)
            except:
                pass

    def _run_flake8(self, filepath: str) -> List[QualityIssue]:
        """运行Flake8检查"""
        issues = []

        try:
            # Flake8配置：忽略一些不重要的规则
            # E501: 行太长（放宽到120字符）
            # W503: 运算符前换行（与PEP8冲突）
            # E203: 冒号前空格（与black冲突）
            result = subprocess.run(
                ['flake8', filepath, '--max-line-length=120', '--extend-ignore=W503,E203'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        # 解析格式：file.py:line:col: code message
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            try:
                                line_num = int(parts[1])
                                col_num = int(parts[2])
                                msg_part = parts[3].strip()

                                # 提取错误代码和消息
                                if ' ' in msg_part:
                                    code, message = msg_part.split(' ', 1)
                                else:
                                    code, message = msg_part, ""

                                # 判断严重程度
                                severity = 'error' if code.startswith('E') or code.startswith('F') else 'warning'

                                issues.append(QualityIssue(
                                    tool='flake8',
                                    severity=severity,
                                    line=line_num,
                                    column=col_num,
                                    message=message,
                                    code=code,
                                    suggestion=self._get_flake8_suggestion(code)
                                ))
                            except (ValueError, IndexError):
                                continue

        except FileNotFoundError:
            logger.warning("Flake8未安装，跳过检查")
        except subprocess.TimeoutExpired:
            logger.warning("Flake8检查超时")
        except Exception as e:
            logger.warning(f"Flake8检查失败: {e}")

        return issues

    def _run_pylint(self, filepath: str) -> List[QualityIssue]:
        """运行Pylint检查"""
        issues = []

        try:
            # Pylint配置：生成JSON输出，禁用一些不必要的检查
            result = subprocess.run(
                [
                    'pylint', filepath,
                    '--output-format=json',
                    '--disable=C0111,C0103,R0913,R0914',  # 禁用文档、命名、参数过多等
                    '--max-line-length=120'
                ],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.stdout:
                try:
                    pylint_results = json.loads(result.stdout)

                    for item in pylint_results:
                        # 映射Pylint严重程度
                        severity_map = {
                            'error': 'error',
                            'warning': 'warning',
                            'refactor': 'info',
                            'convention': 'info',
                            'information': 'info'
                        }
                        severity = severity_map.get(item.get('type', 'info'), 'info')

                        # 只报告error和warning，忽略info
                        if severity in ['error', 'warning']:
                            issues.append(QualityIssue(
                                tool='pylint',
                                severity=severity,
                                line=item.get('line', 0),
                                column=item.get('column', 0),
                                message=item.get('message', ''),
                                code=item.get('symbol', item.get('message-id', '')),
                                suggestion=None
                            ))

                except json.JSONDecodeError:
                    logger.warning("无法解析Pylint输出")

        except FileNotFoundError:
            logger.warning("Pylint未安装，跳过检查")
        except subprocess.TimeoutExpired:
            logger.warning("Pylint检查超时")
        except Exception as e:
            logger.warning(f"Pylint检查失败: {e}")

        return issues

    def _run_mypy(self, filepath: str) -> List[QualityIssue]:
        """运行Mypy类型检查"""
        issues = []

        try:
            result = subprocess.run(
                ['mypy', filepath, '--show-error-codes', '--no-error-summary'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if ':' in line and 'error:' in line:
                        # 解析格式：file.py:line: error: message [code]
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            try:
                                line_num = int(parts[1].strip())
                                msg_part = parts[2].strip()

                                if 'error:' in msg_part:
                                    message = msg_part.split('error:', 1)[1].strip()

                                    # 提取错误代码
                                    code = ''
                                    if '[' in message and ']' in message:
                                        code = message[message.rfind('[')+1:message.rfind(']')]
                                        message = message[:message.rfind('[')].strip()

                                    issues.append(QualityIssue(
                                        tool='mypy',
                                        severity='warning',  # 类型错误作为警告
                                        line=line_num,
                                        column=0,
                                        message=message,
                                        code=code or 'type-error'
                                    ))
                            except (ValueError, IndexError):
                                continue

        except FileNotFoundError:
            logger.debug("Mypy未安装，跳过检查")
        except subprocess.TimeoutExpired:
            logger.warning("Mypy检查超时")
        except Exception as e:
            logger.warning(f"Mypy检查失败: {e}")

        return issues

    def _get_flake8_suggestion(self, code: str) -> Optional[str]:
        """根据Flake8错误代码提供修复建议"""
        suggestions = {
            'E501': '缩短行长度到120字符以内，或使用括号换行',
            'E302': '在类或函数定义前添加两个空行',
            'E303': '删除多余的空行',
            'E231': '在逗号后添加空格',
            'E225': '在运算符周围添加空格',
            'E251': '在关键字参数赋值周围不要添加空格',
            'E401': '每个import语句单独一行',
            'E402': '将import语句移到文件顶部',
            'F401': '删除未使用的import',
            'F841': '删除未使用的变量或使用下划线前缀',
        }
        return suggestions.get(code)

    def _calculate_score(self, issues: List[QualityIssue], code: str) -> float:
        """
        计算代码质量分数（0-100）

        扣分规则：
        - 每个error扣10分
        - 每个warning扣3分
        - 每个info扣1分
        - 基础分100分
        """
        score = 100.0

        for issue in issues:
            if issue.severity == 'error':
                score -= 10
            elif issue.severity == 'warning':
                score -= 3
            elif issue.severity == 'info':
                score -= 1

        # 代码行数奖励（鼓励简洁）
        lines = len([l for l in code.split('\n') if l.strip()])
        if lines < 50:
            score += 5  # 简洁代码奖励

        return max(0.0, min(100.0, score))


def quick_quality_check(code: str) -> bool:
    """
    快速质量检查（只返回是否通过）

    Args:
        code: 代码字符串

    Returns:
        是否通过质量检查
    """
    analyzer = CodeQualityAnalyzer(enable_mypy=False)
    result = analyzer.analyze(code)

    if not result.get("success"):
        return False

    # 通过标准：无error，质量分数>=60
    return result.get("error_count", 1) == 0 and result.get("quality_score", 0) >= 60
