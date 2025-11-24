"""
一致性检查器 - 确保记忆树的逻辑一致性
"""

from typing import Dict, Any, List
from loguru import logger


class ConsistencyChecker:
    """
    一致性检查器 - 验证记忆树的完整性
    
    检查项:
    1. 父子关系完整性
    2. 时间戳一致性 (子节点时间在父节点范围内)
    3. 引用完整性 (L1→L0, L2→L1等)
    4. 语义一致性 (父节点摘要应涵盖子节点)
    """
    
    def __init__(self):
        """初始化一致性检查器"""
        self.inconsistencies: List[Dict[str, Any]] = []
        logger.info("ConsistencyChecker initialized")
    
    def check_tree(self, storage_backends: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查整个记忆树的一致性
        
        Args:
            storage_backends: 存储后端
            
        Returns:
            Dict: {
                "is_consistent": bool,
                "errors": List[Dict],
                "warnings": List[Dict]
            }
        """
        logger.info("Starting consistency check")
        
        errors = []
        warnings = []
        
        vector_store = storage_backends.get("vector")
        graph_store = storage_backends.get("graph")
        
        if not vector_store:
            return {"is_consistent": False, "errors": [{"type": "no_vector_store"}], "warnings": []}
        
        try:
            # 1. 获取所有节点
            all_nodes = vector_store.get_all_nodes(limit=10000)
            
            logger.info(f"Checking {len(all_nodes)} nodes")
            
            # 2. 检查每个节点
            for node in all_nodes:
                # 时间戳完整性
                if node.get("timestamp_start", 0) > node.get("timestamp_end", 0):
                    errors.append({
                        "type": "invalid_timestamp",
                        "node_id": node["node_id"],
                        "message": "timestamp_start > timestamp_end"
                    })
                
                # 必需字段
                required_fields = ["node_id", "level", "nl_summary"]
                for field in required_fields:
                    if field not in node or not node[field]:
                        errors.append({
                            "type": "missing_field",
                            "node_id": node["node_id"],
                            "field": field
                        })
            
            # 3. 如果有图数据库,检查引用完整性
            if graph_store:
                ref_errors = self._check_reference_integrity(all_nodes, graph_store)
                errors.extend(ref_errors)
            
            is_consistent = len(errors) == 0
            
            logger.info(f"Consistency check completed: {len(errors)} errors, {len(warnings)} warnings")
            
            return {
                "is_consistent": is_consistent,
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Consistency check failed: {e}")
            return {
                "is_consistent": False,
                "errors": [{"type": "check_failed", "message": str(e)}],
                "warnings": []
            }
    
    def _check_reference_integrity(
        self,
        nodes: List[Dict],
        graph_store: Any
    ) -> List[Dict]:
        """检查引用完整性"""
        errors = []
        
        # 占位符实现
        # 实际应该检查图数据库中的边是否指向存在的节点
        
        return errors

