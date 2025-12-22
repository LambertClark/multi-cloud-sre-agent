# 多云SRE Agent系统

**核心理念：Agent驱动的智能SRE系统，通过Agent自主生成代码，而非硬编码具体功能**

基于LangChain的智能多云SRE管理系统，通过Agent协作实现从API文档提取、代码生成到安全执行的全流程自动化。

## 🌟 核心特性

### 1. Agent驱动的代码生成
- **SpecDocAgent**: SDK内省 + OpenAPI解析，动态提取2032+个API操作
- **CodeGeneratorAgent**: ReAct模式自主生成→测试→修正，支持Python/JS/TS/Go
- **DataAdapterAgent**: 混合架构（规则引擎 + LLM）实现多云数据统一
- **ManagerAgent**: 任务分解和Agent协调（开发中）

### 2. 增强RAG检索系统
- **混合检索**: 向量检索 + BM25关键词检索，RRF融合
- **Reranker重排序**: Cross-Encoder提升Top-K准确率
- **Query改写**: LLM生成查询变体提升召回率
- **智能缓存**: 24小时过期，DocumentCache双层缓存

### 3. 代码质量保障
- **静态分析**: flake8 + pylint + mypy集成
- **代码审查**: 安全漏洞、性能问题、最佳实践检查
- **测试生成**: 自动生成单元测试，覆盖率>80%
- **模板库**: 15+个常见模式（分页、重试、批量处理）

### 4. 安全沙箱系统
- **代码扫描**: AST静态分析，检测危险函数和资源删除
- **沙箱执行**: 隔离环境，资源限制，异常捕获
- **权限管理**: 最小权限原则，70个只读API操作白名单

### 5. 工具动态注册
- **自动注册**: 生成的代码自动注册为可复用工具
- **质量评分**: 成功率70% + 使用频率20% + 执行速度10%
- **版本管理**: 自动版本升级，代码变化检测

### 6. 对话管理系统
- **会话管理**: 多轮对话，24小时自动过期
- **上下文压缩**: LLM总结历史，保持在token限制内
- **任务续传**: 失败任务恢复执行，断点续传

### 7. 统一Schema体系
```python
# 健康检查Schema
HealthSchema: MetricHealth, LogHealth, TraceHealth, ResourceHealth

# 资源Schema
ResourceSchema: ComputeResource, ContainerResource, NetworkResource, CDNResource

# 指标Schema
MetricSchema: MetricResult, MetricDataPoint
```

## 🚀 快速开始

### 安装
```bash
# 克隆项目
git clone https://github.com/LambertClark/multi-cloud-sre-agent.git
cd multi-cloud-sre-agent

# 安装依赖（使用uv）
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM API 密钥和云平台凭证
```

### 配置说明
在 `.env` 文件中配置：
```bash
# LLM配置（硅基流动API）
LLM_MODEL=moonshotai/Kimi-K2-Instruct-0905
LLM_API_KEY=your_siliconflow_api_key
LLM_BASE_URL=https://api.siliconflow.cn/v1

# AWS凭证（可选）
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Azure凭证（可选）
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
AZURE_SUBSCRIPTION_ID=your_subscription_id

# GCP凭证（可选）
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

### 运行
```bash
# 交互模式
python main.py --mode interactive

# 单次查询
python main.py -m query -q "列出AWS EC2实例"

# 健康检查模式
python main.py --mode health
```

## 📖 核心组件详解

### 1. SpecDocAgent - SDK内省和动态文档提取

**从SDK自动提取API定义，无需手动维护文档**

```python
from agents.spec_doc_agent import SpecDocAgent

agent = SpecDocAgent()

# 提取AWS CloudWatch API
result = await agent.process({
    "action": "extract_spec",
    "cloud_provider": "aws",
    "service": "cloudwatch"
})

# 返回：39个CloudWatch操作的完整定义
# get_metric_statistics, put_metric_data, describe_alarms...
```

**支持的云平台**:
- ✅ **AWS**: boto3 SDK内省（898个操作）
  - CloudWatch 39个、S3 110个、EC2 749个
- ✅ **Azure**: Azure SDK内省（79个操作）
  - Monitor 79个操作（客户端→操作组→方法三层架构）
- ✅ **Kubernetes**: OpenAPI规格解析（1055个操作）
  - 直接解析swagger.json标准规格
- 🔨 **GCP**: 支持但需安装google-cloud包

**DocumentCache智能缓存**:
```python
from services.doc_cache import DocumentCache

