"""
遗忘策略 - 基于效用分数的三级阈值策略
"""

from typing import Literal
from loguru import logger


ForgettingAction = Literal["keep_all", "downgrade", "forget_raw", "text_only", "merge_or_delete"]


class ForgettingPolicy:
    """
    遗忘策略 - 将效用分数映射为具体的遗忘动作
    
    三级阈值:
    - HIGH (≥0.7): 完全保留,包括原始数据
    - MEDIUM (0.4-0.7): 降级存储,压缩原始数据
    - LOW (<0.4): 激进遗忘,仅保留文本摘要或合并
    """
    
    # 阈值常量
    THRESHOLD_HIGH = 0.7
    THRESHOLD_MED = 0.4
    THRESHOLD_LOW = 0.2
    
    def __init__(
        self,
        threshold_high: float = 0.7,
        threshold_med: float = 0.4,
        threshold_low: float = 0.2
    ):
        """
        初始化遗忘策略
        
        Args:
            threshold_high: 高价值阈值
            threshold_med: 中等价值阈值
            threshold_low: 低价值阈值
        """
        self.THRESHOLD_HIGH = threshold_high
        self.THRESHOLD_MED = threshold_med
        self.THRESHOLD_LOW = threshold_low
        
        logger.info(f"ForgettingPolicy initialized with thresholds: HIGH={threshold_high}, MED={threshold_med}, LOW={threshold_low}")
    
    def apply(self, utility_score: float) -> ForgettingAction:
        """
        根据效用分数决定遗忘动作
        
        Args:
            utility_score: 节点效用分数 [0, 1]
            
        Returns:
            ForgettingAction: 遗忘动作类型
        """
        if utility_score >= self.THRESHOLD_HIGH:
            return "keep_all"
        
        elif utility_score >= self.THRESHOLD_MED:
            return "downgrade"
        
        elif utility_score >= self.THRESHOLD_LOW:
            return "text_only"
        
        else:
            return "merge_or_delete"
    
    def get_action_description(self, action: ForgettingAction) -> str:
        """获取动作的详细描述"""
        descriptions = {
            "keep_all": "完全保留: 包括原始图像/音频和所有元数据",
            "downgrade": "降级存储: 压缩原始数据,保留高层摘要",
            "text_only": "仅文本: 删除原始数据,仅保留自然语言摘要",
            "merge_or_delete": "合并/删除: 将多个低效用节点合并为粗粒度节点"
        }
        return descriptions.get(action, "未知动作")

