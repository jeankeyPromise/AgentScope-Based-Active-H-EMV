"""
AgentScope-based Agent implementations for Active-H-EMV

新架构（简化版）：
- ForgettingAgent: 主动遗忘（模拟Ebbinghaus遗忘曲线）
- ConsolidationAgent: 记忆整合（模拟睡眠巩固）
- CorrectionAgent: 记忆修正（人机回环纠错）
- MemoryManager: 统一管理器
"""

from .forgetting_agent import ForgettingAgent
from .consolidation_agent import ConsolidationAgent
from .correction_agent import CorrectionAgent
from .memory_manager import MemoryManager

__all__ = [
    "ForgettingAgent",
    "ConsolidationAgent",
    "CorrectionAgent",
    "MemoryManager",
]