cache = DocumentCache()

# 获取或拉取文档（24小时缓存）
spec = await cache.get_or_fetch(
    cloud_provider="aws",
    service="s3",
    operation="list_buckets"
)

# 第一次：从SDK内省提取，存入RAG
# 第二次（24小时内）：直接从内存缓存返回
# 过期后：自动重新提取最新文档
```

### 2. CodeGeneratorAgent - ReAct模式代码生成

**自主生成代码→测试→观察→修正（最多3次迭代）**

```python
from agents.code_generator_agent import CodeGeneratorAgent

agent = CodeGeneratorAgent()

# ReAct模式生成代码
result = await agent.process_with_react({
    "requirement": "列出所有运行中的EC2实例",
    "operation": "describe_instances",
    "cloud_provider": "aws",
    "service": "ec2",
    "language": "python",
    "enable_auto_test": True
})

if result.success:
    print(f"生成代码:\n{result.data['code']}")
    print(f"测试代码:\n{result.data['test_code']}")
    print(f"ReAct迭代次数: {result.data['iterations']}")
    print(f"质量分数: {result.metadata['quality_score']}")
    print(f"审查分数: {result.metadata['review_score']}")
```

**代码质量增强**:
1. **CodeQualityAnalyzer**: flake8 + pylint + mypy静态分析
2. **CodeReviewer**: 安全、性能、最佳实践审查
3. **TestGenerator**: 自动生成单元测试（基础+边缘+异常+Mock）
4. **CodeTemplateLibrary**: 15+个最佳实践模板

**工作流程**:
```
1. Thought: 分析需求，规划实现
2. Action: 生成代码和测试
   ├── 从RAG检索相关文档
   ├── 从模板库查找最佳实践
   └── 生成完整代码（含错误处理）
3. Observation: 执行测试
   ├── 代码质量分析（flake8/pylint）
   ├── 安全审查（SQL注入、命令注入等）
   └── 单元测试执行（pytest）
4. 如果失败：修正代码→重新测试（最多3次）
5. 如果成功：返回代码 + 质量报告
```

### 3. EnhancedRAG - 混合检索系统

**向量检索 + BM25关键词检索，RRF融合**

```python
from services.enhanced_rag import HybridRetriever, Reranker

# 混合检索
retriever = HybridRetriever(
    vector_weight=0.6,  # 向量检索权重
    bm25_weight=0.4,    # BM25权重
    k=60                # RRF参数
)

results = await retriever.hybrid_retrieve(
    query="AWS S3 bucket list",
    top_k=10
)

# Reranker重排序
reranker = Reranker()
reranked = await reranker.rerank(
    query="list S3 buckets",
    documents=results,
    top_k=5
)

# 结果：精准匹配"list_buckets" API文档
```

**Query改写提升召回**:
```python
from services.enhanced_rag import QueryRewriter

rewriter = QueryRewriter()

# 输入："我想创建云服务器"
variants = await rewriter.rewrite_query(
    "我想创建云服务器",
    num_variants=3
)

# 输出：
# 1. "创建虚拟机实例"
# 2. "EC2 RunInstances API"
# 3. "启动计算实例操作"
```

**检索评估指标**:
- **P@K**: Precision at K（检索结果准确率）
- **R@K**: Recall at K（检索结果召回率）
- **NDCG@K**: 考虑排序的质量指标
- **MRR**: Mean Reciprocal Rank（首个相关结果的平均排名）

### 4. 安全沙箱系统

**多层安全保障：扫描→权限→沙箱**

```python
from services.code_security import CodeSecurityScanner
from services.code_sandbox import SandboxExecutor
from services.permission_manager import PermissionManager

# 1. 代码安全扫描
scanner = CodeSecurityScanner()
scan_result = scanner.scan(generated_code)

if scan_result.level == SecurityLevel.BLOCKED:
    raise SecurityError(f"代码包含危险操作: {scan_result.issues}")

# 2. 权限检查
permission_mgr = PermissionManager()
if not permission_mgr.check_permission("ec2", "terminate_instances"):
    raise PermissionError("禁止删除操作")

