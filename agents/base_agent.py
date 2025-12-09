"""
Agent基类，定义所有Agent的通用接口
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    """Agent响应的统一格式"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BaseAgent(ABC):
    """Agent基类，定义通用接口和行为"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    async def process(self, input_data: Any) -> AgentResponse:
        """
        处理输入数据并返回响应
        
        Args:
            input_data: 输入数据
            
        Returns:
            AgentResponse: 处理结果
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        获取Agent的能力列表
        
        Returns:
            List[str]: 能力列表
        """
        pass
    
    def validate_input(self, input_data: Any) -> bool:
        """
        验证输入数据
        
        Args:
            input_data: 输入数据
            
        Returns:
            bool: 验证结果
        """
        return True
    
    async def safe_process(self, input_data: Any) -> AgentResponse:
        """
        安全处理，包含异常处理
        
        Args:
            input_data: 输入数据
            
        Returns:
            AgentResponse: 处理结果
        """
        try:
            if not self.validate_input(input_data):
                return AgentResponse(
                    success=False,
                    error=f"Invalid input for {self.name}"
                )
            
            return await self.process(input_data)
        except Exception as e:
            self.logger.error(f"Error in {self.name}: {str(e)}")
            return AgentResponse(
                success=False,
                error=f"Error in {self.name}: {str(e)}"
            )
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
    
    def __repr__(self) -> str:
        return self.__str__()