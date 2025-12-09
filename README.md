# 多云SRE Agent系统

基于LangChain + LlamaIndex的智能多云SRE管理系统，支持AWS、阿里云、腾讯云、华为云、火山云。

核心功能：
- **Manager Agent**: 任务编排和意图识别
- **SpecDoc Agent**: API规格文档拉取
- **Code Generator**: 智能代码生成
- **RAG System**: 文档检索增强（ChromaDB + 多云文档库）
- **WASM Sandbox**: 安全代码测试
- **Cloud API Tools**: AWS监控工具（CloudWatch、Logs、X-Ray）

## 功能特性

- **智能任务编排**: 自动识别意图、拆解任务、规划执行
- **多云支持**: AWS、阿里云、腾讯云、华为云、火山云（聚焦可观测性）
- **动态代码生成**: 拉取API规格→RAG检索→生成代码→沙箱测试
- **RAG增强**: ChromaDB + 多云文档库，精准检索
- **安全隔离**: WASM沙箱完整测试（语法、功能、错误处理、边界条件）
- **可扩展架构**: 插件化设计，易于添加新云平台和服务

## 快速开始

### 安装
```bash
# 克隆项目
git clone <repo-url>
cd multi-cloud-sre-agent

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥
```

### 运行
```bash
# 交互模式
python main_new.py --mode interactive

# 单次查询
python main_new.py -q "查询AWS EC2的CPU使用率"

# 健康检查
python main_new.py --mode health

# 运行测试
python test_integration.py
```

## 使用方法

### 1. 命令行模式

#### 拉取AWS文档
```bash
# 拉取S3服务文档
python main.py --mode fetch --service S3

# 拉取EC2服务文档
python main.py --mode fetch --service EC2 --doc-type api
```

#### 生成代码
```bash
# 创建示例需求文件
python main.py --create-sample

# 生成Python代码
python main.py --mode generate --requirements sample_requirements.json --language python

# 生成JavaScript代码
python main.py --mode generate --requirements sample_requirements.json --language javascript

# 使用AWS文档生成代码
python main.py --mode generate --requirements sample_requirements.json --language python --docs S3_docs.json
```

### 2. 交互模式
```bash
python main.py --mode interactive
```

交互模式提供以下选项：
1. 拉取AWS文档
2. 生成代码
3. 拉取文档并生成代码
4. 查看Agent能力
5. 退出

### 3. 编程方式使用

#### 使用AWS文档拉取Agent
```python
import asyncio
from agents import AWSDocFetcher

async def fetch_s3_docs():
    doc_fetcher = AWSDocFetcher()
    response = await doc_fetcher.safe_process({
        'service_name': 'S3',
        'doc_type': 'api'
    })
    
    if response.success:
        print(f"成功拉取 {response.data['service_name']} 文档")
        return response.data
    else:
        print(f"拉取失败: {response.error}")
        return None

# 运行
asyncio.run(fetch_s3_docs())
```

#### 使用代码生成Agent
```python
import asyncio
from agents import CodeGenerator

async def generate_s3_code():
    code_generator = CodeGenerator()
    
    requirements = {
        'service_name': 's3',
        'region': 'us-east-1',
        'operations': [
            {
                'name': 'create_bucket',
                'api_call': 'create_bucket',
                'description': '创建S3存储桶',
                'parameters': {
                    'bucket_name': {
                        'type': 'str',
                        'description': '存储桶名称',
                        'required': True
                    }
                }
            }
        ]
    }
    
    response = await code_generator.generate_from_requirements(requirements, 'python')
    
    if response.success:
        print("代码生成成功!")
        print(response.data['code'])
        return response.data['code']
    else:
        print(f"生成失败: {response.error}")
        return None

# 运行
asyncio.run(generate_s3_code())
```

## 需求文件格式

代码生成Agent使用JSON格式的需求文件，示例如下：

