"""
记忆编辑引擎 - 实现追溯性记忆修正与级联更新
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger


class EditingEngine:
    """
    记忆编辑引擎 - 处理人机回环的记忆纠错
    
    核心功能:
    1. 错误源定位
    2. 重感知/重新处理
    3. 级联更新父节点
    4. 编辑历史记录
    """
    
    def __init__(self):
        """初始化编辑引擎"""
        self.edit_log: List[Dict[str, Any]] = []
        logger.info("EditingEngine initialized")
    
    def locate_error_source(
        self,
        retrieved_nodes: List[str],
        original_answer: str,
        user_correction: str,
        storage_backends: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        定位导致错误回答的源节点
        
        策略:
        1. 从检索到的节点开始
        2. 追溯到L1/L0层 (最可能出错的地方)
        3. 语义匹配找出最可疑节点
        
        Args:
            retrieved_nodes: 检索返回的节点ID列表
            original_answer: 系统的原始回答
            user_correction: 用户的纠正
            storage_backends: 存储后端
            
        Returns:
            Optional[Dict]: 错误源节点,如果找不到返回None
        """
        logger.info(f"Locating error source among {len(retrieved_nodes)} nodes")
        
        vector_store = storage_backends.get("vector")
        graph_store = storage_backends.get("graph")
        
        if not vector_store:
            logger.warning("Vector store not available")
            return None
        
        try:
            # 1. 获取所有候选节点
            candidate_nodes = []
            for node_id in retrieved_nodes:
                node = vector_store.get_node(node_id)
                if node:
                    candidate_nodes.append(node)
            
            if not candidate_nodes:
                logger.warning("No candidate nodes found")
                return None
            
            # 2. 如果候选节点是L2或更高层,追溯到L1
            l1_candidates = []
            if graph_store:
                for node in candidate_nodes:
                    if node["level"] in ["L2", "L3", "L4+"]:
                        # 使用图数据库追溯
                        try:
                            l1_children = graph_store.get_descendants(node["node_id"], target_level="L1")
                            l1_candidates.extend(l1_children)
                        except:
                            pass
                    else:
                        l1_candidates.append(node)
            else:
                l1_candidates = candidate_nodes
            
            if not l1_candidates:
                l1_candidates = candidate_nodes
            
            # 3. 语义匹配找出最可疑的节点
            #    (包含原始错误信息的节点)
            error_node = self._semantic_match_error(
                l1_candidates,
                original_answer,
                user_correction
            )
            
            if error_node:
                logger.info(f"Located error source: {error_node['node_id']} (level: {error_node['level']})")
            else:
                logger.warning("Could not locate error source")
            
            return error_node
            
        except Exception as e:
            logger.error(f"Error source location failed: {e}")
            return None
    
    def _semantic_match_error(
        self,
        candidates: List[Dict],
        original_answer: str,
        user_correction: str
    ) -> Optional[Dict]:
        """
        语义匹配找出最可能的错误节点
        
        策略: 找出与原始回答最相关,但与用户纠正冲突的节点
        """
        # 提取关键词
        original_keywords = set(original_answer.lower().split())
        correction_keywords = set(user_correction.lower().split())
        
        best_match = None
        best_score = -1
        
        for candidate in candidates:
            summary = candidate.get("nl_summary", "").lower()
            summary_keywords = set(summary.split())
            
            # 与原始回答的重叠度
            original_overlap = len(original_keywords & summary_keywords)
            
            # 与纠正的冲突度 (重叠应该低)
            correction_overlap = len(correction_keywords & summary_keywords)
            
            # 评分: 高原始重叠 + 低纠正重叠 = 最可疑
            score = original_overlap - correction_overlap * 0.5
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match if best_score > 0 else None
    
    def reperceive(
        self,
        error_node: Dict[str, Any],
        user_correction: str,
        storage_backends: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        重新感知/处理错误节点
        
        Args:
            error_node: 错误源节点
            user_correction: 用户纠正信息
            storage_backends: 存储后端
            
        Returns:
            Dict: {"success": bool, "new_summary": str, "reason": str (if failed)}
        """
        logger.info(f"Re-perceiving node {error_node['node_id']}")
        
        object_store = storage_backends.get("object")
        
        # 检查是否还有原始数据
        has_raw_data = error_node.get("has_raw_data", True)
        if not has_raw_data:
            logger.warning("Original data has been forgotten, cannot re-perceive")
            return {
                "success": False,
                "reason": "原始数据已被遗忘,无法重新感知"
            }
        
        # 如果是L1节点,应该有对应的L0图像
        if error_node["level"] == "L1" and object_store:
            try:
                # 加载原始图像
                # image = object_store.get_image(error_node["l0_reference"])
                
                # 使用更强的VLM重新处理
                # 这里应该调用GPT-4o或其他强大的VLM
                # new_perception = vlm.process(image, prompt=user_correction)
                
                # 占位符: 基于用户纠正生成新的摘要
                new_summary = f"根据用户纠正更新: {user_correction}"
                
                logger.info("Re-perception successful")
                return {
                    "success": True,
                    "new_summary": new_summary
                }
                
            except Exception as e:
                logger.error(f"Re-perception failed: {e}")
                return {
                    "success": False,
                    "reason": f"重新感知失败: {str(e)}"
                }
        
        # 如果是更高层节点,直接更新摘要
        new_summary = f"[已纠正] {user_correction}"
        return {
            "success": True,
            "new_summary": new_summary
        }
    
    def propagate_update_upward(
        self,
        corrected_node: Dict[str, Any],
        storage_backends: Dict[str, Any]
    ) -> List[str]:
        """
        级联向上更新所有受影响的父节点
        
        Args:
            corrected_node: 已纠正的节点
            storage_backends: 存储后端
            
        Returns:
            List[str]: 受影响的父节点ID列表
        """
        logger.info(f"Propagating update from {corrected_node['node_id']}")
        
        graph_store = storage_backends.get("graph")
        vector_store = storage_backends.get("vector")
        
        if not graph_store:
            logger.warning("Graph store not available, cannot propagate")
            return []
        
        try:
            # 1. 查找所有祖先节点
            ancestors = graph_store.get_ancestors(corrected_node["node_id"])
            
            logger.info(f"Found {len(ancestors)} ancestor nodes to update")
            
            # 2. 从最近的父节点开始逐层更新
            affected_nodes = []
            for ancestor_id in ancestors:
                ancestor = vector_store.get_node(ancestor_id)
                if not ancestor:
                    continue
                
                # 重新生成该节点的摘要
                # (应该基于其子节点重新调用LLM)
                # new_summary = self._regenerate_summary(ancestor, vector_store, graph_store)
                
                # 占位符
                new_summary = f"[更新] {ancestor.get('nl_summary', '')}"
                
                # 更新节点
                if vector_store:
                    vector_store.update(ancestor_id, {
                        "nl_summary": new_summary,
                        "last_edited": datetime.now().isoformat()
                    })
                
                affected_nodes.append(ancestor_id)
                logger.debug(f"Updated ancestor {ancestor_id}")
            
            return affected_nodes
            
        except Exception as e:
            logger.error(f"Update propagation failed: {e}")
            return []
    
    def log_edit(self, edit_info: Dict[str, Any]):
        """
        记录编辑历史
        
        Args:
            edit_info: 编辑信息 {timestamp, error_node, correction, affected_nodes}
        """
        self.edit_log.append(edit_info)
        logger.info(f"Edit logged: {edit_info.get('error_node')} -> {len(edit_info.get('affected_nodes', []))} nodes affected")
    
    def get_edit_history(self, node_id: Optional[str] = None) -> List[Dict]:
        """
        获取编辑历史
        
        Args:
            node_id: 可选,仅返回特定节点的编辑历史
            
        Returns:
            List[Dict]: 编辑记录列表
        """
        if node_id:
            return [e for e in self.edit_log if e.get("error_node") == node_id]
        return self.edit_log

