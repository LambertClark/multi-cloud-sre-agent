"""
代码审查器
自动审查生成的代码，发现潜在问题并提供改进建议
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import ast
import re
import logging

logger = logging.getLogger(__name__)


class ReviewSeverity(Enum):
    """审查问题严重程度"""
    INFO = "info"  # 信息提示
    WARNING = "warning"  # 警告
    ERROR = "error"  # 错误
    CRITICAL = "critical"  # 严重错误


class ReviewCategory(Enum):
    """审查类别"""
    SECURITY = "security"  # 安全问题
    PERFORMANCE = "performance"  # 性能问题
    BEST_PRACTICE = "best_practice"  # 最佳实践
    CODE_STYLE = "code_style"  # 代码风格
    ERROR_HANDLING = "error_handling"  # 错误处理
    RESOURCE_MANAGEMENT = "resource_management"  # 资源管理


@dataclass
class ReviewIssue:
    """审查问题"""
    category: ReviewCategory
    severity: ReviewSeverity
    line: int
    message: str
    suggestion: str
    code_snippet: Optional[str] = None


@dataclass
class ReviewResult:
    """审查结果"""
    passed: bool
    score: float  # 0-100分
    issues: List[ReviewIssue]
    summary: Dict[str, int]  # 各类问题统计
    recommendations: List[str]  # 总体建议


class CodeReviewer:
    """
    代码审查器

    检查内容：
    1. 安全问题：SQL注入、命令注入、敏感信息泄露
    2. 性能问题：低效算法、不必要的循环、资源泄漏
    3. 最佳实践：异常处理、资源清理、分页处理
    4. 代码风格：命名规范、文档字符串、复杂度
    """

    def __init__(self):
        self.issues: List[ReviewIssue] = []

    def review(self, code: str) -> ReviewResult:
        """
        审查代码

        Args:
            code: 要审查的代码

        Returns:
            审查结果
        """
        self.issues = []

        # 1. 安全审查
        self._review_security(code)

        # 2. 性能审查
        self._review_performance(code)

        # 3. 最佳实践审查
        self._review_best_practices(code)

        # 4. 错误处理审查
        self._review_error_handling(code)

        # 5. 资源管理审查
        self._review_resource_management(code)

        # 6. 代码风格审查
        self._review_code_style(code)

        # 生成审查结果
        return self._generate_result()

    def _review_security(self, code: str):
        """安全审查"""
        lines = code.split('\n')

        # 检查SQL注入风险
        sql_pattern = re.compile(r'(execute|cursor\.execute|sql)\s*\([^)]*\+[^)]*\)', re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if sql_pattern.search(line):
                self.issues.append(ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    line=i,
                    message="可能存在SQL注入风险",
                    suggestion="使用参数化查询而不是字符串拼接",
                    code_snippet=line.strip()
                ))

        # 检查命令注入风险
        cmd_pattern = re.compile(r'(os\.system|subprocess\.call|subprocess\.run).*shell\s*=\s*True', re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if cmd_pattern.search(line):
                self.issues.append(ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    line=i,
                    message="使用shell=True存在命令注入风险",
                    suggestion="避免使用shell=True，或严格验证输入",
                    code_snippet=line.strip()
                ))

        # 检查硬编码密钥
        secret_pattern = re.compile(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if secret_pattern.search(line) and 'os.environ' not in line and 'getenv' not in line:
                self.issues.append(ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=ReviewSeverity.ERROR,
                    line=i,
                    message="检测到硬编码的密钥或密码",
                    suggestion="使用环境变量或密钥管理服务",
                    code_snippet=line.strip()
                ))

        # 检查eval/exec使用
        if 'eval(' in code or 'exec(' in code:
            for i, line in enumerate(lines, 1):
                if 'eval(' in line or 'exec(' in line:
                    self.issues.append(ReviewIssue(
                        category=ReviewCategory.SECURITY,
                        severity=ReviewSeverity.CRITICAL,
                        line=i,
                        message="使用eval/exec存在代码注入风险",
                        suggestion="避免使用eval/exec，寻找替代方案",
                        code_snippet=line.strip()
                    ))

    def _review_performance(self, code: str):
        """性能审查"""
        try:
            tree = ast.parse(code)
            lines = code.split('\n')

            # 检查嵌套循环
            for node in ast.walk(tree):
                if isinstance(node, ast.For):
                    # 检查是否有嵌套循环
                    nested_loops = [n for n in ast.walk(node) if isinstance(n, ast.For) and n != node]
                    if len(nested_loops) >= 2:
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.PERFORMANCE,
                            severity=ReviewSeverity.WARNING,
                            line=node.lineno,
                            message="检测到多层嵌套循环，可能影响性能",
                            suggestion="考虑优化算法复杂度或使用哈希表",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))

            # 检查列表append在循环中
            for node in ast.walk(tree):
                if isinstance(node, ast.For):
                    appends = [n for n in ast.walk(node) if isinstance(n, ast.Call) and
                              isinstance(n.func, ast.Attribute) and n.func.attr == 'append']
                    if appends:
                        # 检查是否可以用列表推导式
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.PERFORMANCE,
                            severity=ReviewSeverity.INFO,
                            line=node.lineno,
                            message="循环中使用append，考虑使用列表推导式",
                            suggestion="列表推导式通常比append更快",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))

            # 检查全局变量
            for node in ast.walk(tree):
                if isinstance(node, ast.Global):
                    self.issues.append(ReviewIssue(
                        category=ReviewCategory.PERFORMANCE,
                        severity=ReviewSeverity.WARNING,
                        line=node.lineno,
                        message="使用全局变量可能影响性能和可维护性",
                        suggestion="考虑使用函数参数或类属性",
                        code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                    ))

        except SyntaxError:
            logger.warning("代码解析失败，跳过AST性能检查")

    def _review_best_practices(self, code: str):
        """最佳实践审查"""
        lines = code.split('\n')

        # 检查是否处理分页
        if 'boto3' in code and 'describe_instances' in code:
            if 'paginator' not in code.lower() and 'nexttoken' not in code.lower():
                self.issues.append(ReviewIssue(
                    category=ReviewCategory.BEST_PRACTICE,
                    severity=ReviewSeverity.WARNING,
                    line=0,
                    message="AWS API调用未使用分页器，可能遗漏数据",
                    suggestion="使用get_paginator()处理大量数据"
                ))

        # 检查是否有重试机制
        if ('boto3' in code or 'requests' in code) and 'ClientError' in code:
            if 'retry' not in code.lower() and 'for attempt in' not in code:
                self.issues.append(ReviewIssue(
                    category=ReviewCategory.BEST_PRACTICE,
                    severity=ReviewSeverity.INFO,
                    line=0,
                    message="API调用未实现重试机制",
                    suggestion="添加指数退避重试处理临时错误"
                ))

        # 检查是否有日志记录
        if 'logger' not in code and 'logging' not in code and 'print' in code:
            self.issues.append(ReviewIssue(
                category=ReviewCategory.BEST_PRACTICE,
                severity=ReviewSeverity.INFO,
                line=0,
                message="使用print而不是logging",
                suggestion="使用logging模块便于生产环境调试"
            ))

        # 检查函数文档字符串
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not ast.get_docstring(node):
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.BEST_PRACTICE,
                            severity=ReviewSeverity.INFO,
                            line=node.lineno,
                            message=f"函数{node.name}缺少文档字符串",
                            suggestion="添加文档字符串说明函数用途和参数",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))
        except SyntaxError:
            pass

    def _review_error_handling(self, code: str):
        """错误处理审查"""
        lines = code.split('\n')

        try:
            tree = ast.parse(code)

            # 检查空except
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.ERROR_HANDLING,
                            severity=ReviewSeverity.WARNING,
                            line=node.lineno,
                            message="使用空except捕获所有异常",
                            suggestion="明确指定要捕获的异常类型",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))

                    # 检查except块是否为空
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.ERROR_HANDLING,
                            severity=ReviewSeverity.WARNING,
                            line=node.lineno,
                            message="except块为空（只有pass）",
                            suggestion="至少记录异常日志",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))

            # 检查是否有finally清理资源
            has_try_with_resources = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    # 检查是否打开文件或连接
                    has_open = any('open(' in ast.unparse(n) if hasattr(ast, 'unparse') else False
                                   for n in ast.walk(node.body[0]) if isinstance(n, ast.Call))

                    if has_open and not node.finalbody:
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.ERROR_HANDLING,
                            severity=ReviewSeverity.WARNING,
                            line=node.lineno,
                            message="打开资源但没有finally块确保关闭",
                            suggestion="使用with语句或添加finally块",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))

        except SyntaxError:
            logger.warning("代码解析失败，跳过错误处理检查")

    def _review_resource_management(self, code: str):
        """资源管理审查"""
        lines = code.split('\n')

        # 检查文件操作是否使用with语句
        file_open_pattern = re.compile(r'^\s*(\w+)\s*=\s*open\(')
        for i, line in enumerate(lines, 1):
            if file_open_pattern.search(line) and 'with' not in lines[max(0, i-2):i]:
                self.issues.append(ReviewIssue(
                    category=ReviewCategory.RESOURCE_MANAGEMENT,
                    severity=ReviewSeverity.WARNING,
                    line=i,
                    message="未使用with语句打开文件",
                    suggestion="使用'with open() as f:'确保文件正确关闭",
                    code_snippet=line.strip()
                ))

        # 检查数据库连接是否关闭
        if 'connect(' in code and '.close()' not in code and 'with' not in code:
            self.issues.append(ReviewIssue(
                category=ReviewCategory.RESOURCE_MANAGEMENT,
                severity=ReviewSeverity.WARNING,
                line=0,
                message="数据库连接可能未正确关闭",
                suggestion="使用with语句或在finally中close()"
            ))

        # 检查AWS资源是否清理
        if 'run_instances' in code and 'terminate_instances' not in code:
            self.issues.append(ReviewIssue(
                category=ReviewCategory.RESOURCE_MANAGEMENT,
                severity=ReviewSeverity.INFO,
                line=0,
                message="创建EC2实例但未见清理代码",
                suggestion="确保在测试后清理临时资源"
            ))

    def _review_code_style(self, code: str):
        """代码风格审查"""
        lines = code.split('\n')

        try:
            tree = ast.parse(code)

            # 检查函数复杂度（行数）
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 计算函数行数
                    func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    if func_lines > 50:
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.CODE_STYLE,
                            severity=ReviewSeverity.INFO,
                            line=node.lineno,
                            message=f"函数{node.name}过长（{func_lines}行）",
                            suggestion="考虑拆分为更小的函数",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))

                    # 检查参数数量
                    param_count = len(node.args.args)
                    if param_count > 5:
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.CODE_STYLE,
                            severity=ReviewSeverity.INFO,
                            line=node.lineno,
                            message=f"函数{node.name}参数过多（{param_count}个）",
                            suggestion="考虑使用配置对象或减少参数",
                            code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else None
                        ))

            # 检查变量命名（单字母变量）
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    if len(node.id) == 1 and node.id not in ['i', 'j', 'k', 'x', 'y', 'z']:
                        self.issues.append(ReviewIssue(
                            category=ReviewCategory.CODE_STYLE,
                            severity=ReviewSeverity.INFO,
                            line=node.lineno if hasattr(node, 'lineno') else 0,
                            message=f"单字母变量名'{node.id}'可读性差",
                            suggestion="使用描述性的变量名"
                        ))

        except SyntaxError:
            logger.warning("代码解析失败，跳过代码风格检查")

        # 检查行长度
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                self.issues.append(ReviewIssue(
                    category=ReviewCategory.CODE_STYLE,
                    severity=ReviewSeverity.INFO,
                    line=i,
                    message=f"行过长（{len(line)}字符）",
                    suggestion="限制在120字符以内，使用括号换行"
                ))

    def _generate_result(self) -> ReviewResult:
        """生成审查结果"""
        # 统计各类问题
        summary = {
            'critical': sum(1 for i in self.issues if i.severity == ReviewSeverity.CRITICAL),
            'error': sum(1 for i in self.issues if i.severity == ReviewSeverity.ERROR),
            'warning': sum(1 for i in self.issues if i.severity == ReviewSeverity.WARNING),
            'info': sum(1 for i in self.issues if i.severity == ReviewSeverity.INFO)
        }

        # 计算分数（100分制）
        score = 100.0
        score -= summary['critical'] * 25  # 严重问题扣25分
        score -= summary['error'] * 10  # 错误扣10分
        score -= summary['warning'] * 5  # 警告扣5分
        score -= summary['info'] * 1  # 信息扣1分
        score = max(0.0, score)

        # 判断是否通过
        passed = summary['critical'] == 0 and summary['error'] == 0 and score >= 60

        # 生成总体建议
        recommendations = self._generate_recommendations(summary)

        return ReviewResult(
            passed=passed,
            score=score,
            issues=self.issues,
            summary=summary,
            recommendations=recommendations
        )

    def _generate_recommendations(self, summary: Dict[str, int]) -> List[str]:
        """生成总体建议"""
        recommendations = []

        if summary['critical'] > 0:
            recommendations.append("⚠️  发现严重安全问题，必须立即修复")

        if summary['error'] > 0:
            recommendations.append("❌ 发现错误级别问题，建议修复后再使用")

        if summary['warning'] > 5:
            recommendations.append("⚡ 警告问题较多，建议优化代码质量")

        # 按类别统计
        category_counts = {}
        for issue in self.issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        # 找出最多的问题类别
        if category_counts:
            max_category = max(category_counts.items(), key=lambda x: x[1])
            if max_category[1] >= 3:
                category_name = {
                    ReviewCategory.SECURITY: "安全性",
                    ReviewCategory.PERFORMANCE: "性能",
                    ReviewCategory.BEST_PRACTICE: "最佳实践",
                    ReviewCategory.ERROR_HANDLING: "错误处理",
                    ReviewCategory.RESOURCE_MANAGEMENT: "资源管理",
                    ReviewCategory.CODE_STYLE: "代码风格"
                }
                recommendations.append(
                    f"📊 {category_name.get(max_category[0], '其他')}问题最多，建议重点关注"
                )

        if not recommendations:
            recommendations.append("✅ 代码质量良好，未发现重大问题")

        return recommendations


def review_code(code: str) -> ReviewResult:
    """
    审查代码的便捷函数

    Args:
        code: 要审查的代码

    Returns:
        审查结果
    """
    reviewer = CodeReviewer()
    return reviewer.review(code)