# 3. 沙箱执行
sandbox = SandboxExecutor(
    timeout=30,
    memory_limit_mb=512
)
result = sandbox.execute(
    code=generated_code,
    globals_dict={"boto3": boto3}
)
```

**安全特性**:
- ✅ 禁止exec/eval/compile等危险函数
- ✅ 禁止terminate/delete等资源删除操作
- ✅ 禁止os.system/subprocess等shell命令
- ✅ 限制模块导入（仅云SDK和安全模块）
- ✅ CPU时间和内存限制
- ✅ 敏感信息检测（密码、API密钥）

**权限管理**:
- AWS: 32个只读操作（describe_*, list_*, get_*）
- Azure: 14个只读操作
- GCP: 8个只读操作
- Kubernetes: 16个只读操作
- **总计70个API操作白名单**

### 5. 工具动态注册系统

**生成的代码自动注册为可复用工具**

```python
from services.tool_registry import ToolRegistry, GeneratedTool

registry = ToolRegistry()

# 注册工具
tool = GeneratedTool(
    name="list_ec2_instances",
    description="列出所有EC2实例",
    code=generated_code,
    test_code=test_code,
    parameters=[...],
    cloud_provider="aws",
    service="ec2",
    category="query"
)

result = registry.register(tool)
# 首次注册：版本1.0.0
# 代码变化：自动升级到1.0.1

# 搜索工具
tools = registry.search_tools(
    cloud_provider="aws",
    service="ec2",
    query="list instances"
)

# 使用工具
tool = tools[0]
result = exec(tool.code)

# 记录指标
registry.record_execution(
    tool_id=tool.tool_id,
    success=True,
    execution_time=0.5
)

# 质量评分自动更新
# 质量分 = 成功率*70% + 使用频率*20% + 执行速度*10%
```

**工作流程**:
```
1. 用户请求："列出K8s Pod"
2. registry.search_tools(query="list pods", cloud_provider="kubernetes")
3. 如果找到 → 直接使用现有工具（复用率100%）
4. 如果未找到 → CodeGeneratorAgent生成新代码
5. 测试通过 → registry.register(tool)
6. 下次同样请求 → 命中工具库，无需重新生成
```

### 6. 对话管理和上下文压缩

**支持多轮对话和任务续传**

```python
from services.conversation_manager import ConversationManager, MessageRole

manager = ConversationManager()

# 创建会话
session = manager.create_session(user_id="user1")

# 添加消息
manager.add_message(
    session.session_id,
    MessageRole.USER,
    "查询电商平台的EC2实例"
)

# 设置上下文变量
manager.set_context_variable(session.session_id, "business_name", "电商平台")

# 添加任务
task = manager.add_task(
    session.session_id,
    "查询AWS EC2实例"
)

# 任务执行失败
manager.update_task(
    session.session_id,
    task.task_id,
    status=TaskStatus.FAILED,
    error="网络超时"
)

# 恢复任务
manager.resume_task(session.session_id, task.task_id)
```

**上下文压缩**:
```python
from services.context_compressor import ContextCompressor

compressor = ContextCompressor()

# 长对话自动压缩
if len(session.messages) > 20:
    compressed_session = await compressor.compress_session(session)
    # 40条消息 → 1条总结 + 5条最近消息
```

**特性**:
- ✅ 24小时会话过期
- ✅ 消息历史持久化（JSON）
- ✅ 任务状态跟踪（pending→in_progress→completed/failed）
- ✅ 上下文变量管理（业务名称、云平台等）
- ✅ LLM总结历史（控制在token限制内）
- ✅ 任务续传（失败/暂停任务恢复）

### 7. DataAdapterAgent - 多云数据统一

**混合架构：规则引擎（快速）+ LLM（智能）**

```python
from agents.data_adapter_agent import DataAdapterAgent

agent = DataAdapterAgent()

# AWS EC2 → ComputeResource
aws_ec2_data = {
    "InstanceId": "i-1234567890abcdef0",
    "InstanceType": "t3.medium",
    "State": {"Name": "running"}
}

result = await agent.safe_process({
    "raw_data": aws_ec2_data,
    "cloud_provider": "aws",
    "target_schema": "ComputeResource"
})

