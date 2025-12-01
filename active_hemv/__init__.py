"""
Active-H-EMV: AgentScope-Based Hierarchical Episodic Memory with Active Management

基于AgentScope框架的主动式层级情景记忆系统

新架构（简化版）:
- H-EMV作为数据结构（使用现有llm_emv代码）
- 三个后处理Agent（模拟人脑记忆机制）
  1. ForgettingAgent: 主动遗忘
  2. ConsolidationAgent: 记忆整合
  3. CorrectionAgent: 记忆修正
"""

__version__ = "2.0.0"
__author__ = "Your Name"
__description__ = "AgentScope-based post-processing agents for H-EMV memory system"

from .agents import (
    ForgettingAgent,
    ConsolidationAgent,
    CorrectionAgent,
    MemoryManager
)

from .memory import (
    UtilityScorer,
    ForgettingPolicy,
    EditingEngine,
    ConsistencyChecker
)

from .storage import (
    VectorStore,
    MilvusVectorStore,
    ChromaVectorStore
)

__all__ = [
    # Agents
    "ForgettingAgent",
    "ConsolidationAgent",
    "CorrectionAgent",
    "MemoryManager",
    
    # Memory Management
    "UtilityScorer",
    "ForgettingPolicy",
    "EditingEngine",
    "ConsistencyChecker",
    
    # Storage
    "VectorStore",
    "MilvusVectorStore",
    "ChromaVectorStore",
]


