"""
ConsolidationAgent - 整合Agent

模拟人类睡眠中的记忆巩固过程，整合相似记忆，提取跨事件模式

灵感来源: 记忆巩固理论 (Memory Consolidation Theory)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from agentscope.agent import AgentBase
from agentscope.message import Msg
from em.em_tree import HigherLevelSummary, GoalBasedSummary, EventBasedSummary


class ConsolidationAgent(AgentBase):
    """
    整合Agent - 记忆巩固与模式提取
    
    职责:
    1. 查找相似的记忆片段
    2. 使用LLM提取跨事件模式
    3. 合并冗余记忆
    4. 强化重要记忆（增加效用值）
    
    运行频率: 每晚一次（模拟睡眠）
    """
    
    def __init__(
        self,
        name: str = "ConsolidationAgent",
        model_config_name: str = "gpt-4o",  # 整合需要强模型
        similarity_threshold: float = 0.85,
        pattern_extraction_enabled: bool = True,
        **kwargs
    ):
        """
        初始化整合Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置（建议用GPT-4）
            similarity_threshold: 记忆相似度阈值
            pattern_extraction_enabled: 是否启用模式提取
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            **kwargs
        )
        
        self.similarity_threshold = similarity_threshold
        self.pattern_extraction_enabled = pattern_extraction_enabled
        
        # 统计信息
        self.stats = {
            "total_consolidations": 0,
            "memories_merged": 0,
            "patterns_extracted": 0,
            "memories_reinforced": 0
        }
        
        logger.info(f"[{self.name}] Initialized with similarity_threshold={similarity_threshold}")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        处理记忆整合请求
        
        输入消息格式:
        {
            "type": "consolidate",
            "memory_tree": HigherLevelSummary,
            "consolidation_mode": "daily" | "weekly"
        }
        
        返回消息格式:
        {
            "type": "consolidation_result",
            "updated_tree": HigherLevelSummary,
            "stats": Dict
        }
        """
        try:
            if x is None or x.content.get("type") != "consolidate":
                return Msg(
                    name=self.name,
                    content={
                        "type": "error",
                        "message": "Invalid message type, expected 'consolidate'"
                    },
                    role="assistant"
                )
            
            memory_tree = x.content.get("memory_tree")
            mode = x.content.get("consolidation_mode", "daily")
            
            if memory_tree is None:
                return Msg(
                    name=self.name,
                    content={"type": "error", "message": "memory_tree is required"},
                    role="assistant"
                )
            
            logger.info(f"[{self.name}] Starting {mode} consolidation cycle")
            
            # 执行整合
            updated_tree, cycle_stats = self._consolidation_cycle(memory_tree, mode)
            
            # 更新统计
            self.stats["total_consolidations"] += 1
            self.stats["memories_merged"] += cycle_stats["merged"]
            self.stats["patterns_extracted"] += cycle_stats["patterns"]
            self.stats["memories_reinforced"] += cycle_stats["reinforced"]
            
            logger.info(
                f"[{self.name}] Consolidation completed: "
                f"merged={cycle_stats['merged']}, "
                f"patterns={cycle_stats['patterns']}, "
                f"reinforced={cycle_stats['reinforced']}"
            )
            
            return Msg(
                name=self.name,
                content={
                    "type": "consolidation_result",
                    "updated_tree": updated_tree,
                    "cycle_stats": cycle_stats,
                    "cumulative_stats": self.stats
                },
                role="assistant"
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] Consolidation failed: {e}")
            return Msg(
                name=self.name,
                content={"type": "error", "message": str(e)},
                role="assistant"
            )
    
    def _consolidation_cycle(
        self, 
        memory_tree: HigherLevelSummary, 
        mode: str
    ) -> tuple:
        """
        执行一次记忆整合周期
        
        Returns:
            (updated_tree, stats): 更新后的树和统计信息
        """
        stats = {
            "merged": 0,
            "patterns": 0,
            "reinforced": 0
        }
        
        # 1. 查找相似记忆组
        similar_groups = self._find_similar_memories(memory_tree)
        logger.info(f"[{self.name}] Found {len(similar_groups)} similar memory groups")
        
        # 2. 提取跨事件模式
        if self.pattern_extraction_enabled and similar_groups:
            for group in similar_groups:
                if len(group) >= 3:  # 至少3个相似记忆才提取模式
                    pattern = self._extract_pattern(group)
                    if pattern:
                        stats["patterns"] += 1
                        # 创建整合节点
                        self._create_consolidated_node(memory_tree, group, pattern)
        
        # 3. 合并冗余记忆
        for group in similar_groups:
            if len(group) >= 2:
                merged = self._merge_memories(group)
                if merged:
                    stats["merged"] += len(group) - 1  # 多个合并为1个
        
        # 4. 强化重要记忆
        reinforced = self._reinforce_important_memories(memory_tree)
        stats["reinforced"] = reinforced
        
        return memory_tree, stats
    
    def _find_similar_memories(self, tree: HigherLevelSummary) -> List[List]:
        """
        查找相似的记忆片段
        
        Returns:
            List[List]: 相似记忆组，例如 [[mem1, mem2, mem3], [mem4, mem5], ...]
        """
        # 收集所有L2/L3节点
        memories = []
        
        def collect_memories(node):
            if isinstance(node, (EventBasedSummary, GoalBasedSummary)):
                memories.append(node)
            
            if hasattr(node, 'children'):
                for child in node.children:
                    collect_memories(child)
            elif hasattr(node, 'events'):
                for event in node.events:
                    collect_memories(event)
        
        collect_memories(tree)
        
        # 简单的相似度计算（基于关键词重叠）
        similar_groups = []
        processed = set()
        
        for i, mem1 in enumerate(memories):
            if i in processed:
                continue
            
            group = [mem1]
            summary1 = mem1.nl_summary.lower()
            words1 = set(summary1.split())
            
            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                if j in processed:
                    continue
                
                summary2 = mem2.nl_summary.lower()
                words2 = set(summary2.split())
                
                # Jaccard相似度
                intersection = len(words1 & words2)
                union = len(words1 | words2)
                similarity = intersection / union if union > 0 else 0
                
                if similarity >= self.similarity_threshold:
                    group.append(mem2)
                    processed.add(j)
            
            if len(group) >= 2:
                similar_groups.append(group)
                processed.add(i)
        
        return similar_groups
    
    def _extract_pattern(self, similar_memories: List) -> Optional[str]:
        """
        使用LLM从相似记忆中提取通用模式
        
        Args:
            similar_memories: 相似记忆列表
            
        Returns:
            str: 提取的模式描述
        """
        if not hasattr(self, 'model') or self.model is None:
            logger.warning("LLM not available, skipping pattern extraction")
            return None
        
        try:
            # 构建prompt
            summaries = [mem.nl_summary for mem in similar_memories]
            prompt = f"""
