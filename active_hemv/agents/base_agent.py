"""
基础Agent类，所有Active-H-EMV的Agent都继承自此类
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import agentscope
from agentscope.agents import AgentBase
from agentscope.message import Msg
from loguru import logger


class BaseMemoryAgent(AgentBase):
    """
    Active-H-EMV 系统的基础Agent类
    
    扩展了AgentScope的AgentBase,提供记忆系统专用的功能:
    - 统一的日志记录
    - 访问记录跟踪(用于效用计算)
    - 错误处理
    """
    
    def __init__(
        self,
        name: str,
        sys_prompt: Optional[str] = None,
        model_config_name: Optional[str] = None,
        storage_backends: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        初始化基础记忆Agent
        
        Args:
            name: Agent名称
            sys_prompt: 系统提示词
            model_config_name: 模型配置名称
            storage_backends: 存储后端配置 {"vector": ..., "graph": ..., "object": ...}
            **kwargs: 其他AgentScope参数
        """
        super().__init__(
            name=name,
            sys_prompt=sys_prompt,
            model_config_name=model_config_name,
            **kwargs
        )
        
        self.storage_backends = storage_backends or {}
        self.access_log: List[Dict[str, Any]] = []
        
        # 初始化日志
        logger.info(f"[{self.name}] Agent initialized")
    
    def log_access(self, node_id: str, operation: str, metadata: Optional[Dict] = None):
        """
        记录对记忆节点的访问(用于效用函数的访问热度A(n,t)计算)
        
        Args:
            node_id: 记忆节点ID
            operation: 操作类型 (read/write/update/delete)
            metadata: 额外元数据
        """
        access_record = {
            "agent": self.name,
            "node_id": node_id,
            "operation": operation,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }
        self.access_log.append(access_record)
        
        # 如果有向量数据库,同步更新访问计数
        if "vector" in self.storage_backends:
            try:
                self.storage_backends["vector"].update_access_count(node_id)
            except Exception as e:
                logger.warning(f"Failed to update access count: {e}")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        基础reply方法,子类必须覆盖实现
        
        Args:
            x: 输入消息
            
        Returns:
            Msg: 响应消息
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement reply()")
    
    def get_vector_store(self):
        """获取向量数据库实例"""
        return self.storage_backends.get("vector")
    
    def get_graph_store(self):
        """获取图数据库实例"""
        return self.storage_backends.get("graph")
    
    def get_object_store(self):
        """获取对象存储实例"""
        return self.storage_backends.get("object")
    
    def get_message_queue(self):
        """获取消息队列实例"""
        return self.storage_backends.get("message_queue")
    
    def handle_error(self, error: Exception, context: Dict[str, Any]) -> Msg:
        """
        统一的错误处理
        
        Args:
            error: 异常对象
            context: 错误上下文信息
            
        Returns:
            Msg: 错误响应消息
        """
        logger.error(
            f"[{self.name}] Error occurred: {str(error)}",
            extra={"context": context}
        )
        
        return Msg(
            name=self.name,
            content={
                "type": "error",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context
            },
            role="assistant"
        )
    
    def create_success_msg(self, content: Dict[str, Any]) -> Msg:
        """
        创建成功响应消息的辅助方法
        
        Args:
            content: 响应内容
            
        Returns:
            Msg: 成功响应消息
        """
        return Msg(
            name=self.name,
            content={
                "type": "success",
                "timestamp": datetime.now().isoformat(),
                **content
            },
            role="assistant"
        )

