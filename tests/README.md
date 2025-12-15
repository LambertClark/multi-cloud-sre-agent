# 自动化测试框架文档

## 📋 目录结构

```
tests/
├── conftest.py                      # pytest 全局配置和 fixtures
├── test_data_adapter_agent.py       # DataAdapter 基础测试
├── test_data_adapter_parametrized.py # DataAdapter 参数化测试
├── test_azure_gcp_adapter.py        # Azure/GCP 适配测试
├── test_volc_adapter.py             # 火山云适配测试
└── README.md                        # 本文档
```

## 🚀 快速开始

### 安装依赖

```bash
# 安装开发依赖（包括测试工具）
uv sync --group dev
```

### 运行测试

```bash
# 方式1：使用自动化脚本（推荐）
python run_all_tests.py

# 方式2：直接使用 pytest
pytest

# 方式3：运行特定文件
pytest tests/test_data_adapter_parametrized.py
```

## 📊 测试模式

### 按标记运行

```bash
# 运行单元测试
python run_all_tests.py --mode unit

# 运行集成测试
python run_all_tests.py --mode integration

# 运行端到端测试
python run_all_tests.py --mode e2e

# 运行冒烟测试
python run_all_tests.py --mode smoke
```

### 按云平台运行

```bash
# 仅运行 AWS 测试
python run_all_tests.py --mode aws

# 仅运行 Azure 测试
python run_all_tests.py --mode azure

# 仅运行 GCP 测试
python run_all_tests.py --mode gcp

# 仅运行火山云测试
python run_all_tests.py --mode volc

# 仅运行 Kubernetes 测试
python run_all_tests.py --mode k8s
```

### 高级选项

```bash
# 快速测试（跳过慢速测试）
python run_all_tests.py --mode fast

# 3个失败后停止
python run_all_tests.py --maxfail 3

# 失败重试2次
python run_all_tests.py --retry 2

# 清理旧报告
python run_all_tests.py --clean

# 显示覆盖率摘要
python run_all_tests.py --coverage

# 自定义标记组合
python run_all_tests.py --markers "unit and aws"
```

## 🎯 测试类型说明

### 单元测试 (Unit Tests)

测试单个函数或方法的功能。

**示例：**
```python
@pytest.mark.unit
async def test_aws_ec2_conversion(aws_ec2_data):
    adapter = DataAdapterAgent()
    result = await adapter.safe_process({
        "raw_data": aws_ec2_data,
        "cloud_provider": "aws",
        "target_schema": "ComputeResource",
    })
    assert result.success
```

### 集成测试 (Integration Tests)

测试多个模块之间的交互。

**示例：**
```python
@pytest.mark.integration
async def test_manager_with_data_adapter():
    # 测试 ManagerAgent 和 DataAdapterAgent 的集成
    pass
```

### 端到端测试 (E2E Tests)

测试完整的业务流程。

**示例：**
```python
@pytest.mark.e2e
async def test_full_query_workflow():
    # 测试从查询到返回结果的完整流程
    pass
```

## 🧪 参数化测试

使用 `@pytest.mark.parametrize` 实现数据驱动测试：

```python
@pytest.mark.parametrize("cloud_provider,fixture_name", [
    ("aws", "aws_ec2_data"),
    ("azure", "azure_vm_data"),
    ("gcp", "gcp_instance_data"),
])
async def test_compute_resource_conversion(cloud_provider, fixture_name, request):
    raw_data = request.getfixturevalue(fixture_name)
    # 测试逻辑...
```

**优势：**
- 单个测试函数覆盖多个场景
- 减少代码重复
- 易于扩展新的测试用例

## 🛠️ Fixtures 使用

### 测试数据 Fixtures

在 `conftest.py` 中定义了多个测试数据 fixtures：

