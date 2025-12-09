"""
测试Agent功能
"""
import asyncio
import logging
from agents import AWSDocFetcher, CodeGenerator

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_aws_doc_fetcher():
    """测试AWS文档拉取Agent"""
    print("=" * 50)
    print("测试AWS文档拉取Agent")
    print("=" * 50)
    
    # 创建AWS文档拉取Agent
    doc_fetcher = AWSDocFetcher()
    
    # 测试获取能力
    capabilities = doc_fetcher.get_capabilities()
    print(f"Agent能力: {capabilities}")
    
    # 测试拉取S3服务文档
    test_input = {
        'service_name': 'S3',
        'doc_type': 'api'
    }
    
    try:
        print(f"\n正在拉取 {test_input['service_name']} 文档...")
        response = await doc_fetcher.safe_process(test_input)
        
        if response.success:
            print(f"✅ 成功拉取文档!")
            print(f"服务名称: {response.data['service_name']}")
            print(f"找到文档数量: {response.data['total_links_found']}")
            print(f"获取的文档数量: {len(response.data['documents'])}")
            
            # 显示第一个文档的信息
            if response.data['documents']:
                first_doc = response.data['documents'][0]
                print(f"\n第一个文档标题: {first_doc['title']}")
                print(f"API章节数量: {len(first_doc['api_sections'])}")
                print(f"表格数量: {len(first_doc['tables'])}")
        else:
            print(f"❌ 拉取文档失败: {response.error}")
            
    except Exception as e:
        print(f"❌ 测试过程中出现异常: {str(e)}")


async def test_code_generator():
    """测试代码生成Agent"""
    print("\n" + "=" * 50)
    print("测试代码生成Agent")
    print("=" * 50)
    
    # 创建代码生成Agent
    code_generator = CodeGenerator()
    
    # 测试获取能力
    capabilities = code_generator.get_capabilities()
    print(f"Agent能力: {capabilities}")
    
    # 测试生成Python代码
    test_requirements = {
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
                    },
                    'region': {
                        'type': 'str', 
                        'description': 'AWS区域',
                        'required': False
                    }
                }
            },
            {
                'name': 'list_objects',
                'api_call': 'list_objects_v2',
                'description': '列出S3存储桶中的对象',
                'parameters': {
                    'bucket_name': {
                        'type': 'str',
                        'description': '存储桶名称',
                        'required': True
                    },
                    'max_keys': {
                        'type': 'int',
                        'description': '最大返回对象数量',
                        'required': False
                    }
                }
            }
        ],
        'include_main': True
    }
    
    test_input = {
        'requirements': test_requirements,
        'language': 'python'
    }
    
    try:
        print(f"\n正在生成 {test_input['language']} 代码...")
        response = await code_generator.safe_process(test_input)
        
        if response.success:
            print(f"✅ 成功生成代码!")
            print(f"语言: {response.data['language']}")
            print(f"API信息数量: {response.data['api_info_count']}")
            print(f"生成时间: {response.data['generated_at']}")
            
            print("\n生成的代码:")
            print("-" * 40)
            print(response.data['code'])
            print("-" * 40)
        else:
            print(f"❌ 生成代码失败: {response.error}")
            
    except Exception as e:
        print(f"❌ 测试过程中出现异常: {str(e)}")


async def test_javascript_code_generation():
    """测试JavaScript代码生成"""
    print("\n" + "=" * 50)
    print("测试JavaScript代码生成")
    print("=" * 50)
    
    code_generator = CodeGenerator()
    
    test_requirements = {
        'service_name': 'ec2',
        'region': 'us-west-2',
        'operations': [
            {
                'name': 'describeInstances',
                'api_call': 'describe_instances',
                'description': '描述EC2实例',
                'parameters': {
                    'instance_ids': {
                        'type': 'array',
                        'description': '实例ID列表',
                        'required': False
                    }
                }
            }
        ],
        'include_example': True
    }
    
    test_input = {
        'requirements': test_requirements,
        'language': 'javascript'
    }
    
    try:
        print(f"\n正在生成 {test_input['language']} 代码...")
        response = await code_generator.safe_process(test_input)
        
        if response.success:
            print(f"✅ 成功生成JavaScript代码!")
            print("\n生成的代码:")
            print("-" * 40)
            print(response.data['code'])
            print("-" * 40)
        else:
            print(f"❌ 生成JavaScript代码失败: {response.error}")
            
    except Exception as e:
        print(f"❌ 测试过程中出现异常: {str(e)}")


async def test_agent_integration():
    """测试Agent集成功能"""
    print("\n" + "=" * 50)
    print("测试Agent集成功能")
    print("=" * 50)
    
    try:
        # 1. 首先拉取AWS文档
        doc_fetcher = AWSDocFetcher()
        doc_fetcher = AWSDocFetcher()
        code_generator = CodeGenerator()
        
        print("步骤1: 拉取AWS文档...")
        doc_response = await doc_fetcher.safe_process({
            'service_name': 'lambda',
            'doc_type': 'api'
        })
        
        if doc_response.success:
            print("✅ 文档拉取成功!")
            
            # 2. 使用拉取的文档生成代码
            print("\n步骤2: 基于文档生成代码...")
            code_requirements = {
                'service_name': 'lambda',
                'region': 'us-east-1',
                'operations': [
                    {
                        'name': 'create_function',
                        'api_call': 'create_function',
                        'description': '创建Lambda函数',
                        'parameters': {
                            'function_name': {
                                'type': 'str',
                                'description': '函数名称',
                                'required': True
                            },
                            'runtime': {
                                'type': 'str',
                                'description': '运行时环境',
                                'required': True
                            },
                            'role': {
                                'type': 'str',
                                'description': '执行角色ARN',
                                'required': True
                            }
                        }
                    }
                ]
            }
            
            code_response = await code_generator.generate_with_docs(
                requirements=code_requirements,
                aws_docs=doc_response.data,
                language='python'
            )
            
            if code_response.success:
                print("✅ 代码生成成功!")
                print("\n生成的集成代码:")
                print("-" * 40)
                print(code_response.data['code'])
                print("-" * 40)
            else:
                print(f"❌ 代码生成失败: {code_response.error}")
        else:
            print(f"❌ 文档拉取失败: {doc_response.error}")
            
    except Exception as e:
        print(f"❌ 集成测试过程中出现异常: {str(e)}")


async def main():
    """主测试函数"""
    print("开始测试Agent功能...")
    
    # 测试各个Agent
    await test_aws_doc_fetcher()
    await test_code_generator()
    await test_javascript_code_generation()
    await test_agent_integration()
    
    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())