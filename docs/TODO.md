# 多云SRE Agent - 任务清单

## 项目定位

**核心理念：** 我们不应该硬编码具体业务功能，而是打造一个能够自主生成代码的Agent系统。

**我们的职责：**
- ✅ 构建强大的RAG系统（让Agent获取准确的API文档）
- ✅ 开发Agent框架（让Agent能自主协作和决策）
- ✅ 提升代码生成质量（让Agent生成的代码可靠可用）
- ✅ 建立工具动态注册机制（让Agent自己创造工具）

**不应该做的：**
- ❌ 硬编码K8s工具类
- ❌ 手写CloudFront监控函数
- ❌ 实现具体的日志巡查逻辑
- ❌ 开发Trace根因分析算法

---

## ✅ 已完成

### 核心组件

- [x] **健康判断标准Schema** (`schemas/health_schema.py`)
  - 统一的HealthStatus枚举和阈值配置
  - MetricHealth、LogHealth、TraceHealth、ResourceHealth

- [x] **DataAdapterAgent** - 混合架构数据转换Agent
  - 规则引擎（快速路径）+ LLM引擎（智能路径）
  - 支持AWS、Azure、GCP、Volcano Engine、Kubernetes
  - 零代码扩展新云平台

- [x] **CodeGeneratorAgent - ReAct模式** ✨
  - 自主生成代码 → 测试 → 观察 → 修正（最多3次迭代）
  - 集成RAG文档检索
  - 带重试的LLM调用（应对网络不稳定）
  - 完整的单元测试覆盖

- [x] **RAG系统基础** (`rag_system.py`)
  - ChromaDB向量存储
  - HuggingFace Embeddings
  - 异步查询（避免阻塞事件循环）

### 基础工具

- [x] **AWS工具集** (`tools/aws_tools.py`)
  - EC2监控、CloudWatch指标、X-Ray、CloudWatch Logs
  - 批量查询和阈值过滤
  - 业务标签映射 (`services/tag_mapping_service.py`)

- [x] **测试框架**
  - pytest + pytest-asyncio
  - 单元测试（Mock LLM）
  - 集成测试（实际API调用）
  - HTML测试报告

---

## 📋 待完成任务

### 阶段一：动态文档系统 🎯

#### 任务1：实现DocumentFetcherAgent - 动态文档获取 (P0)

**目标：** Agent自主拉取最新在线API文档，而非依赖静态文档库

**核心理念：**
- ✅ Agent需要时**动态拉取**在线文档
- ✅ 永远使用**最新版本**API Spec
- ✅ 智能缓存 + 过期自动刷新
- ❌ 不手动整理文档
- ❌ 不静态存储

**实现内容：**
- [ ] 创建 `DocumentFetcherAgent` (`agents/document_fetcher_agent.py`)
  - 输入：云平台、服务名称、操作
  - 输出：相关API文档

- [ ] 实现文档源注册表 (`config/doc_sources.yaml`)
  ```yaml
  kubernetes:
    base_url: "https://kubernetes.io/docs/reference/"
    api_patterns:
      - "generated/kubernetes-api/v1.28/#list-pod-v1-core"
      - "generated/kubernetes-api/v1.28/#read-pod-v1-core"
    fetch_strategy: "scrape"  # 或 openapi_spec

  aws:
    base_url: "https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/"
    sdk_pattern: "client-{service}/class-{operation}command.html"
    fetch_strategy: "sdk_docs"

  gcp:
    base_url: "https://cloud.google.com/python/docs/reference/"
    openapi_spec: "https://raw.githubusercontent.com/googleapis/google-api-python-client/main/docs/dyn/"
    fetch_strategy: "openapi"
  ```

- [ ] 实现多种文档获取策略
  - **OpenAPI/Swagger Spec** - 直接解析结构化规格（最优）
  - **SDK文档爬取** - 解析官方SDK文档页面
  - **GitHub README/Examples** - 爬取示例代码
  - **LLM辅助解析** - 复杂HTML结构时用LLM提取关键信息