```json
{
  "service_name": "s3",
  "region": "us-east-1",
  "operations": [
    {
      "name": "create_bucket",
      "api_call": "create_bucket",
      "description": "创建S3存储桶",
      "parameters": {
        "bucket_name": {
          "type": "str",
          "description": "存储桶名称",
          "required": true
        },
        "region": {
          "type": "str",
          "description": "AWS区域",
          "required": false
        }
      }
    },
    {
      "name": "list_objects",
      "api_call": "list_objects_v2",
      "description": "列出S3存储桶中的对象",
      "parameters": {
        "bucket_name": {
          "type": "str",
          "description": "存储桶名称",
          "required": true
        },
        "max_keys": {
          "type": "int",
          "description": "最大返回对象数量",
          "required": false
        }
      }
    }
  ],
  "include_main": true
}
```

### 字段说明
- `service_name`: AWS服务名称
- `region`: AWS区域
- `operations`: 操作列表
  - `name`: 生成的函数名称
  - `api_call`: AWS SDK API调用名称
  - `description`: 函数描述
  - `parameters`: 参数列表
    - `type`: 参数类型
    - `description`: 参数描述
    - `required`: 是否必需
- `include_main`: 是否包含主函数示例

## 生成的代码示例

### Python代码示例
```python
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

# Initialize AWS client
s3_client = boto3.client('s3', region_name='us-east-1')

def create_bucket(bucket_name, region):
    """
    创建S3存储桶
    
    Args:
        bucket_name (str): 存储桶名称
        region (str): AWS区域
    
    Returns:
        dict: Operation result
    """
    try:
        response = s3_client.create_bucket(
            'bucket_name': bucket_name,
            'region': region  # optional
        )
        return response
    except ClientError as e:
        logger.error(f"Error calling create_bucket: {e}")
        raise
```

### JavaScript代码示例
```javascript
const AWS = require('aws-sdk');

// Initialize AWS service
const s3 = new AWS.S3({
    region: 'us-east-1'
});

async function createBucket(bucketName, region) {
    /**
     * 创建S3存储桶
     * 
     * @param {Object} params - Operation parameters
     * @param {string} bucketName - 存储桶名称
     * @param {string} region - AWS区域
     * @returns {Promise<Object>} Operation result
     */
    try {
        const params = {
            bucketName,
            region  // optional
        };
        
        const result = await s3.createBucket(params).promise();
        return result;
    } catch (error) {
        console.error(`Error calling createBucket: ${error}`);
        throw error;
    }
}
```

## 测试

运行测试套件：
```bash
python test_agents.py
```

测试包括：
- AWS文档拉取功能测试
- 代码生成功能测试
- 多语言代码生成测试
- Agent集成测试

## 项目结构

```
multi-cloud-sre-agent/
├── agents/
│   ├── __init__.py          # Agent包导出
│   ├── base_agent.py        # Agent基类
│   ├── aws_doc_fetcher.py   # AWS文档拉取Agent
│   └── code_generator.py    # 代码生成Agent
├── main.py                  # 主程序入口
├── test_agents.py          # 测试文件
├── pyproject.toml          # 项目配置
└── README.md               # 项目文档
```

## 扩展和定制

### 添加新的编程语言支持
1. 在 `CodeGenerator` 类的 `_load_code_templates` 方法中添加新语言的模板
2. 在 `_generate_<language>_code` 方法中实现生成逻辑
3. 更新 `supported_languages` 列表

### 添加新的云服务支持
1. 在 `AWSDocFetcher` 中添加特定服务的URL模式
2. 更新文档提取逻辑以适应新的文档格式

### 自定义Agent
继承 `BaseAgent` 类并实现必要的方法：
```python
from agents.base_agent import BaseAgent, AgentResponse

class CustomAgent(BaseAgent):
    def __init__(self, config=None):
        super().__init__("Custom Agent", config)
    
    def get_capabilities(self):
        return ["custom_capability_1", "custom_capability_2"]
    
    def validate_input(self, input_data):
        # 实现输入验证逻辑
        return True
    
    async def process(self, input_data):
        # 实现核心处理逻辑
        return AgentResponse(success=True, data="处理结果")
```

## 故障排除

### 常见问题

1. **AWS文档拉取失败**
   - 检查网络连接
   - 确认服务名称拼写正确
   - 某些服务可能需要特定的URL模式

2. **代码生成错误**
   - 检查需求文件JSON格式是否正确
   - 确认所有必需字段都已提供
   - 验证API调用名称是否正确

3. **依赖安装问题**
   - 确保使用Python 3.13+
   - 尝试使用虚拟环境
   - 检查系统依赖是否完整

### 调试模式
启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```