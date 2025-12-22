# 快速启动指南

## 🚀 5分钟快速启动

### 1. 环境准备

**必需：**
- Python 3.10+
- uv (包管理器)

**可选：**
- 云平台凭证（AWS/Azure/GCP等）

### 2. 安装依赖

```bash
# 安装uv（如果没有）
# Windows PowerShell:
# irm https://astral.sh/uv/install.ps1 | iex

# 同步依赖
uv sync
```

### 3. 配置API密钥

编辑 `.env` 文件（已存在）：
```bash
# LLM配置（硅基流动API）
OPENAI_API_KEY=sk-你的密钥
OPENAI_API_BASE=https://api.siliconflow.cn/v1

# 云平台凭证（可选，用于实际调用云API）
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# AZURE_SUBSCRIPTION_ID=your_subscription_id
# ...
```

### 4. 运行健康检查

```bash
# Windows:
run.bat health

# Linux/Mac:
./run.sh health

# 或直接使用Python:
uv run python test_health.py
```

**预期输出：**
```
✅ manager_agent: ok
✅ spec_doc_agent: ok
✅ code_gen_agent: ok
✅ rag_system: ok
✅ tool_registry: ok (18个工具)
✅ sandbox: ok
✅ conversation_manager: ok
```

### 5. 运行交互模式

```bash
# Windows:
run.bat

# Linux/Mac:
./run.sh

# 或直接：
uv run python main.py --mode interactive
```

### 6. 运行单次查询

```bash
# Windows:
run.bat query "查询AWS EC2实例"

# Linux/Mac:
./run.sh query "查询AWS EC2实例"

# 或直接：
uv run python main.py -q "查询AWS EC2实例"
```

---

## 📝 核心功能演示

### 演示1：健康检查
```bash
uv run python test_health.py
```
- 检查所有组件状态
- 查看工具数量
- 验证RAG系统

### 演示2：查看已注册工具
```python
from tools.cloud_tools import get_tool_registry

registry = get_tool_registry()
tools = registry.list_tools()

print(f"已注册工具数: {len(tools)}")
for tool in tools[:5]:
    print(f"  - {tool}")
```

### 演示3：对话管理
```python
from orchestrator import get_orchestrator
import asyncio

async def demo():
    orch = get_orchestrator()

    # 创建会话并查询
    result = await orch.process_request(
        "查询AWS CloudWatch告警",
        user_id="demo_user"
    )

    session_id = result["session_id"]

    # 查看对话历史
    history = orch.get_conversation_history(session_id)
    print(f"对话消息数: {len(history)}")

asyncio.run(demo())
```

---

## 🔧 常见问题

### Q1: 报错 "SOCKS proxy error"
**原因：** 系统代理设置冲突

**解决：** 使用 `run.bat` 或 `run.sh` 启动（自动禁用代理）

### Q2: 没有云平台凭证怎么办？
**答：** 可以正常运行！系统会：
- 使用Mock数据进行演示
- 展示代码生成能力
- 所有Agent仍然可用

### Q3: LLM API密钥无效
**答：** 检查 `.env` 文件：
- 确保API密钥格式正确（sk-开头）
- 确认base_url是 `https://api.siliconflow.cn/v1`
- 访问硅基流动官网确认额度

### Q4: 如何查看日志？
```bash
# 开启详细日志
uv run python main.py -q "测试查询" --verbose

# 或查看日志文件
# logs/目录（如果启用）
```

---

## 🎯 答辩演示建议

### 场景1：系统架构演示（2分钟）
```bash
# 1. 健康检查
uv run python test_health.py

# 展示点：
- 7大核心组件
- 18个预注册工具
- RAG系统ready
- 对话管理ready
```

### 场景2：工具注册演示（3分钟）
```python
# 展示工具库
from tools.cloud_tools import get_tool_registry

registry = get_tool_registry()
print(f"工具总数: {len(registry.list_tools())}")

# 展示搜索功能
aws_tools = registry.search_tools(cloud_provider="aws")
print(f"AWS工具: {len(aws_tools)}个")
```

### 场景3：代码生成演示（5分钟）
```bash
# 使用Mock模式展示（无需真实凭证）
uv run python demo/code_generation_demo.py

# 展示：
- 意图识别
- 代码生成
- 安全检查
- 代码执行
```

---

## 📦 项目结构

```
multi-cloud-sre-agent/
├── agents/                 # Agent实现
│   ├── manager_agent.py    # 主协调Agent
│   ├── code_generator_agent.py  # 代码生成
│   ├── spec_doc_agent.py   # 文档提取
│   └── data_adapter_agent.py    # 数据适配
├── services/              # 核心服务
│   ├── conversation_manager.py  # 对话管理
│   ├── context_compressor.py    # 上下文压缩
│   ├── tool_registry.py   # 工具注册表
│   ├── code_security.py   # 代码安全
│   └── enhanced_rag.py    # 增强RAG
├── tools/                 # 工具集
│   ├── aws_tools.py       # AWS工具
│   ├── azure_tools.py     # Azure工具
│   └── cloud_tools.py     # 统一工具注册
├── orchestrator.py        # 编排器
├── main.py               # 主程序
├── test_health.py        # 健康检查
├── run.bat / run.sh      # 启动脚本
└── .env                  # 配置文件
```

---

## 🚨 重要提示

1. **代理问题：** 必须使用 `run.bat/run.sh` 或手动禁用系统代理
2. **API密钥：** 确保 `.env` 中的LLM密钥有效
3. **编码问题：** Windows下使用UTF-8编码（脚本已处理）
4. **演示模式：** 即使没有云平台凭证，也能演示大部分功能

---

## 📞 支持

遇到问题？

1. 查看 `README.md` 详细文档
2. 运行 `uv run python test_health.py` 检查系统状态
3. 检查 `.env` 配置是否正确
4. 查看TODO.md了解开发进度

---

## ✨ 核心亮点（答辩时强调）

1. **SDK内省技术** - 2032个API操作自动提取，无需手动维护
2. **ReAct模式** - 代码生成→测试→观察→修正
3. **混合检索** - 向量+BM25+Reranker，检索准确率高
4. **安全沙箱** - 70个只读API白名单，禁止危险操作
5. **工具动态注册** - 质量评分、版本管理、自动复用
6. **对话管理** - 会话持久化、任务续传、上下文压缩
7. **完整测试** - 64个测试用例，覆盖核心功能
