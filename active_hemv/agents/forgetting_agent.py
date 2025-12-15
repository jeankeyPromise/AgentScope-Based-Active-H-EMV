"""
ForgettingAgent - 遗忘Agent

模拟人类的遗忘过程，主动删除低效用记忆，压缩存储空间

灵感来源: Ebbinghaus遗忘曲线
"""

from typing import Dict, Any, Optional, List
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
            
            elif action == "merge_or_delete":
                # 合并或删除节点（需要特殊处理高层节点）
                storage_freed, nodes_deleted = self._merge_or_delete_node(
                    node, memory_tree, all_nodes
                )
                stats["forgotten"] += nodes_deleted
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
    
    def _merge_or_delete_node(
        self,
        node: Any,
        memory_tree: HigherLevelSummary,
        all_nodes: List[Any]
    ) -> tuple:
        """
        合并或删除低效用节点
        
        策略:
        1. 如果是叶子节点（L0/L1/L2），直接删除
        2. 如果是高层节点（L3+），需要特殊处理:
           - 先检查子节点的效用值
           - 如果子节点也低效用，可以删除整个子树
           - 如果子节点高效用，需要将子节点提升到父节点
        
        Returns:
            (storage_freed_mb, nodes_deleted_count): 释放的存储空间和删除的节点数
        """
        storage_freed = 0.0
        nodes_deleted = 0
        
        # 判断节点层级
        node_level = self._get_node_level(node)
        
        # 如果是叶子节点（L0/L1/L2），可以直接删除
        if node_level <= 2:
            storage_freed = self._text_only(node)  # 先清理数据
            nodes_deleted = 1
            logger.info(f"Deleted leaf node (L{node_level}): {getattr(node, 'nl_summary', '')[:50]}")
            return storage_freed, nodes_deleted
        
        # 如果是高层节点（L3+），需要检查子节点
        child_nodes = self._get_child_nodes(node)
        
        if not child_nodes:
            # 没有子节点，直接删除
            storage_freed = self._text_only(node)
            nodes_deleted = 1
            logger.info(f"Deleted empty high-level node (L{node_level})")
            return storage_freed, nodes_deleted
        
        # 检查子节点的效用值
        high_utility_children = []
        low_utility_children = []
        
        for child in child_nodes:
            child_dict = self._node_to_dict(child)
            child_utility = child_dict.get("utility_score", 0.5)
            
            if child_utility >= self.forgetting_policy.THRESHOLD_MED:
                high_utility_children.append(child)
            else:
                low_utility_children.append(child)
        
        # 策略决策
        if len(high_utility_children) == 0:
            # 所有子节点都低效用，可以删除整个子树
            storage_freed = self._delete_subtree(node)
            nodes_deleted = 1 + len(child_nodes)  # 包括当前节点和所有子节点
            logger.info(
                f"Deleted entire subtree (L{node_level}): "
                f"{len(child_nodes)} children all have low utility"
            )
            
        elif len(high_utility_children) <= 2:
            # 只有1-2个子节点高效用，可以合并到父节点
            storage_freed = self._merge_children_to_parent(node, high_utility_children)
            nodes_deleted = len(low_utility_children)  # 只删除低效用的子节点
            logger.info(
                f"Merged {len(high_utility_children)} high-utility children, "
                f"deleted {len(low_utility_children)} low-utility children"
            )
            
        else:
            # 多个子节点高效用，不应该删除父节点
            # 只删除低效用的子节点
            for child in low_utility_children:
                child_storage, _ = self._merge_or_delete_node(child, memory_tree, all_nodes)
                storage_freed += child_storage
                nodes_deleted += 1
            
            # 标记父节点为"已压缩"（保留但标记）
            if hasattr(node, 'compressed'):
                node.compressed = True
            logger.info(
                f"Preserved high-level node (L{node_level}) with {len(high_utility_children)} "
                f"high-utility children, deleted {len(low_utility_children)} low-utility children"
            )
        
        return storage_freed, nodes_deleted
    
    def _get_node_level(self, node: Any) -> int:
        """获取节点的层级"""
        from em.em_tree import (
            RawDataInstant, SceneGraphInstant, 
            EventBasedSummary, GoalBasedSummary, HigherLevelSummary
        )
        
        if isinstance(node, RawDataInstant):
            return 0
        elif isinstance(node, SceneGraphInstant):
            return 1
        elif isinstance(node, EventBasedSummary):
            return 2
        elif isinstance(node, GoalBasedSummary):
            return 3
        elif isinstance(node, HigherLevelSummary):
            # 递归计算最高层级
            if hasattr(node, 'previous_summaries') and node.previous_summaries:
                max_child_level = max(
                    self._get_node_level(child) 
                    for child in node.previous_summaries
                )
                return max_child_level + 1
            return 3
        else:
            return 2  # 默认值
    
    def _get_child_nodes(self, node: Any) -> List[Any]:
        """获取节点的所有子节点"""
        children = []
        
        if hasattr(node, 'previous_summaries'):
            children.extend(node.previous_summaries)
        elif hasattr(node, 'events'):
            children.extend(node.events)
        elif hasattr(node, 'scenes'):
            children.extend(node.scenes)
        
        return children
    
    def _delete_subtree(self, node: Any) -> float:
        """删除整个子树（递归删除所有子节点）"""
        storage_freed = 0.0
        
        # 递归删除子节点
        child_nodes = self._get_child_nodes(node)
        for child in child_nodes:
            storage_freed += self._delete_subtree(child)
        
        # 删除当前节点数据
        storage_freed += self._text_only(node)
        
        return storage_freed
    
    def _merge_children_to_parent(
        self,
        parent_node: Any,
        high_utility_children: List[Any]
    ) -> float:
        """
        将高效用的子节点合并到父节点
        
        策略: 将子节点的摘要合并到父节点的摘要中
        """
        storage_freed = 0.0
        
        # 删除低效用的子节点
        all_children = self._get_child_nodes(parent_node)
        low_utility_children = [
            child for child in all_children 
            if child not in high_utility_children
        ]
        
        for child in low_utility_children:
            storage_freed += self._delete_subtree(child)
        
        # 更新父节点的子节点列表
        if hasattr(parent_node, 'previous_summaries'):
            parent_node.previous_summaries = high_utility_children
        elif hasattr(parent_node, 'events'):
            parent_node.events = high_utility_children
        
        # 更新父节点摘要（合并子节点摘要）
        if hasattr(parent_node, 'nl_summary') and high_utility_children:
            child_summaries = [
                getattr(child, 'nl_summary', '') 
                for child in high_utility_children
            ]
            merged_summary = f"[合并] {parent_node.nl_summary}\n" + "\n".join(
                f"  - {s[:50]}..." if len(s) > 50 else f"  - {s}"
                for s in child_summaries
            )
            parent_node.nl_summary = merged_summary
        
        return storage_freed

