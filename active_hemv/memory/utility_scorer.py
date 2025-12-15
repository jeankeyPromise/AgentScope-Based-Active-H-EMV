"""
效用评分器 - 实现效用函数 U(n,t) = α·A(n,t) + β·S(n) + γ·I(n)

核心创新: 基于效用理论的自适应遗忘
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer


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
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
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
            # 注意: llm_model 是从 ForgettingAgent 传入的 self.model
            # AgentScope 的 model 对象有 generate() 方法
            if llm_model is not None:
                response = llm_model.generate(prompt)
                # 尝试解析返回的分数
                try:
                    # 提取数字（处理可能的格式：0.85, 0.85分, 分数:0.85等）
                    import re
                    match = re.search(r'0?\.\d+|1\.0', response.strip())
                    if match:
                        score = float(match.group())
                    else:
                        # 如果无法解析，使用启发式方法
                        logger.warning(f"无法解析LLM返回的分数: {response}, 使用启发式方法")
                        score = self._heuristic_salience(nl_summary)
                except ValueError as e:
                    logger.error(f"解析LLM返回的分数失败: {e}, 使用启发式方法")
                    score = self._heuristic_salience(nl_summary)
            else:
                # 如果没有LLM，使用启发式方法
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
            return 1.0

        # 获取当前向量
        current_vec = self._get_node_embedding(node)
        node_id = node.get("node_id")
        
        # 收集历史向量 (过滤掉自己)
        history_vecs = [
            self._get_node_embedding(n) for n in all_nodes 
            if n.get("node_id") != node_id
        ]
        
        # 过滤无效向量
        history_vecs = [v for v in history_vecs if v is not None]
        if not history_vecs:
            return 1.0

        # 矩阵化计算余弦相似度
        history_matrix = np.array(history_vecs)
        
        # 1. 点积 (Dot Product)
        dot_products = np.dot(history_matrix, current_vec)
        
        # 2. 范数 (Norms)
        curr_norm = np.linalg.norm(current_vec)
        hist_norms = np.linalg.norm(history_matrix, axis=1)
        
        # 3. 余弦相似度 = Dot / (NormA * NormB)
        # 加上 1e-9 防止分母为零
        similarities = dot_products / (curr_norm * hist_norms + 1e-9)
        
        # 取最大相似度 (截断在 0-1 之间)
        max_sim = max(0.0, float(np.max(similarities)))

        return 1.0 - max_sim

    def _get_node_embedding(self, node: Dict) -> Optional[np.ndarray]:
        """获取节点 Embedding (优先读缓存 -> 现场计算 -> 回写缓存)"""
        # 1. 缓存命中
        if "embedding" in node and node["embedding"] is not None:
            val = node["embedding"]
            return np.array(val) if isinstance(val, list) else val
            
        # 2. 现场计算
        text = node.get("nl_summary", "")
        if not text:
            return np.zeros(384) 
            
        # self.encoder 假定已在 __init__ 中初始化
        vec = self.encoder.encode(text)
        
        # 3. 回写缓存
        node["embedding"] = vec 
        return vec
