"""
自动化测试运行脚本
支持多种测试模式、标记过滤、失败重试、报告生成
"""
import subprocess
import sys
import os
import argparse
import io
from datetime import datetime
from pathlib import Path

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.reports_dir = Path("reports")
        self.ensure_reports_dir()

    def ensure_reports_dir(self):
        """确保报告目录存在"""
        self.reports_dir.mkdir(exist_ok=True)
        print(f"📁 报告目录: {self.reports_dir.absolute()}")

    def run_tests(self, mode="all", markers=None, verbose=True, maxfail=None, retry=0):
        """
        运行测试

        Args:
            mode: 测试模式 (all/unit/integration/e2e/smoke/快速云平台标记)
            markers: 自定义标记过滤
            verbose: 详细输出
            maxfail: 最大失败数
            retry: 失败重试次数
        """
        print("=" * 70)
        print("🧪 多云SRE Agent 自动化测试框架")
        print("=" * 70)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 测试模式: {mode}")

        # 构建pytest命令
        cmd = [sys.executable, "-m", "pytest", "tests/"]

        # 添加详细输出
        if verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        # 添加标记过滤
        if mode != "all":
            if mode in ["unit", "integration", "e2e", "smoke", "regression"]:
                cmd.extend(["-m", mode])
                print(f"🏷️  测试标记: {mode}")
            elif mode in ["aws", "azure", "gcp", "volc", "k8s"]:
                cmd.extend(["-m", mode])
                print(f"☁️  云平台: {mode.upper()}")
            elif mode == "fast":
                # 快速测试：只运行单元测试，跳过慢速测试
                cmd.extend(["-m", "unit and not slow"])
                print("🏷️  测试标记: unit (跳过慢速测试)")
            elif mode == "slow":
                # 慢速测试
                cmd.extend(["-m", "slow"])
                print("🏷️  测试标记: slow")

        # 自定义标记
        if markers:
            cmd.extend(["-m", markers])
            print(f"🏷️  自定义标记: {markers}")

        # 失败时最多失败数
        if maxfail:
            cmd.extend(["--maxfail", str(maxfail)])
            print(f"⚠️  最多失败: {maxfail} 个")

        # 失败重试
        if retry > 0:
            # 注意：需要安装 pytest-rerunfailures 插件
            cmd.extend(["--reruns", str(retry)])
            print(f"🔄 失败重试: {retry} 次")

        # 显示最慢的10个测试
        cmd.append("--durations=10")

        print(f"\n🚀 执行命令: {' '.join(cmd)}\n")
        print("-" * 70)

        # 运行测试
        start_time = datetime.now()
        result = subprocess.run(cmd, capture_output=False)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("-" * 70)
        print(f"\n⏰ 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  总耗时: {duration:.2f} 秒")

        # 结果分析
        if result.returncode == 0:
            print("\n✅ 所有测试通过!")
            print(f"📊 查看报告:")
            print(f"   - HTML测试报告: {self.reports_dir / 'test_report.html'}")
            print(f"   - 覆盖率报告: {self.reports_dir / 'coverage' / 'index.html'}")
        else:
            print(f"\n❌ 测试失败 (退出码: {result.returncode})")
            print(f"📊 查看失败详情:")
            print(f"   - HTML测试报告: {self.reports_dir / 'test_report.html'}")

        return result.returncode

    def show_coverage_summary(self):
        """显示覆盖率摘要"""
        print("\n" + "=" * 70)
        print("📈 测试覆盖率摘要")
        print("=" * 70)

        # 运行覆盖率报告（仅显示）
        subprocess.run([
            sys.executable, "-m", "coverage", "report",
            "--include=agents/*,tools/*,schemas/*"
        ])

    def clean_reports(self):
        """清理旧的测试报告"""
        import shutil

        if self.reports_dir.exists():
            print(f"🧹 清理旧报告: {self.reports_dir}")
            shutil.rmtree(self.reports_dir)
            self.reports_dir.mkdir()
            print("✅ 清理完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="多云SRE Agent 自动化测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
测试模式说明:
  all          - 运行所有测试 (默认)
  unit         - 仅运行单元测试
  integration  - 仅运行集成测试
  e2e          - 仅运行端到端测试
  smoke        - 仅运行冒烟测试
  fast         - 快速测试 (单元测试，跳过慢速)
  slow         - 仅运行慢速测试
  aws          - 仅运行 AWS 相关测试
  azure        - 仅运行 Azure 相关测试
  gcp          - 仅运行 GCP 相关测试
  volc         - 仅运行火山云相关测试
  k8s          - 仅运行 Kubernetes 相关测试

使用示例:
  python run_all_tests.py                    # 运行所有测试
  python run_all_tests.py --mode unit        # 仅运行单元测试
  python run_all_tests.py --mode aws         # 仅运行 AWS 测试
  python run_all_tests.py --mode fast        # 快速测试
  python run_all_tests.py --maxfail 3        # 3个失败后停止
  python run_all_tests.py --retry 2          # 失败重试2次
  python run_all_tests.py --clean            # 清理旧报告
        """
    )

    parser.add_argument(
        "-m", "--mode",
        choices=["all", "unit", "integration", "e2e", "smoke", "regression",
                 "fast", "slow", "aws", "azure", "gcp", "volc", "k8s"],
        default="all",
        help="测试模式"
    )

    parser.add_argument(
        "--markers",
        help="自定义pytest标记过滤 (例如: 'unit and aws')"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="简洁输出模式"
    )

    parser.add_argument(
        "--maxfail",
        type=int,
        help="最大失败数后停止"
    )

    parser.add_argument(
        "--retry",
        type=int,
        default=0,
        help="失败重试次数"
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理旧的测试报告"
    )

    parser.add_argument(
        "--coverage",
        action="store_true",
        help="显示覆盖率摘要"
    )

    args = parser.parse_args()

    # 创建测试运行器
    runner = TestRunner()

    # 清理旧报告
    if args.clean:
        runner.clean_reports()
        if not any([args.mode != "all", args.markers]):
            return 0

    # 运行测试
    exit_code = runner.run_tests(
        mode=args.mode,
        markers=args.markers,
        verbose=not args.quiet,
        maxfail=args.maxfail,
        retry=args.retry
    )

    # 显示覆盖率摘要
    if args.coverage and exit_code == 0:
        runner.show_coverage_summary()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