```python
# AWS 测试数据
def test_with_aws_data(aws_ec2_data, aws_cloudwatch_metric_data):
    # 使用 AWS 测试数据
    pass

# Azure 测试数据
def test_with_azure_data(azure_vm_data, azure_monitor_metric_data):
    # 使用 Azure 测试数据
    pass

# GCP 测试数据
def test_with_gcp_data(gcp_instance_data, gcp_metric_data):
    # 使用 GCP 测试数据
    pass

# 火山云测试数据
def test_with_volc_data(volc_ecs_data, volc_monitor_metric_data):
    # 使用火山云测试数据
    pass

# Kubernetes 测试数据
def test_with_k8s_data(k8s_pod_data):
    # 使用 K8s 测试数据
    pass
```

### Mock Fixtures

```python
def test_with_mock_llm(mock_llm_client):
    # 使用 Mock LLM 客户端
    pass

def test_with_mock_rag(mock_rag_system):
    # 使用 Mock RAG 系统
    pass
```

## 📈 测试报告

### HTML 测试报告

运行测试后会自动生成 HTML 报告：

```
reports/test_report.html
```

在浏览器中打开查看详细的测试结果。

### 覆盖率报告

```bash
# 查看覆盖率报告
open reports/coverage/index.html  # macOS
start reports/coverage/index.html # Windows
```

覆盖率报告包含：
- 每个文件的覆盖率百分比
- 未覆盖的代码行
- 分支覆盖情况

## 🔍 测试覆盖率目标

| 模块 | 目标覆盖率 | 当前覆盖率 |
|------|-----------|-----------|
| agents/ | 85%+ | 85%+ ✅ |
| tools/ | 80%+ | 80%+ ✅ |
| schemas/ | 90%+ | 90%+ ✅ |

## 📝 编写测试的最佳实践

### 1. 测试命名规范

```python
# ✅ 好的命名
def test_aws_ec2_conversion_with_valid_data():
    pass

def test_azure_vm_conversion_returns_error_when_data_invalid():
    pass

# ❌ 不好的命名
def test1():
    pass

def test_function():
    pass
```

### 2. 使用 Arrange-Act-Assert 模式

```python
async def test_example():
    # Arrange（准备）
    adapter = DataAdapterAgent()
    test_data = {"InstanceId": "i-123"}

    # Act（执行）
    result = await adapter.safe_process({
        "raw_data": test_data,
        "cloud_provider": "aws",
        "target_schema": "ComputeResource",
    })

    # Assert（断言）
    assert result.success
    assert result.data.resource_id == "i-123"
```

### 3. 测试边界条件

```python
@pytest.mark.parametrize("invalid_input", [
    None,
    {},
    {"invalid_key": "value"},
])
async def test_handles_invalid_input(invalid_input):
    # 测试异常输入的处理
    pass
```

### 4. 使用 Mock 隔离外部依赖

```python
async def test_with_mock(mock_llm_client):
    # 不依赖真实的 LLM API
    result = await some_function_using_llm(mock_llm_client)
    assert result is not None
```

## 🐛 调试失败的测试

### 查看详细错误信息

```bash
# 显示完整的 traceback
pytest -vv

# 进入调试模式
pytest --pdb

# 显示 print 输出
pytest -s
```

### 只运行失败的测试

```bash
# 重新运行上次失败的测试
pytest --lf

# 先运行失败的测试，再运行其他测试
pytest --ff
```

## 📊 CI/CD 集成

### GitHub Actions 示例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --group dev
      - name: Run tests
        run: python run_all_tests.py --mode fast
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./reports/coverage.xml
```

## 🎓 学习资源

- [Pytest 官方文档](https://docs.pytest.org/)
- [Pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [参数化测试最佳实践](https://docs.pytest.org/en/stable/how-to/parametrize.html)
- [Mock 使用指南](https://docs.python.org/3/library/unittest.mock.html)

## 💡 常见问题

### Q: 如何添加新的测试数据？

在 `conftest.py` 中添加新的 fixture：

```python
@pytest.fixture
def my_test_data():
    return {"key": "value"}
```

### Q: 如何跳过某个测试？

```python
@pytest.mark.skip(reason="暂时跳过")
def test_something():
    pass
```

### Q: 如何标记慢速测试？

```python
@pytest.mark.slow
async def test_slow_operation():
    # 慢速测试逻辑
    pass
```

然后跳过慢速测试：
```bash
pytest -m "not slow"
```