- [ ] 实现智能缓存机制 (`services/doc_cache.py`)
  ```python
  class DocumentCache:
      """文档缓存：有过期时间的RAG存储"""

      async def get_or_fetch(
          self,
          cloud_provider: str,
          service: str,
          operation: str,
          max_age_hours: int = 24  # 24小时过期
      ) -> List[Document]:
          # 1. 查询RAG缓存
          cached = await self.rag.query(...)
          if cached and not self._is_expired(cached):
              return cached

          # 2. 缓存过期，动态拉取
          fresh_docs = await self.fetcher.fetch_docs(...)

          # 3. 更新RAG
          await self.rag.update(fresh_docs)

          return fresh_docs
  ```

- [ ] 文档解析和结构化
  - 提取API签名、参数、返回值
  - 提取示例代码
  - 提取错误码和常见问题
  - 生成embeddings并存储

**工作流程：**
```
1. CodeGeneratorAgent需要生成"list K8s pods"代码
2. 调用DocumentCache.get_or_fetch("kubernetes", "core", "list_pod")
3. 检查RAG缓存 → 未找到或已过期
4. DocumentFetcherAgent拉取：
   - 访问 https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/
   - 使用LLM提取list_pod API文档
   - 解析参数：namespace, labelSelector, fieldSelector等
   - 提取Python示例代码
5. 存储到RAG（标记时间戳）
6. 返回最新文档给CodeGeneratorAgent
7. 下次24小时内请求 → 直接使用缓存
```

**验收标准：**
```python
# Agent能自动拉取K8s最新文档并生成代码
result = await orchestrator.process("列出电商平台的所有Pod")
# 1. 自动识别需要K8s API文档
# 2. 动态从kubernetes.io拉取最新文档
# 3. 生成正确代码
# 4. 下次请求复用缓存（24小时内）
```

---

#### 任务2：优化RAG检索质量 (P0)

**目标：** 提升文档检索的准确性和相关性

**实现内容：**
- [ ] 实现混合检索策略
  - 向量相似度检索
  - 关键词BM25检索
  - 混合排序（RRF - Reciprocal Rank Fusion）
- [ ] 添加重排序模型（Reranker）
  - 使用交叉编码器对候选文档重新排序
  - 提升Top-K结果的准确性
- [ ] 实现Query改写
  - 将用户自然语言转为API查询
  - 例如："列出Pod" → "list_pods API documentation"
- [ ] 添加检索评估指标
  - 记录检索成功率
  - 分析失败case并优化

**验收标准：**
- RAG检索准确率 > 85%
- Top-3命中率 > 95%

---

#### 任务3：实现OpenAPI Spec动态解析 (P1)

**目标：** 优先使用结构化API规格（OpenAPI/Swagger），自动解析

**核心理念：**
- ✅ 优先使用OpenAPI/Swagger等**结构化规格**
- ✅ 动态拉取最新Spec文件
- ✅ 自动解析为结构化API定义
- ❌ 不手动维护API规格数据库

**实现内容：**
- [ ] 创建 `OpenAPIParser` (`services/openapi_parser.py`)
  ```python
  class OpenAPIParser:
      """解析OpenAPI/Swagger规格"""

      async def fetch_and_parse(
          self,
          spec_url: str  # 例如：https://petstore3.swagger.io/api/v3/openapi.json
      ) -> Dict[str, APISpec]:
          # 1. 动态拉取OpenAPI JSON/YAML
          spec_content = await self._fetch(spec_url)

          # 2. 解析为结构化API定义
          apis = self._parse_openapi(spec_content)

          # 3. 返回API字典
          return apis  # {"listPets": APISpec(...), "createPet": APISpec(...)}
  ```

- [ ] 设计统一API规格Schema (`schemas/api_spec.py`)
  ```python
  class APISpec:
      name: str                    # list_pod
      cloud_provider: str          # kubernetes
      service: str                 # core_v1
      method: str                  # GET
      endpoint: str                # /api/v1/namespaces/{namespace}/pods
      parameters: List[Parameter]  # namespace, labelSelector...
      return_type: Dict            # PodList
      examples: List[str]          # 代码示例
      documentation_url: str       # 官方文档链接
      openapi_schema: Dict         # 原始OpenAPI schema
  ```

- [ ] 扩展文档源注册表支持OpenAPI
  ```yaml
  kubernetes:
    openapi_spec: "https://raw.githubusercontent.com/kubernetes/kubernetes/master/api/openapi-spec/swagger.json"
    fetch_strategy: "openapi"

  aws:
    # AWS没有官方OpenAPI，使用boto3 service model
    service_model: "boto3"
    fetch_strategy: "sdk_introspection"

  stripe:
    openapi_spec: "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json"
    fetch_strategy: "openapi"
  ```