你是一个记忆整合系统。以下是{len(summaries)}个相似的机器人记忆片段:

{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(summaries))}

请分析这些记忆，提取出它们共同的模式或规律。

要求:
1. 用一句话描述共同模式
2. 突出可泛化的技能或知识
3. 使用中文

模式描述:
"""
            
            # 调用LLM
            response = self.model.generate(prompt)
            pattern = response.strip()
            
            logger.info(f"[{self.name}] Extracted pattern: {pattern}")
            return pattern
            
        except Exception as e:
            logger.error(f"Pattern extraction failed: {e}")
            return None
    
    def _create_consolidated_node(
        self, 
        tree: HigherLevelSummary, 
        memories: List, 
        pattern: str
    ):
        """创建一个整合节点，包含提取的模式"""
        # 在实际实现中，这里应该创建新的HigherLevelSummary节点
        # 简化版：只在第一个记忆上添加标记
        if memories:
            first_mem = memories[0]
            if not hasattr(first_mem, 'consolidated_pattern'):
                first_mem.consolidated_pattern = pattern
                first_mem.consolidated_from = [id(m) for m in memories]
                logger.debug(f"Created consolidated node with pattern: {pattern}")
    
    def _merge_memories(self, similar_memories: List) -> bool:
        """
        合并冗余记忆
        
        Args:
            similar_memories: 相似记忆列表
            
        Returns:
            bool: 是否成功合并
        """
        if len(similar_memories) < 2:
            return False
        
        try:
            # 简化实现：标记后续记忆为"已合并"
            primary = similar_memories[0]
            
            for mem in similar_memories[1:]:
                mem._merged_into = id(primary)
                logger.debug(f"Merged memory {id(mem)} into {id(primary)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Memory merge failed: {e}")
            return False
    
    def _reinforce_important_memories(self, tree: HigherLevelSummary) -> int:
        """
        强化重要记忆（增加效用值）
        
        强化条件:
        1. 被频繁访问的记忆
        2. 被整合的记忆（说明具有通用性）
        3. 包含异常事件的记忆
        
        Returns:
            int: 强化的记忆数量
        """
        reinforced_count = 0
        
        def reinforce_node(node):
            nonlocal reinforced_count
            
            # 条件1: 高访问频率
            if hasattr(node, 'access_count') and node.access_count > 10:
                if hasattr(node, 'utility_score'):
                    node.utility_score = min(node.utility_score + 0.2, 1.0)
                    reinforced_count += 1
            
            # 条件2: 被整合的记忆
            if hasattr(node, 'consolidated_pattern'):
                if hasattr(node, 'utility_score'):
                    node.utility_score = min(node.utility_score + 0.15, 1.0)
                    reinforced_count += 1
            
            # 条件3: 包含异常关键词
            if hasattr(node, 'nl_summary'):
                summary = node.nl_summary.lower()
                if any(kw in summary for kw in ['失败', 'error', '异常', '碰撞', '摔倒']):
                    if hasattr(node, 'utility_score'):
                        node.utility_score = min(node.utility_score + 0.3, 1.0)
                        reinforced_count += 1
            
            # 递归处理子节点
            if hasattr(node, 'children'):
                for child in node.children:
                    reinforce_node(child)
            elif hasattr(node, 'events'):
                for event in node.events:
                    reinforce_node(event)
        
        reinforce_node(tree)
        return reinforced_count

