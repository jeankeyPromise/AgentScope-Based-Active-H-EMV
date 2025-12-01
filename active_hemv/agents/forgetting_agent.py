"""
ForgettingAgent - 遗忘Agent

模拟人类的遗忘过程，主动删除低效用记忆，压缩存储空间

灵感来源: Ebbinghaus遗忘曲线
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from agentscope.agent import AgentBase
from agentscope.message import Msg
from em.em_tree import HigherLevelSummary, AnyTreeNode


class ForgettingAgent(AgentBase):
    """
    遗忘Agent - 处理整棵记忆树的遗忘
    
    职责:
    1. 计算每个节点的效用值 U(n,t) = α·A + β·S + γ·I
    2. 根据效用值删除/压缩低价值记忆
    3. 释放存储空间
    
    运行频率: 每小时/每天
    """
    
    def __init__(
        self,
        name: str = "ForgettingAgent",
        model_config_name: Optional[str] = None,
        utility_weights: tuple = (0.5, 0.3, 0.2),  # (α, β, γ)
        threshold_low: float = 0.2,
        threshold_med: float = 0.4,
        threshold_high: float = 0.7,
        **kwargs
    ):
        """
        初始化遗忘Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置(用于语义显著性评估)
            utility_weights: 效用函数权重 (访问热度, 语义显著性, 信息密度)
            threshold_low/med/high: 三级效用阈值
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            **kwargs
        )
        
        # 导入效用评分器和遗忘策略
        from active_hemv.memory import UtilityScorer, ForgettingPolicy
        
        self.utility_scorer = UtilityScorer(*utility_weights)
        self.forgetting_policy = ForgettingPolicy(
            threshold_high=threshold_high,
            threshold_med=threshold_med,
            threshold_low=threshold_low
        )
        
        # 统计信息
        self.stats = {
            "total_cycles": 0,
            "nodes_processed": 0,
            "nodes_forgotten": 0,
            "nodes_compressed": 0,
            "storage_saved_mb": 0.0
        }
        
        logger.info(f"[{self.name}] Initialized with utility weights α={utility_weights[0]}, β={utility_weights[1]}, γ={utility_weights[2]}")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        处理遗忘请求
        
        输入消息格式:
        {
            "type": "forgetting_cycle",
            "memory_tree": HigherLevelSummary,
            "current_time": datetime (可选)
        }
        
        返回消息格式:
        {
            "type": "forgetting_result",
            "updated_tree": HigherLevelSummary,
            "stats": Dict
        }
        """
        try:
            if x is None or x.content.get("type") != "forgetting_cycle":
                return Msg(
                    name=self.name,
                    content={
                        "type": "error",
                        "message": "Invalid message type, expected 'forgetting_cycle'"
                    },
                    role="assistant"
                )
            
            memory_tree = x.content.get("memory_tree")
            current_time = x.content.get("current_time", datetime.now())
            
            if memory_tree is None:
                return Msg(
                    name=self.name,
                    content={"type": "error", "message": "memory_tree is required"},
                    role="assistant"
                )
            
            logger.info(f"[{self.name}] Starting forgetting cycle #{self.stats['total_cycles'] + 1}")
            
            # 执行遗忘周期
            updated_tree, cycle_stats = self._forgetting_cycle(memory_tree, current_time)
            
            # 更新全局统计
            self.stats["total_cycles"] += 1
            self.stats["nodes_processed"] += cycle_stats["processed"]
            self.stats["nodes_forgotten"] += cycle_stats["forgotten"]
            self.stats["nodes_compressed"] += cycle_stats["compressed"]
            self.stats["storage_saved_mb"] += cycle_stats["storage_saved_mb"]
            
            logger.info(
                f"[{self.name}] Cycle completed: "
                f"forgotten={cycle_stats['forgotten']}, "
                f"compressed={cycle_stats['compressed']}, "
                f"saved={cycle_stats['storage_saved_mb']:.2f}MB"
            )
            
            return Msg(
                name=self.name,
                content={
                    "type": "forgetting_result",
                    "updated_tree": updated_tree,
                    "cycle_stats": cycle_stats,
                    "cumulative_stats": self.stats
                },
                role="assistant"
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] Forgetting cycle failed: {e}")
            return Msg(
                name=self.name,
                content={"type": "error", "message": str(e)},
                role="assistant"
            )
    
    def _forgetting_cycle(
        self, 
        memory_tree: HigherLevelSummary, 
        current_time: datetime
    ) -> tuple:
        """
        执行一次完整的遗忘周期
        
        Returns:
            (updated_tree, stats): 更新后的树和统计信息
        """
        stats = {
            "processed": 0,
            "forgotten": 0,
            "compressed": 0,
            "storage_saved_mb": 0.0
        }
        
        # 1. 遍历树，计算每个节点的效用值
        all_nodes = self._collect_all_nodes(memory_tree)
        
        for node in all_nodes:
            stats["processed"] += 1
            
            # 计算效用值
            utility = self.utility_scorer.compute(
                self._node_to_dict(node),
                current_time,
                [self._node_to_dict(n) for n in all_nodes],
                llm_model=self.model if hasattr(self, 'model') else None
            )
            
            # 存储到节点（如果可能）
            if hasattr(node, 'utility_score'):
                node.utility_score = utility
            
            # 2. 根据效用值决定操作
            action = self.forgetting_policy.apply(utility)
            
            if action == "forget_raw":
                # 删除L0/L1的原始数据
                storage_freed = self._forget_raw_data(node)
                stats["forgotten"] += 1
                stats["storage_saved_mb"] += storage_freed
                
            elif action == "downgrade":
                # 压缩数据
                storage_freed = self._compress_node(node)
                stats["compressed"] += 1
                stats["storage_saved_mb"] += storage_freed
            
            elif action == "text_only":
                # 仅保留文本
                storage_freed = self._text_only(node)
                stats["forgotten"] += 1
                stats["storage_saved_mb"] += storage_freed
        
        return memory_tree, stats
    
    def _collect_all_nodes(self, tree: HigherLevelSummary) -> list:
        """递归收集树中的所有节点"""
        nodes = [tree]
        
        if hasattr(tree, 'children'):
            for child in tree.children:
                nodes.extend(self._collect_all_nodes(child))
        elif hasattr(tree, 'events'):
            for event in tree.events:
                nodes.extend(self._collect_all_nodes(event))
        elif hasattr(tree, 'scenes'):
            for scene in tree.scenes:
                nodes.append(scene)
        
        return nodes
    
    def _node_to_dict(self, node: Any) -> Dict:
        """将节点转换为dict格式（用于效用计算）"""
        node_dict = {
            "node_id": str(id(node)),
            "level": node.__class__.__name__,
            "nl_summary": getattr(node, 'nl_summary', ''),
            "timestamp_start": 0,
            "timestamp_end": 0,
            "utility_score": getattr(node, 'utility_score', 0.5),
            "is_locked": getattr(node, 'is_locked', False),
            "access_count": getattr(node, 'access_count', 0),
            "last_accessed": 0
        }
        
        # 提取时间戳
        if hasattr(node, 'range'):
            try:
                start, end = node.range
                node_dict["timestamp_start"] = int(start.timestamp())
                node_dict["timestamp_end"] = int(end.timestamp())
            except:
                pass
        elif hasattr(node, 'raw') and hasattr(node.raw, 'timestamp'):
            ts = int(node.raw.timestamp.timestamp())
            node_dict["timestamp_start"] = ts
            node_dict["timestamp_end"] = ts
        
        return node_dict
    
    def _forget_raw_data(self, node: Any) -> float:
        """
        删除节点的原始数据（图像/音频）
        
        Returns:
            float: 释放的存储空间(MB)
        """
        storage_freed = 0.0
        
        try:
            # 如果节点有原始图像
            if hasattr(node, 'raw') and hasattr(node.raw, 'image') and node.raw.image:
                # 估算图像大小 (假设640x480 RGB)
                storage_freed += 0.9  # ~1MB
                node.raw.image = None
                logger.debug(f"Deleted image from node {id(node)}")
            
            # 如果节点有音频
            if hasattr(node, 'raw') and hasattr(node.raw, 'sound') and node.raw.sound is not None:
                storage_freed += 0.5  # ~0.5MB
                node.raw.sound = None
                logger.debug(f"Deleted audio from node {id(node)}")
            
            # 标记为已遗忘
            if hasattr(node, 'raw'):
                node.raw._data_forgotten = True
                
        except Exception as e:
            logger.error(f"Failed to forget raw data: {e}")
        
        return storage_freed
    
    def _compress_node(self, node: Any) -> float:
        """
        压缩节点数据
        
        Returns:
            float: 释放的存储空间(MB)
        """
        # 简化实现：标记为压缩状态
        if hasattr(node, 'compressed'):
            node.compressed = True
        
        return 0.5  # 假设压缩节省50%空间
    
    def _text_only(self, node: Any) -> float:
        """
        仅保留文本摘要，删除所有其他数据
        
        Returns:
            float: 释放的存储空间(MB)
        """
        storage_freed = self._forget_raw_data(node)
        
        # 删除场景图细节
        if hasattr(node, 'objects'):
            node.objects = []
            storage_freed += 0.1
        
        if hasattr(node, 'relations'):
            node.relations = []
            storage_freed += 0.05
        
        return storage_freed