- [ ] CodeGeneratorAgent优先使用OpenAPI规格
  ```python
  # 1. 尝试OpenAPI Spec（最精确）
  spec = await openapi_parser.get_spec("kubernetes", "list_pod")
  if spec:
      return await self._generate_from_spec(spec)

  # 2. Fallback到RAG文档检索
  docs = await rag.query(...)
  return await self._generate_from_docs(docs)
  ```

**优势：**
- **精确性**：OpenAPI规格是机器可读的，无歧义
- **完整性**：包含所有参数、类型、约束
- **最新性**：从GitHub拉取，永远是最新版本
- **自动化**：无需人工整理和维护

**支持的规格格式：**
- OpenAPI 3.x (JSON/YAML)
- Swagger 2.0
- gRPC Proto files
- GraphQL Schema
- Boto3 Service Models (AWS特有)

---

### 阶段二：Agent能力提升 🚀

#### 任务4：实现Manager Agent核心能力 (P0)

**目标：** 编排多个Agent协同工作，分解复杂任务

**实现内容：**
- [ ] 创建 `ManagerAgent` (`agents/manager_agent.py`)
  - 任务理解和分解
  - Agent选择和调度
  - 结果聚合和汇报
- [ ] 实现ReAct推理模式
  - Thought：分析任务，规划步骤
  - Action：调用子Agent或工具
  - Observation：观察结果，调整计划
- [ ] 实现多Agent协作协议
  - 定义Agent间通信格式
  - 支持顺序执行、并行执行、条件执行
- [ ] 添加任务执行跟踪
  - 记录执行历史
  - 支持断点续传

**场景示例：**
```
用户: "帮我分析电商平台业务的健康状况"

Manager Agent推理:
1. Thought: 需要收集多个维度的数据（CPU、日志、Trace）
2. Action: 调用CodeGeneratorAgent生成"查询EC2 CPU"代码并执行
3. Observation: 获得3台高CPU实例
4. Action: 调用CodeGeneratorAgent生成"查询日志ERROR"代码并执行
5. Observation: 发现500个错误日志
6. Action: 调用DataAdapterAgent转换为统一Health格式
7. Observation: 综合健康评分65分（不健康）
8. 返回：健康报告 + 问题列表 + 修复建议
```

**验收标准：**
- 能自主分解复杂任务为多个步骤
- 能根据中间结果动态调整计划
- 成功率 > 70%

---

#### 任务5：增强CodeGeneratorAgent代码质量 (P1)

**目标：** 提升生成代码的正确性和可维护性

**实现内容：**
- [ ] 添加代码静态分析
  - 集成pylint/flake8/mypy
  - 在测试前先检查代码质量
  - 发现问题时自动修正
- [ ] 增强测试生成能力
  - 生成边界条件测试
  - 生成异常处理测试
  - 覆盖率目标 > 80%
- [ ] 实现代码模板库
  - 常见模式的代码模板（分页、重试、批处理）
  - 优先使用模板，减少错误
- [ ] 添加代码review机制
  - 生成代码后自动review
  - 检查安全漏洞（SQL注入、XSS等）
  - 检查性能问题（N+1查询、无限循环）

**验收标准：**
- 生成代码首次测试通过率 > 60%
- 3次迭代后测试通过率 > 90%
- 无安全漏洞

---

#### 任务6：实现工具动态注册机制 (P1) ✨

**目标：** 让Agent生成的代码能自动注册为可复用工具

**实现内容：**
- [ ] 设计工具注册协议
  ```python
  class GeneratedTool:
      name: str
      description: str
      code: str
      test_code: str
      parameters: List[Parameter]
      return_type: Dict
      metadata: Dict
  ```
- [ ] 实现工具持久化
  - 保存生成的代码到 `generated/tools/`
  - 记录工具元信息到工具库
  - 支持版本管理
- [ ] 实现工具发现和调用
  - Manager Agent能查询可用工具
  - 优先复用已生成的工具，避免重复生成
