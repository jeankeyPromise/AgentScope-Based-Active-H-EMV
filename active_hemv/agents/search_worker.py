"""
Search-Worker Agent: 并行搜索工作Agent

用于Memory Orchestrator的推测性并行搜索
"""

from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger

from agentscope.message import Msg
from .base_agent import BaseMemoryAgent


class SearchWorkerAgent(BaseMemoryAgent):
    """
    搜索工作Agent - 在特定范围内进行并行搜索
    
    用途:
    - 被Memory Orchestrator动态创建
    - 并行搜索不同时间范围
    - 返回局部搜索结果
    """
    
    def __init__(
        self,
        name: str = "SearchWorker",
        model_config_name: Optional[str] = None,
        storage_backends: Optional[Dict] = None,
        time_range: Optional[tuple] = None,  # (start_datetime, end_datetime)
        search_query: Optional[str] = None,
        **kwargs
    ):
        """
        初始化搜索工作Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置
            storage_backends: 存储后端
            time_range: 搜索的时间范围
            search_query: 搜索查询
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            storage_backends=storage_backends,
            **kwargs
        )
        
        self.time_range = time_range
        self.search_query = search_query
        
        logger.debug(f"[{self.name}] Initialized for range: {time_range}")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        执行搜索并返回结果
        
        输入消息格式 (可选,也可以使用初始化参数):
        {
            "type": "search_request",
            "query": str,
            "time_range": (datetime, datetime)
        }
        
        返回消息格式:
        {
            "type": "search_result",
            "found": bool,
            "results": List[Dict],
            "time_range": str
        }
        """
        try:
            # 从消息或初始化参数获取搜索信息
            query = x.content.get("query") if x else self.search_query
            time_range = x.content.get("time_range") if x else self.time_range
            
            if not query or not time_range:
                return self.handle_error(
                    ValueError("Missing query or time_range"),
                    {}
                )
            
            # 执行搜索
            results = self.search(query, time_range)
            
            return self.create_success_msg({
                "found": len(results) > 0,
                "results": results,
                "time_range": f"{time_range[0]} - {time_range[1]}",
                "count": len(results)
            })
            
        except Exception as e:
            return self.handle_error(e, {"query": query if 'query' in locals() else None})
    
    def search(self, query: str, time_range: tuple) -> list:
        """
        在指定时间范围内搜索
        
        Args:
            query: 搜索查询
            time_range: (start, end) datetime元组
            
        Returns:
            List[Dict]: 搜索结果
        """
        vector_store = self.get_vector_store()
        if not vector_store:
            logger.warning(f"[{self.name}] Vector store not available")
            return []
        
        try:
            start, end = time_range
            
            # 构建时间过滤器
            filters = {
                "timestamp_start": (">=", int(start.timestamp())),
                "timestamp_end": ("<=", int(end.timestamp()))
            }
            
            # 语义搜索
            results = vector_store.search(query, top_k=5, filters=filters)
            
            # 记录访问
            for result in results:
                self.log_access(result["node_id"], "read", {"search_query": query})
            
            logger.info(f"[{self.name}] Found {len(results)} results in range {start.date()} - {end.date()}")
            
            return results
            
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}")
            return []