# 快速规则：毫秒级转换
resource = result.data
print(f"资源ID: {resource.resource_id}")
print(f"状态: {resource.state}")
print(f"转换方法: {result.metadata['conversion_method']}")  # fast_rule
```

**支持的转换**:
- ✅ AWS/Azure/GCP/Volcano/K8s → ComputeResource
- ✅ CloudWatch/AzureMonitor/CloudMonitoring → MetricResult
- ✅ CloudWatchLogs/TLS → LogHealth
- ✅ X-Ray/AppInsights/CloudTrace → TraceHealth

## 🧪 测试

### 运行所有测试
```bash
# 代码质量集成测试
uv run pytest tests/test_code_quality_integration.py -v

# 对话管理测试
uv run pytest tests/test_conversation_manager.py -v

# DataAdapterAgent测试
uv run pytest tests/test_data_adapter_agent.py -v

# 工具注册表测试
uv run pytest tests/test_tool_registry.py -v

# 安全沙箱测试
uv run pytest tests/test_security_sandbox.py -v

# 增强RAG测试
uv run pytest tests/test_enhanced_rag.py -v
```

### 测试覆盖
- ✅ 代码质量分析（19个测试）
- ✅ 对话管理系统（18个测试）
- ✅ 数据适配转换
- ✅ 工具注册和搜索
- ✅ 安全沙箱系统
- ✅ RAG混合检索

## 📁 项目结构

```
multi-cloud-sre-agent/
├── agents/                          # Agent模块
│   ├── base_agent.py               # Agent基类
│   ├── manager_agent.py            # 任务编排Agent
│   ├── code_generator_agent.py     # ⭐ 代码生成Agent（ReAct模式）
│   ├── data_adapter_agent.py       # ⭐ 数据适配Agent
│   └── spec_doc_agent.py           # ⭐ SDK内省和文档提取Agent
│
├── services/                        # 核心服务
│   ├── doc_cache.py                # ⭐ 智能文档缓存
│   ├── enhanced_rag.py             # ⭐ 混合检索系统
│   ├── code_quality.py             # ⭐ 代码质量分析
│   ├── code_reviewer.py            # ⭐ 代码审查器
│   ├── code_templates.py           # ⭐ 代码模板库
│   ├── test_generator.py           # ⭐ 测试生成器
│   ├── code_security.py            # ⭐ 代码安全扫描
│   ├── code_sandbox.py             # ⭐ 沙箱执行环境
│   ├── permission_manager.py       # ⭐ 权限管理
│   ├── tool_registry.py            # ⭐ 工具注册表
│   ├── conversation_manager.py     # ⭐ 对话管理
│   └── context_compressor.py       # ⭐ 上下文压缩
│
├── schemas/                         # 统一Schema定义
│   ├── health_schema.py            # 健康检查Schema
│   ├── resource_schema.py          # 资源Schema
│   └── metric_schema.py            # 指标Schema
│
├── tools/                           # 云平台工具
│   ├── cloud_tools.py              # 工具注册中心
│   ├── aws_tools.py                # AWS监控工具
│   └── azure_tools.py              # Azure监控工具
│
├── tests/                           # 测试文件
│   ├── test_code_quality_integration.py
│   ├── test_conversation_manager.py
│   ├── test_data_adapter_agent.py
│   ├── test_tool_registry.py
│   ├── test_security_sandbox.py
│   └── test_enhanced_rag.py
│
├── rag_system.py                    # RAG系统
├── config.py                        # 配置管理
├── main.py                          # 主入口
└── orchestrator.py                  # 编排器
```

## 🎯 核心原则

1. **Agent优先**: 能让Agent生成的绝不手写
2. **质量优先**: 宁可慢一点，也要保证生成代码的正确性
3. **安全优先**: 沙箱隔离，防止恶意代码
4. **可观测**: 记录所有决策过程，便于调试和优化
5. **持续改进**: 从失败中学习，不断提升能力

## 🚧 开发中

- [ ] Manager Agent完整实现
- [ ] DiagnosticAgent故障诊断
- [ ] Agent协作优化
- [ ] 可观测性监控Dashboard

## 📊 系统统计

**当前能力**:
- 2032个API操作（AWS 898、Azure 79、K8s 1055）
- 15+个代码模板（分页、重试、批量处理等）
- 70个只读API操作白名单
- 代码质量评分系统（0-100分）
- 工具质量评分（成功率+频率+速度）

**测试覆盖**:
- 代码质量：19个测试✅
- 对话管理：18个测试✅
- 安全沙箱：5个测试✅
- 工具注册：5个测试✅