- [ ] 实现工具质量评分
  - 记录工具使用次数、成功率
  - 淘汰低质量工具
  - 推荐高质量工具

**工作流程：**
```
1. 用户请求："列出K8s Pod"
2. Manager Agent查询工具库 → 未找到"list_pods"工具
3. 调用CodeGeneratorAgent生成代码
4. 测试通过后，注册为"list_pods"工具
5. 下次同样请求 → 直接复用工具，无需重新生成
```

**验收标准：**
- 工具复用率 > 50%（同样需求第二次无需生成）
- 工具库包含 > 20个高质量工具

---

#### 任务7：创建DiagnosticAgent诊断Agent (P2)

**目标：** 专门处理故障诊断和根因分析

**实现内容：**
- [ ] 创建 `DiagnosticAgent` (`agents/diagnostic_agent.py`)
  - 接收故障现象（如：Pod崩溃、API超时）
  - 自动收集相关数据（日志、指标、事件）
  - 调用CodeGeneratorAgent生成诊断代码
  - LLM分析数据并推断根因
- [ ] 实现多层诊断策略
  - 第一层：表面症状（如：CPU 100%）
  - 第二层：直接原因（如：进程死锁）
  - 第三层：根本原因（如：代码bug）
- [ ] 生成诊断报告
  - 问题描述
  - 根因分析
  - 修复建议
  - 预防措施

**场景示例：**
```
用户: "web-app-xyz Pod一直CrashLoopBackOff"

DiagnosticAgent工作流程:
1. 生成并执行"kubectl describe pod"代码 → 发现OOMKilled
2. 生成并执行"kubectl logs"代码 → 发现内存持续增长
3. 生成并执行"查询内存指标"代码 → 确认内存泄漏
4. LLM分析：内存限制256MB，实际使用450MB
5. 返回报告：OOM根因 + 增加limit建议 + 排查内存泄漏建议
```

---

### 阶段三：系统完善 🔧

#### 任务8：实现Agent对话历史管理 (P1)

**目标：** 支持多轮对话和上下文理解

**实现内容：**
- [ ] 创建对话Session管理器
  - 跟踪用户会话
  - 保存对话历史
  - 支持上下文引用（"再查一下"、"那个业务"）
- [ ] 实现上下文压缩
  - 长对话自动总结
  - 保留关键信息
  - 控制LLM输入长度
- [ ] 支持任务续传
  - 保存任务执行状态
  - 失败后可恢复

---

#### 任务9：添加可观测性和监控 (P1)

**目标：** 监控Agent系统运行状况

**实现内容：**
- [ ] 添加结构化日志
  - 使用structlog
  - 记录Agent决策过程
  - 记录代码生成和执行结果
- [ ] 实现性能指标收集
  - Agent响应时间
  - 代码生成成功率
  - LLM调用次数和成本
  - RAG检索质量
- [ ] 创建监控Dashboard
  - Grafana + Prometheus
  - 可视化关键指标
  - 异常告警

---

#### 任务10：实现安全沙箱 (P0)

**目标：** 安全地执行生成的代码

**实现内容：**
- [ ] 完善WASM沙箱
  - 限制文件系统访问
  - 限制网络访问（仅允许白名单API）
  - 限制CPU/内存使用
- [ ] 添加代码审查
  - 扫描危险函数（exec、eval、os.system）
  - 扫描敏感信息泄露
  - 扫描恶意行为
- [ ] 实现权限管理
  - 不同云平台的权限隔离
  - 最小权限原则

**安全要求：**
- 生成的代码不能删除资源（只读查询）
- 不能访问本地文件系统
- 不能执行任意shell命令

---

#### 任务11：建立Agent能力评测体系 (P2)

**目标：** 量化评估Agent能力并持续改进

**实现内容：**
- [ ] 创建评测数据集
  - 收集真实SRE场景问题
  - 标注正确答案和执行步骤
  - 覆盖简单/困难/复杂任务
- [ ] 实现自动化评测
  - 正确性：生成代码能否运行
  - 完整性：是否解决了用户问题
  - 效率：执行步骤是否冗余
  - 质量：代码是否符合最佳实践
- [ ] 建立回归测试
  - 每次改动后运行评测
  - 防止能力退化

**评测指标：**
- 任务完成率
- 代码生成成功率
- 平均执行步骤数
- 用户满意度

