"""
Prompt Injection防御系统
实现多层安全防护，防止恶意prompt注入攻击
"""
import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """安全错误异常"""
    pass


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    reason: Optional[str] = None
    sanitized_input: Optional[Dict[str, Any]] = None


class PromptInjectionDefense:
    """
    Prompt Injection防御系统

    实现三层防御：
    1. 黑名单检测（快速拦截明显的恶意指令）
    2. 输入长度限制（防止超长输入）
    3. 结构化提取（强制参数化，隔离自由文本）
    """

    # 黑名单模式：检测恶意指令
    BLACKLIST_PATTERNS = [
        # === 指令覆盖攻击 ===
        r"忽略.*(?:指令|规则|约束)",
        r"ignore.*(?:instruct|rule|constraint|previous|above)",
        r"forget.*(?:above|previous|instruction)",
        r"disregard.*(?:previous|above|instruction)",
        r"nevermind.*(?:previous|above)",

        # === 角色劫持攻击 ===
        r"你现在(?:是|扮演|充当)",
        r"you\s+are\s+now",
        r"assume.*role",
        r"pretend.*to\s+be",
        r"act\s+as\s+(?:if|a)",

        # === 危险操作关键词 ===
        r"(?:delete|remove|terminate|drop|destroy).*(?:all|everything|\*)",
        r"(?:删除|移除|终止|销毁).*(?:所有|全部)",
        r"rm\s+-rf",
        r"drop\s+table",
        r"truncate\s+table",

        # === 代码注入攻击 ===
        r"import\s+os(?:\s|;|$)",
        r"import\s+subprocess",
        r"__import__\s*\(",
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"open\s*\(['\"].*['\"],\s*['\"]w",  # 写文件

        # === 系统命令执行 ===
        r"os\.system\s*\(",
        r"subprocess\.",
        r"shell\s*=\s*True",
        r"Popen\s*\(",

        # === 网络请求（可能泄漏数据）===
        r"requests?\.(get|post)",
        r"urllib\.request",
        r"curl\s+http",
        r"wget\s+http",

        # === 环境变量访问（可能泄漏密钥）===
        r"os\.environ",
        r"getenv\s*\(",
        r"process\.env",

        # === 绕过尝试 ===
        r"base64\.decode",
        r"chr\s*\(",  # 字符编码绕过
        r"\.decode\s*\(['\"]",
    ]

    # 危险操作白名单（允许的只读操作）
    ALLOWED_ACTIONS = {
        "list", "列出", "显示", "查看", "show", "display",
        "query", "查询", "统计", "分析", "analyze", "stats",
        "describe", "描述", "详情", "信息", "info", "get",
        "search", "搜索", "查找", "find",
        "monitor", "监控", "观察", "watch",
    }

    # 危险操作黑名单（禁止的写操作）
    # 注意：这些词必须是完整单词，不能是子串
    DANGEROUS_ACTIONS_PATTERNS = [
        r"\bdelete\b", r"\b删除\b",
        r"\bremove\b", r"\b移除\b",
        r"\bterminate\b", r"\b终止\b",
        r"\bstop\b", r"\b停止\b",
        r"\bcreate\b", r"\b创建\b",
        r"\badd\b", r"\b添加\b",
        r"\bupdate\b", r"\b更新\b",
        r"\bmodify\b", r"\b修改\b",
        r"\bdrop\b", r"\b销毁\b",
        r"\bdestroy\b",
        r"\bexecute\b", r"\b执行\b",
        # "run"太容易误杀（running），暂不包含
    ]

    def __init__(self, max_input_length: int = 1000):
        """
        初始化防御系统

        Args:
            max_input_length: 最大输入长度（字符数）
        """
        self.max_input_length = max_input_length
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.BLACKLIST_PATTERNS]
        self.compiled_dangerous_actions = [re.compile(pattern, re.IGNORECASE) for pattern in self.DANGEROUS_ACTIONS_PATTERNS]

    def validate_and_sanitize(self, user_query: str) -> ValidationResult:
        """
        验证并清洗用户输入

        Args:
            user_query: 用户原始查询

        Returns:
            ValidationResult包含验证结果和清洗后的数据

        Raises:
            SecurityError: 检测到恶意输入时抛出
        """
        logger.info(f"开始安全检查，输入长度: {len(user_query)}")

        # 检查1：长度限制
        if len(user_query) > self.max_input_length:
            return ValidationResult(
                passed=False,
                reason=f"输入过长（{len(user_query)}字符，最大{self.max_input_length}字符）"
            )

        # 检查2：黑名单匹配
        for pattern in self.compiled_patterns:
            match = pattern.search(user_query)
            if match:
                matched_text = match.group(0)
                logger.warning(f"检测到疑似注入攻击: {matched_text}")
                return ValidationResult(
                    passed=False,
                    reason=f"检测到可疑模式: {matched_text[:50]}..."
                )

        # 检查3：危险操作检测（使用完整单词匹配）
        for pattern in self.compiled_dangerous_actions:
            match = pattern.search(user_query)
            if match:
                matched_word = match.group(0)
                # 检查是否有安全的上下文（例如"不要删除"）
                if not self._is_safe_context(user_query, matched_word):
                    logger.warning(f"检测到危险操作: {matched_word}")
                    return ValidationResult(
                        passed=False,
                        reason=f"包含危险操作关键词: {matched_word}"
                    )

        # 检查4：结构化提取
        try:
            structured_input = self._extract_structured_query(user_query)
            logger.info(f"结构化提取成功: {structured_input}")

            return ValidationResult(
                passed=True,
                sanitized_input=structured_input
            )
        except Exception as e:
            logger.error(f"结构化提取失败: {str(e)}")
            return ValidationResult(
                passed=False,
                reason=f"无法解析查询: {str(e)}"
            )

    def _is_safe_context(self, text: str, dangerous_word: str) -> bool:
        """
        检查危险词是否在安全上下文中

        例如："不要删除"、"如何防止删除" 是安全的
        """
        # 查找危险词前后的文本
        index = text.lower().find(dangerous_word)
        if index == -1:
            return True

        # 检查前面是否有否定词
        before = text[max(0, index-20):index].lower()
        negation_words = ["不要", "不能", "禁止", "防止", "避免", "don't", "do not", "prevent", "avoid", "how to prevent"]

        for neg_word in negation_words:
            if neg_word in before:
                return True  # 在否定上下文中，是安全的

        return False

    def _extract_structured_query(self, text: str) -> Dict[str, Any]:
        """
        强制结构化提取：只提取关键参数，丢弃自由文本

        这是最安全的方式：完全忽略用户的自由文本，只提取参数化的字段
        """
        structured = {
            "action": self._extract_action(text),
            "resource": self._extract_resource(text),
            "cloud_provider": self._extract_cloud_provider(text),
            "filters": self._extract_filters(text),
            "time_range": self._extract_time_range(text),
            "original_query": text[:200],  # 保留原始查询的前200字符供日志使用
        }

        # 验证action的安全性
        if structured["action"] not in self.ALLOWED_ACTIONS:
            raise SecurityError(f"不允许的操作: {structured['action']}")

        return structured

    def _extract_action(self, text: str) -> str:
        """提取操作类型（白名单）"""
        text_lower = text.lower()

        # 优先匹配只读操作
        for action in self.ALLOWED_ACTIONS:
            if action in text_lower:
                # 确认这是主要动词（不是在句子中间）
                # 检查是否在句首或者在空格/标点后面
                if text_lower.startswith(action) or f" {action}" in text_lower or f"\n{action}" in text_lower:
                    return action

        # 默认为最安全的操作：list（假设用户想查看数据）
        return "list"

    def _extract_resource(self, text: str) -> str:
        """提取资源类型"""
        text_lower = text.lower()

        resource_keywords = {
            "ec2": ["ec2", "实例", "instance", "虚拟机", "vm"],
            "rds": ["rds", "数据库", "database", "db"],
            "s3": ["s3", "存储", "bucket", "对象存储"],
            "lambda": ["lambda", "函数", "function", "serverless"],
            "cloudwatch": ["cloudwatch", "监控", "metrics", "指标"],
            "logs": ["logs", "日志", "logging"],
            "vpc": ["vpc", "网络", "network", "subnet"],
            "cdn": ["cdn", "cloudfront", "分发", "缓存"],
        }

        for resource, keywords in resource_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return resource

        return "unknown"

    def _extract_cloud_provider(self, text: str) -> str:
        """提取云平台"""
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["aws", "亚马逊", "amazon"]):
            return "aws"
        elif any(kw in text_lower for kw in ["azure", "微软", "microsoft"]):
            return "azure"
        elif any(kw in text_lower for kw in ["gcp", "google", "谷歌"]):
            return "gcp"
        elif any(kw in text_lower for kw in ["aliyun", "阿里", "ali", "阿里云"]):
            return "aliyun"
        elif any(kw in text_lower for kw in ["volcengine", "火山", "字节"]):
            return "volcengine"

        return "aws"  # 默认AWS

    def _extract_filters(self, text: str) -> Dict[str, Any]:
        """提取过滤条件"""
        filters = {}
        text_lower = text.lower()

        # 提取状态
        if "running" in text_lower or "运行" in text_lower:
            filters["status"] = "running"
        elif "stopped" in text_lower or "停止" in text_lower:
            filters["status"] = "stopped"

        # 提取阈值（例如：CPU>80%）
        cpu_match = re.search(r"cpu.*?(\d+)%?", text_lower)
        if cpu_match:
            filters["cpu_threshold"] = int(cpu_match.group(1))

        memory_match = re.search(r"(?:memory|内存).*?(\d+)%?", text_lower)
        if memory_match:
            filters["memory_threshold"] = int(memory_match.group(1))

        return filters

    def _extract_time_range(self, text: str) -> Dict[str, Any]:
        """提取时间范围"""
        time_range = {}
        text_lower = text.lower()

        # 简单的时间范围提取
        if "last hour" in text_lower or "最近1小时" in text_lower or "过去1小时" in text_lower:
            time_range["duration"] = "1h"
        elif "last 24 hours" in text_lower or "最近24小时" in text_lower or "过去一天" in text_lower:
            time_range["duration"] = "24h"
        elif "last 7 days" in text_lower or "最近7天" in text_lower or "过去一周" in text_lower:
            time_range["duration"] = "7d"
        else:
            time_range["duration"] = "1h"  # 默认1小时

        return time_range
