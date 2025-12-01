"""
CorrectionAgent - 修正Agent

处理人机回环的记忆纠错，当用户指出记忆错误时，定位并修正

灵感来源: 认知失调理论 (Cognitive Dissonance Theory)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from agentscope.agent import AgentBase
from agentscope.message import Msg
from em.em_tree import HigherLevelSummary, AnyTreeNode


class CorrectionAgent(AgentBase):
    """
    修正Agent - 处理记忆纠错
    
    职责:
    1. 接收用户纠错信息
    2. 定位错误的记忆节点
    3. 使用LLM生成修正后的描述
    4. 级联更新父节点
    5. 记录修正历史
    
    运行频率: 按需（用户纠错时）
    """
    
    def __init__(
        self,
        name: str = "CorrectionAgent",
        model_config_name: str = "gpt-4o",  # 修正需要强模型
        max_correction_history: int = 10,
        **kwargs
    ):
        """
        初始化修正Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置
            max_correction_history: 每个节点保留的最大修正历史数
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            **kwargs
        )
        
        self.max_correction_history = max_correction_history
        
        # 全局修正历史
        self.correction_log = []
        
        # 统计信息
        self.stats = {
            "total_corrections": 0,
            "successful_corrections": 0,
            "failed_corrections": 0,
            "nodes_updated": 0
        }
        
        logger.info(f"[{self.name}] Initialized")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        处理记忆修正请求
        
        输入消息格式:
        {
            "type": "correction",
            "memory_tree": HigherLevelSummary,
            "query": str,  # 原始查询
            "system_answer": str,  # 系统的错误回答
            "user_correction": str  # 用户的纠正
        }
        
        返回消息格式:
        {
            "type": "correction_result",
            "updated_tree": HigherLevelSummary,
            "success": bool,
            "corrected_node_id": str,
            "nodes_updated": int
        }
        """
        try:
            if x is None or x.content.get("type") != "correction":
                return Msg(
                    name=self.name,
                    content={
                        "type": "error",
                        "message": "Invalid message type, expected 'correction'"
                    },
                    role="assistant"
                )
            
            memory_tree = x.content.get("memory_tree")
            query = x.content.get("query")
            system_answer = x.content.get("system_answer", "")
            user_correction = x.content.get("user_correction")
            
            if not all([memory_tree, query, user_correction]):
                return Msg(
                    name=self.name,
                    content={
                        "type": "error",
                        "message": "memory_tree, query, and user_correction are required"
                    },
                    role="assistant"
                )
            
            logger.info(f"[{self.name}] Processing correction for query: '{query}'")
            logger.info(f"[{self.name}] User correction: '{user_correction}'")
            
            # 执行修正
            result = self._correct_memory(
                memory_tree, 
                query, 
                system_answer, 
                user_correction
            )
            
            # 更新统计
            self.stats["total_corrections"] += 1
            if result["success"]:
                self.stats["successful_corrections"] += 1
                self.stats["nodes_updated"] += result["nodes_updated"]
            else:
                self.stats["failed_corrections"] += 1
            
            logger.info(
                f"[{self.name}] Correction {'successful' if result['success'] else 'failed'}: "
                f"updated {result['nodes_updated']} nodes"
            )
            
            return Msg(
                name=self.name,
                content={
                    "type": "correction_result",
                    "updated_tree": memory_tree,
                    **result,
                    "cumulative_stats": self.stats
                },
                role="assistant"
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] Correction failed: {e}")
            self.stats["failed_corrections"] += 1
            return Msg(
                name=self.name,
                content={"type": "error", "message": str(e)},
                role="assistant"
            )
    
    def _correct_memory(
        self,
        memory_tree: HigherLevelSummary,
        query: str,
        system_answer: str,
        user_correction: str
    ) -> Dict[str, Any]:
        """
        执行记忆修正
        
        Returns:
            Dict: {
                "success": bool,
                "corrected_node_id": str,
                "nodes_updated": int,
                "reason": str (if failed)
            }
        """
        # 1. 定位错误节点
        error_node = self._locate_error_node(memory_tree, query, system_answer, user_correction)
        
        if error_node is None:
            return {
                "success": False,
                "nodes_updated": 0,
                "reason": "无法定位错误源节点"
            }
        
        logger.info(f"[{self.name}] Located error node: {id(error_node)}")
        
        # 2. 生成修正后的描述
        corrected_summary = self._generate_corrected_summary(
            original_summary=getattr(error_node, 'nl_summary', ''),
            user_correction=user_correction
        )
        
        if not corrected_summary:
            return {
                "success": False,
                "corrected_node_id": str(id(error_node)),
                "nodes_updated": 0,
                "reason": "LLM生成修正描述失败"
            }
        
        # 3. 更新错误节点
        original_summary = getattr(error_node, 'nl_summary', '')
        error_node.nl_summary = corrected_summary
        
        # 添加修正标记和历史
        if not hasattr(error_node, 'correction_history'):
            error_node.correction_history = []
        
        error_node.correction_history.append({
            "timestamp": datetime.now(),
            "original": original_summary,
            "correction": user_correction,
            "corrected_summary": corrected_summary
        })
        
        # 限制历史长度
        if len(error_node.correction_history) > self.max_correction_history:
            error_node.correction_history = error_node.correction_history[-self.max_correction_history:]
        
        error_node.corrected = True
        
        # 4. 级联更新父节点
        affected_nodes = self._propagate_update(memory_tree, error_node)
        
        # 5. 记录到全局日志
        self.correction_log.append({
            "timestamp": datetime.now(),
            "query": query,
            "correction": user_correction,
            "node_id": str(id(error_node)),
            "nodes_affected": len(affected_nodes)
        })
        
        return {
            "success": True,
            "corrected_node_id": str(id(error_node)),
            "nodes_updated": 1 + len(affected_nodes),
            "affected_node_ids": [str(id(n)) for n in affected_nodes]
        }
    
    def _locate_error_node(
        self,
        tree: HigherLevelSummary,
        query: str,
        system_answer: str,
        user_correction: str
    ) -> Optional[Any]:
        """
        定位包含错误信息的节点
        
        策略:
        1. 查找与query最相关的节点
        2. 检查节点内容是否包含system_answer中的错误信息
        3. 返回最可疑的节点
        """
        # 收集所有节点
        all_nodes = []
        
        def collect(node):
            all_nodes.append(node)
            if hasattr(node, 'children'):
                for child in node.children:
                    collect(child)
            elif hasattr(node, 'events'):
                for event in node.events:
                    collect(event)
            elif hasattr(node, 'scenes'):
                for scene in node.scenes:
                    all_nodes.append(scene)
        
        collect(tree)
        
        # 简单的关键词匹配
        query_words = set(query.lower().split())
        answer_words = set(system_answer.lower().split())
        correction_words = set(user_correction.lower().split())
        
        best_match = None
        best_score = -1
        
        for node in all_nodes:
            if not hasattr(node, 'nl_summary'):
                continue
            
            summary = node.nl_summary.lower()
            summary_words = set(summary.split())
            
            # 计算相似度
            query_overlap = len(query_words & summary_words)
            answer_overlap = len(answer_words & summary_words)
            correction_conflict = len(correction_words & summary_words)
            
            # 评分：与query相关 + 与错误answer相关 - 与correction冲突
            score = query_overlap * 2 + answer_overlap * 3 - correction_conflict * 2
            
            if score > best_score:
                best_score = score
                best_match = node
        
        if best_score > 0:
            return best_match
        
        # 如果没找到，返回第一个叶子节点
        return all_nodes[0] if all_nodes else None
    
    def _generate_corrected_summary(
        self,
        original_summary: str,
        user_correction: str
    ) -> Optional[str]:
        """
        使用LLM生成修正后的摘要
        
        Args:
            original_summary: 原始错误摘要
            user_correction: 用户纠正信息
            
        Returns:
            str: 修正后的摘要
        """
        if not hasattr(self, 'model') or self.model is None:
            logger.warning("LLM not available, using simple replacement")
            # 简单替换
            return f"[已修正] {user_correction}"
        
        try:
            prompt = f"""