---

### 阶段四：高级能力 🌟

#### 任务12：Agent自主学习能力 (P3)

**目标：** Agent从失败中学习并改进

**实现内容：**
- [ ] 记录失败案例
  - 保存失败的任务请求
  - 保存生成的错误代码
  - 保存错误信息
- [ ] 失败案例分析
  - LLM分析失败原因
  - 提取改进建议
  - 更新生成策略
- [ ] 知识库自动扩充
  - 从成功案例提取模式
  - 补充到RAG文档库
  - 生成新的代码模板

---

#### 任务13：多Agent协作优化 (P3)

**目标：** 提升Agent之间的协作效率

**实现内容：**
- [ ] 实现Agent负载均衡
  - 多个CodeGeneratorAgent并行工作
  - 分布式任务队列
- [ ] 实现Agent专业化
  - 创建专精Agent（K8sAgent、AWSAgent）
  - 根据任务类型选择最佳Agent
- [ ] 实现Agent间知识共享
  - 共享成功经验
  - 共享工具库
  - 协同优化

---

## 优先级排序

### P0 - 立即开始（Agent能力核心）
1. ✅ 任务4：Manager Agent核心能力 - **最高优先级**
2. 任务1：DocumentFetcherAgent - 动态文档获取 ✨
3. 任务2：优化RAG检索质量
4. 任务10：安全沙箱

### P1 - 重要（质量和可用性）
5. 任务5：增强代码生成质量
6. 任务6：工具动态注册机制 ✨
7. 任务8：对话历史管理
8. 任务9：可观测性监控

### P2 - 高级（功能增强）
9. 任务3：API规格库
10. 任务7：DiagnosticAgent诊断
11. 任务11：能力评测体系

### P3 - 探索（未来方向）
12. 任务12：自主学习能力
13. 任务13：多Agent协作优化

---

## 当前进度

```
核心理念: Agent自主生成代码，而非硬编码功能 ✅
已完成: RAG基础、CodeGeneratorAgent ReAct、DataAdapterAgent
下一步: Manager Agent → 动态文档获取 → 工具动态注册

阶段一 动态文档系统:  0/3 完成 (DocumentFetcherAgent、RAG优化、OpenAPI解析)
阶段二 Agent能力提升: 1/4 完成 (CodeGeneratorAgent ✅)
阶段三 系统完善:      0/4 完成
阶段四 高级能力:      0/2 完成
```

---

## 验收标准

### 简单模式（基础能力）
- [ ] 用户："列出CPU>80%的EC2实例"
  - Manager Agent → CodeGeneratorAgent生成代码 → 执行 → 返回结果
  - 无需我们手写任何EC2查询逻辑

### 困难模式（复杂任务）
- [ ] 用户："帮我分析电商平台的健康状况"
  - Manager Agent分解任务 → 生成多段代码 → 执行 → 聚合分析 → 返回报告
  - 涉及EC2、K8s、日志、Trace多个数据源

### 地狱模式（自主诊断）
- [ ] 用户："Pod一直崩溃，帮我定位原因"
  - DiagnosticAgent → 生成诊断代码 → 收集数据 → LLM分析 → 返回根因报告
  - 完全自主，无需人工介入

---

## 里程碑

### M1: Agent框架完备 (预计2周)
- ✅ CodeGeneratorAgent ReAct
- ✅ DataAdapterAgent
- 🔨 Manager Agent
- 🔨 工具动态注册

### M2: 动态文档系统 (预计1周)
- 🔨 DocumentFetcherAgent - 自动拉取在线文档
- 🔨 RAG检索质量优化
- 🔨 OpenAPI Spec动态解析

### M3: 质量和安全 (预计1周)
- 🔨 代码质量增强
- 🔨 安全沙箱
- 🔨 可观测性

### M4: 高级能力 (预计2周)
- 🔨 DiagnosticAgent
- 🔨 对话管理
- 🔨 能力评测

---

## 关键原则

1. **Agent优先**：能让Agent生成的绝不手写
2. **质量优先**：宁可慢一点，也要保证生成代码的正确性
3. **安全优先**：沙箱隔离，防止恶意代码
4. **可观测**：记录所有决策过程，便于调试和优化
5. **持续改进**：从失败中学习，不断提升能力

