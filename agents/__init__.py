"""
多云SRE Agent包
包含Manager Agent、SpecDoc Agent、Code Generator Agent等
"""

from .base_agent import BaseAgent, AgentResponse
from .manager_agent import ManagerAgent
from .spec_doc_agent import SpecDocAgent
from .code_generator_agent import CodeGeneratorAgent
from .data_adapter_agent import DataAdapterAgent

__all__ = [
    'BaseAgent',
    'AgentResponse',
    'ManagerAgent',
    'SpecDocAgent',
    'CodeGeneratorAgent',
    'DataAdapterAgent'
]

__version__ = '0.1.0'