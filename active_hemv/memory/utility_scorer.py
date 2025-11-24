"""
效用评分器 - 实现效用函数 U(n,t) = α·A(n,t) + β·S(n) + γ·I(n)

核心创新: 基于效用理论的自适应遗忘
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
from loguru import logger


class UtilityScorer:
    """
    节点效用评分器
    
    效用函数: U(n,t) = α·A(n,t) + β·S(n) + γ·I(n)
    
    其中:
    - A(n,t): 访问热度 (时间衰减的访问频率)
    - S(n): 语义显著性 (LLM评估事件重要性)
    - I(n): 信息密度 (节点独特性)
    - α, β, γ: 权重参数 (默认 0.5, 0.3, 0.2)
    """
    
    def __init__(
        self,
        alpha: float = 0.5,  # 访问热度权重
        beta: float = 0.3,   # 语义显著性权重
        gamma: float = 0.2,  # 信息密度权重
        lambda_decay: float = 0.01  # 时间衰减系数
    ):
        """
        初始化效用评分器
        
        Args:
            alpha: 访问热度权重
            beta: 语义显著性权重
            gamma: 信息密度权重
            lambda_decay: 时间衰减系数 (越大衰减越快)
        """
        # 权重归一化
        total = alpha + beta + gamma
        self.alpha = alpha / total
        self.beta = beta / total
        self.gamma = gamma / total
        
        self.lambda_decay = lambda_decay
        
        logger.info(f"UtilityScorer initialized with α={self.alpha:.2f}, β={self.beta:.2f}, γ={self.gamma:.2f}")
    
    def compute(
        self,
        node: Dict[str, Any],
        current_time: datetime,
        all_nodes: List[Dict[str, Any]],
        llm_model: Optional[Any] = None
    ) -> float:
        """
        计算节点的效用值
        
        Args:
            node: 节点数据
            current_time: 当前时间
            all_nodes: 所有节点列表 (用于计算信息密度)
            llm_model: LLM模型 (用于语义显著性评估)
            
        Returns:
            float: 效用分数 [0, 1]
        """
        try:
            # 1. 访问热度 A(n,t)
            A = self._compute_access_frequency(node, current_time)
            
            # 2. 语义显著性 S(n)
            S = self._compute_semantic_salience(node, llm_model)
            
            # 3. 信息密度 I(n)
            I = self._compute_information_density(node, all_nodes)
            
            # 4. 综合效用
            utility = self.alpha * A + self.beta * S + self.gamma * I
            
            logger.debug(f"Node {node.get('node_id')}: U={utility:.3f} (A={A:.3f}, S={S:.3f}, I={I:.3f})")
            
            return np.clip(utility, 0.0, 1.0)
            
        except Exception as e:
            logger.error(f"Utility computation failed: {e}")
            return 0.5  # 默认中等效用
    
    def _compute_access_frequency(self, node: Dict, current_time: datetime) -> float:
        """
        计算访问热度 A(n,t) - 带时间衰减的访问频率
        
        公式: A = Σ exp(-λ * Δt_i) / (N + 1)
        
        其中:
        - Δt_i: 第i次访问距今的天数
        - λ: 衰减系数
        - N: 总访问次数
        """
        access_count = node.get("access_count", 0)
        last_accessed = node.get("last_accessed", 0)
        
        if access_count == 0:
            return 0.1  # 从未访问,低但非零
        
        # 计算最后一次访问距今的天数
        if last_accessed == 0:
            # 如果没有记录,使用节点创建时间估计
            created_at = datetime.fromtimestamp(node.get("timestamp_start", 0))
            delta_days = (current_time - created_at).days
        else:
            last_access_time = datetime.fromtimestamp(last_accessed)
            delta_days = (current_time - last_access_time).days
        
        # 时间衰减
        decay = np.exp(-self.lambda_decay * delta_days)
        
        # 归一化访问频率 (假设最大访问次数为100)
        normalized_freq = min(access_count / 100.0, 1.0)
        
        return decay * normalized_freq
    
    def _compute_semantic_salience(
        self,
        node: Dict,
        llm_model: Optional[Any] = None
    ) -> float:
        """
        计算语义显著性 S(n) - LLM评估事件重要性
        
        评分标准:
        - 异常事件 (失败、错误): 0.8-1.0
        - 重要任务节点: 0.6-0.8
        - 常规操作: 0.3-0.5
        - 重复性动作: 0.0-0.3
        """
        # 如果已经有缓存的显著性分数
        if "salience_score" in node:
            return node["salience_score"]
        
        nl_summary = node.get("nl_summary", "")
        
        # 基于关键词的启发式评分 (如果没有LLM)
        if not llm_model:
            return self._heuristic_salience(nl_summary)
        
        # 使用LLM评分
        try:
            prompt = f"""
            请对以下机器人记忆片段的显著性打分(0-1):
            
            "{nl_summary}"
            
            评分标准:
            - 异常/错误事件: 0.8-1.0
            - 重要任务: 0.6-0.8
            - 常规操作: 0.3-0.5
            - 重复性动作: 0.0-0.3
            
            请只返回一个0-1之间的浮点数,不要解释。
            """
            
            # 调用LLM
            # response = llm_model.generate(prompt)
            # score = float(response.strip())
            
            # 占位符
            score = self._heuristic_salience(nl_summary)
            
            return np.clip(score, 0.0, 1.0)
            
        except Exception as e:
            logger.error(f"LLM salience scoring failed: {e}")
            return self._heuristic_salience(nl_summary)
    
    def _heuristic_salience(self, text: str) -> float:
        """基于关键词的启发式显著性评分"""
        text_lower = text.lower()
        
        # 高显著性关键词
        high_keywords = ["failed", "error", "失败", "错误", "异常", "摔倒", "碰撞"]
        if any(kw in text_lower for kw in high_keywords):
            return 0.9
        
        # 中高显著性关键词
        medium_high_keywords = ["completed", "完成", "达成", "成功", "first time", "第一次"]
        if any(kw in text_lower for kw in medium_high_keywords):
            return 0.7
        
        # 中等显著性关键词
        medium_keywords = ["grasp", "抓取", "移动", "放置", "pick", "place"]
        if any(kw in text_lower for kw in medium_keywords):
            return 0.5
        
        # 低显著性 (默认)
        return 0.3
    
    def _compute_information_density(
        self,
        node: Dict,
        all_nodes: List[Dict]
    ) -> float:
        """
        计算信息密度 I(n) - 节点的独特性
        
        公式: I = 1 - max_similarity(node, other_nodes)
        
        节点与历史越相似,信息密度越低
        """
        if not all_nodes or len(all_nodes) <= 1:
            return 1.0  # 唯一节点,高密度
        
        node_summary = node.get("nl_summary", "")
        node_id = node.get("node_id")
        
        # 计算与其他节点的相似度 (简化版: 基于词汇重叠)
        similarities = []
        for other in all_nodes:
            if other.get("node_id") == node_id:
                continue
            
            other_summary = other.get("nl_summary", "")
            sim = self._text_similarity(node_summary, other_summary)
            similarities.append(sim)
        
        if not similarities:
            return 1.0
        
        # 信息密度 = 1 - 最大相似度
        max_sim = max(similarities)
        return 1.0 - max_sim
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        简化的文本相似度计算 (基于词汇重叠)
        
        更好的实现应该使用embedding余弦相似度
        """
        if not text1 or not text2:
            return 0.0
        
        # 分词 (简化版)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        # Jaccard相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 0.0
        
        return intersection / union

