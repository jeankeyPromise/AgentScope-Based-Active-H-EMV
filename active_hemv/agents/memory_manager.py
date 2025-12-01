"""
MemoryManager - 记忆管理器

统一管理三个后处理Agent，协调它们的工作

这是整个Active-H-EMV系统的核心调度器
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import pickle
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler

from agentscope.message import Msg
from em.em_tree import HigherLevelSummary

from .forgetting_agent import ForgettingAgent
from .consolidation_agent import ConsolidationAgent
from .correction_agent import CorrectionAgent


class MemoryManager:
    """
    记忆管理器 - 协调三个后处理Agent
    
    职责:
    1. 管理记忆树的生命周期
    2. 定时触发ForgettingAgent和ConsolidationAgent
    3. 按需触发CorrectionAgent
    4. 提供统一的查询接口
    """
    
    def __init__(
        self,
        memory_tree: Optional[HigherLevelSummary] = None,
        forgetting_interval_hours: float = 1.0,
        consolidation_time: str = "02:00",  # 凌晨2点整合
        enable_auto_schedule: bool = True,
        storage_path: Optional[str] = None,
        **agent_configs
    ):
        """
        初始化记忆管理器
        
        Args:
            memory_tree: 初始记忆树（可选）
            forgetting_interval_hours: 遗忘Agent运行间隔（小时）
            consolidation_time: 整合Agent运行时间（24小时制）
            enable_auto_schedule: 是否启用自动调度
            storage_path: 记忆树持久化路径
            **agent_configs: Agent配置参数
        """
        self.memory_tree = memory_tree
        self.storage_path = storage_path
        
        # 创建三个Agent
        self.forgetting_agent = ForgettingAgent(
            name="ForgettingAgent",
            **agent_configs.get("forgetting", {})
        )
        
        self.consolidation_agent = ConsolidationAgent(
            name="ConsolidationAgent",
            **agent_configs.get("consolidation", {})
        )
        
        self.correction_agent = CorrectionAgent(
            name="CorrectionAgent",
            **agent_configs.get("correction", {})
        )
        
        # 初始化调度器
        self.scheduler = None
        if enable_auto_schedule:
            self.scheduler = BackgroundScheduler()
            
            # 添加遗忘任务（每小时）
            self.scheduler.add_job(
                self.run_forgetting_cycle,
                'interval',
                hours=forgetting_interval_hours,
                id='forgetting_cycle'
            )
            
            # 添加整合任务（每天凌晨2点）
            hour, minute = map(int, consolidation_time.split(':'))
            self.scheduler.add_job(
                self.run_consolidation_cycle,
                'cron',
                hour=hour,
                minute=minute,
                id='consolidation_cycle'
            )
            
            self.scheduler.start()
            logger.info(f"[MemoryManager] Auto-scheduler started")
        
        # 统计信息
        self.stats = {
            "total_queries": 0,
            "forgetting_cycles": 0,
            "consolidation_cycles": 0,
            "corrections": 0
        }
        
        logger.info("[MemoryManager] Initialized with 3 agents")
    
    def load_memory_tree(self, path: str):
        """
        从文件加载记忆树
        
        Args:
            path: pickle文件路径
        """
        try:
            with open(path, 'rb') as f:
                self.memory_tree = pickle.load(f)
            logger.info(f"[MemoryManager] Loaded memory tree from {path}")
        except Exception as e:
            logger.error(f"Failed to load memory tree: {e}")
            raise
    
    def save_memory_tree(self, path: Optional[str] = None):
        """
        保存记忆树到文件
        
        Args:
            path: 保存路径（可选，默认使用初始化时的storage_path）
        """
        save_path = path or self.storage_path
        
        if not save_path:
            logger.warning("No storage path specified, skipping save")
            return
        
        try:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                pickle.dump(self.memory_tree, f)
            logger.info(f"[MemoryManager] Saved memory tree to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save memory tree: {e}")
    
    def run_forgetting_cycle(self) -> Dict[str, Any]:
        """
        运行一次遗忘周期
        
        Returns:
            Dict: 遗忘结果统计
        """
        if self.memory_tree is None:
            logger.warning("[MemoryManager] No memory tree, skipping forgetting cycle")
            return {"success": False, "reason": "no_memory_tree"}
        
        logger.info("[MemoryManager] Running forgetting cycle")
        
        msg = Msg(
            name="MemoryManager",
            content={
                "type": "forgetting_cycle",
                "memory_tree": self.memory_tree,
                "current_time": datetime.now()
            },
            role="system"
        )
        
        result = self.forgetting_agent(msg)
        
        if result.content.get("type") == "forgetting_result":
            self.memory_tree = result.content["updated_tree"]
            self.stats["forgetting_cycles"] += 1
            
            # 自动保存
            if self.storage_path:
                self.save_memory_tree()
            
            return result.content["cycle_stats"]
        
        return {"success": False, "error": result.content.get("message")}
    
    def run_consolidation_cycle(self, mode: str = "daily") -> Dict[str, Any]:
        """
        运行一次记忆整合周期
        
        Args:
            mode: "daily" | "weekly"
            
        Returns:
            Dict: 整合结果统计
        """
        if self.memory_tree is None:
            logger.warning("[MemoryManager] No memory tree, skipping consolidation cycle")
            return {"success": False, "reason": "no_memory_tree"}
        
        logger.info(f"[MemoryManager] Running {mode} consolidation cycle")
        
        msg = Msg(
            name="MemoryManager",
            content={
                "type": "consolidate",
                "memory_tree": self.memory_tree,
                "consolidation_mode": mode
            },
            role="system"
        )
        
        result = self.consolidation_agent(msg)
        
        if result.content.get("type") == "consolidation_result":
            self.memory_tree = result.content["updated_tree"]
            self.stats["consolidation_cycles"] += 1
            
            # 自动保存
            if self.storage_path:
                self.save_memory_tree()
            
            return result.content["cycle_stats"]
        
        return {"success": False, "error": result.content.get("message")}
    
    def correct_memory(
        self,
        query: str,
        system_answer: str,
        user_correction: str
    ) -> Dict[str, Any]:
        """
        处理用户纠错
        
        Args:
            query: 原始查询
            system_answer: 系统的错误回答
            user_correction: 用户的纠正
            
        Returns:
            Dict: 修正结果
        """
        if self.memory_tree is None:
            logger.warning("[MemoryManager] No memory tree, cannot correct")
            return {"success": False, "reason": "no_memory_tree"}
        
        logger.info(f"[MemoryManager] Processing user correction for: '{query}'")
        
        msg = Msg(
            name="User",
            content={
                "type": "correction",
                "memory_tree": self.memory_tree,
                "query": query,
                "system_answer": system_answer,
                "user_correction": user_correction
            },
            role="user"
        )
        
        result = self.correction_agent(msg)
        
        if result.content.get("type") == "correction_result":
            self.memory_tree = result.content["updated_tree"]
            self.stats["corrections"] += 1
            
            # 自动保存
            if self.storage_path:
                self.save_memory_tree()
            
            return {
                "success": result.content["success"],
                "nodes_updated": result.content.get("nodes_updated", 0)
            }
        
        return {"success": False, "error": result.content.get("message")}
    
    def query(self, question: str) -> str:
        """
        查询记忆（使用现有的llm_emv代码）
        
        Args:
            question: 用户问题
            
        Returns:
            str: 回答
        """
        if self.memory_tree is None:
            return "记忆树为空，无法回答"
        
        self.stats["total_queries"] += 1
        
        # 这里应该集成现有的llm_emv查询逻辑
        # 简化实现：返回提示
        logger.info(f"[MemoryManager] Query: {question}")
        return "请使用llm_emv的查询接口进行检索"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        return {
            "manager": self.stats,
            "forgetting_agent": self.forgetting_agent.stats,
            "consolidation_agent": self.consolidation_agent.stats,
            "correction_agent": self.correction_agent.stats
        }
    
    def shutdown(self):
        """关闭管理器，停止调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("[MemoryManager] Scheduler stopped")
        
        # 最后保存
        if self.storage_path:
            self.save_memory_tree()
    
    def __del__(self):
        """析构时自动关闭"""
        try:
            self.shutdown()
        except:
            pass