你是一个记忆修正系统。用户指出了记忆中的错误，请生成修正后的描述。

原始记忆描述:
{original_summary}

用户纠正:
{user_correction}

请生成修正后的记忆描述，要求:
1. 保留原描述中的正确部分
2. 根据用户纠正修改错误部分
3. 保持描述的完整性和流畅性
4. 使用中文
5. 不要添加"修正"、"更新"等元信息

修正后的描述:
"""
            
            response = self.model.generate(prompt)
            corrected = response.strip()
            
            logger.info(f"[{self.name}] Generated corrected summary")
            return corrected
            
        except Exception as e:
            logger.error(f"LLM correction failed: {e}")
            return f"[已修正] {user_correction}"
    
    def _propagate_update(
        self,
        tree: HigherLevelSummary,
        corrected_node: Any
    ) -> List[Any]:
        """
        级联更新父节点
        
        策略:
        1. 找到corrected_node的所有祖先
        2. 从下往上逐层更新摘要
        
        Returns:
            List[Any]: 受影响的父节点列表
        """
        affected_nodes = []
        
        # 简化实现：查找包含corrected_node的父节点
        def find_and_update_parents(node, target):
            nonlocal affected_nodes
            
            is_parent = False
            
            # 检查children
            if hasattr(node, 'children'):
                for child in node.children:
                    if child is target or find_and_update_parents(child, target):
                        is_parent = True
            
            # 检查events
            if hasattr(node, 'events'):
                for event in node.events:
                    if event is target or find_and_update_parents(event, target):
                        is_parent = True
            
            # 检查scenes
            if hasattr(node, 'scenes'):
                for scene in node.scenes:
                    if scene is target:
                        is_parent = True
            
            # 如果是父节点，更新其摘要
            if is_parent and hasattr(node, 'nl_summary'):
                # 简化：添加标记
                if not node.nl_summary.startswith("[已更新]"):
                    node.nl_summary = f"[已更新] {node.nl_summary}"
                affected_nodes.append(node)
                logger.debug(f"Updated parent node {id(node)}")
            
            return is_parent
        
        find_and_update_parents(tree, corrected_node)
        
        return affected_nodes
    
    def get_correction_history(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的修正历史
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            List[Dict]: 修正历史记录
        """
        return self.correction_log[-limit:]

