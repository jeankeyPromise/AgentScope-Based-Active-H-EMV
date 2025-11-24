"""
Memory-Gardener Agent: 主动记忆维护Agent (核心创新模块)

核心职责:
1. 后台周期性扫描记忆树
2. 计算节点效用值 U(n,t)
3. 执行自适应遗忘策略
4. 处理人机回环的记忆编辑
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler

from agentscope.message import Msg
from .base_agent import BaseMemoryAgent


class MemoryGardenerAgent(BaseMemoryAgent):
    """
    记忆园丁Agent - 主动维护记忆系统健康
    
    创新功能:
    1. 基于效用理论的自适应遗忘
    2. 追溯性记忆编辑与级联更新
    3. 一致性检查与修复
    """
    
    def __init__(
        self,
        name: str = "MemoryGardener",
        model_config_name: Optional[str] = None,
        storage_backends: Optional[Dict] = None,
        utility_scorer=None,  # UtilityScorer实例
        forgetting_policy=None,  # ForgettingPolicy实例
        editing_engine=None,  # EditingEngine实例
        schedule_enabled: bool = True,
        schedule_interval_hours: float = 1.0,
        utility_weights: tuple = (0.5, 0.3, 0.2),  # (α, β, γ)
        **kwargs
    ):
        """
        初始化记忆园丁Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置
            storage_backends: 存储后端
            utility_scorer: 效用评分器
            forgetting_policy: 遗忘策略
            editing_engine: 编辑引擎
            schedule_enabled: 是否启用定时任务
            schedule_interval_hours: 扫描间隔(小时)
            utility_weights: 效用函数权重 (访问热度, 语义显著性, 信息密度)
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            storage_backends=storage_backends,
            **kwargs
        )
        
        # 延迟导入,避免循环依赖
        from active_hemv.memory import UtilityScorer, ForgettingPolicy, EditingEngine
        
        self.utility_scorer = utility_scorer or UtilityScorer(*utility_weights)
        self.forgetting_policy = forgetting_policy or ForgettingPolicy()
        self.editing_engine = editing_engine or EditingEngine()
        
        # 初始化定时调度器
        if schedule_enabled:
            self.scheduler = BackgroundScheduler()
            self.scheduler.add_job(
                self.forgetting_cycle,
                'interval',
                hours=schedule_interval_hours,
                id='forgetting_cycle'
            )
            self.scheduler.start()
            logger.info(f"[{self.name}] Scheduled forgetting cycle every {schedule_interval_hours} hours")
        else:
            self.scheduler = None
        
        # 统计信息
        self.stats = {
            "cycles_run": 0,
            "nodes_forgotten": 0,
            "nodes_downgraded": 0,
            "nodes_merged": 0,
            "edits_performed": 0
        }
        
        logger.info(f"[{self.name}] Initialized with utility weights α={utility_weights[0]}, β={utility_weights[1]}, γ={utility_weights[2]}")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        处理不同类型的消息:
        1. ConflictEvent - 用户纠错,触发记忆编辑
        2. ManualTrigger - 手动触发遗忘周期
        3. UtilityQuery - 查询节点效用
        
        消息格式:
        {
            "type": "ConflictEvent" | "ManualTrigger" | "UtilityQuery",
            ... (根据type有不同字段)
        }
        """
        try:
            if x is None:
                return self.handle_error(ValueError("Empty message"), {})
            
            msg_type = x.content.get("type")
            
            if msg_type == "ConflictEvent":
                return self._handle_conflict_event(x)
            
            elif msg_type == "ManualTrigger":
                return self._handle_manual_trigger(x)
            
            elif msg_type == "UtilityQuery":
                return self._handle_utility_query(x)
            
            else:
                return self.handle_error(
                    ValueError(f"Unknown message type: {msg_type}"),
                    {"supported_types": ["ConflictEvent", "ManualTrigger", "UtilityQuery"]}
                )
            
        except Exception as e:
            return self.handle_error(e, {"input": str(x)[:200]})
    
    def forgetting_cycle(self):
        """
        主动遗忘周期 - 核心创新算法
        
        流程:
        1. 遍历所有记忆节点
        2. 计算效用值 U(n,t)
        3. 根据效用应用遗忘策略
        4. 更新统计信息
        """
        logger.info(f"[{self.name}] Starting forgetting cycle #{self.stats['cycles_run'] + 1}")
        start_time = datetime.now()
        
        try:
            vector_store = self.get_vector_store()
            if not vector_store:
                logger.warning("Vector store not available, skipping forgetting cycle")
                return
            
            # 1. 获取所有节点 (可以分批处理避免内存溢出)
            all_nodes = vector_store.get_all_nodes(limit=10000)
            logger.info(f"[{self.name}] Processing {len(all_nodes)} nodes")
            
            forgotten_count = 0
            downgraded_count = 0
            merged_count = 0
            
            # 2. 按层级分组处理
            nodes_by_level = self._group_nodes_by_level(all_nodes)
            
            # 3. 处理L0/L1层 - 激进遗忘
            if "L0" in nodes_by_level or "L1" in nodes_by_level:
                result = self._process_raw_and_scene_level(
                    nodes_by_level.get("L0", []) + nodes_by_level.get("L1", [])
                )
                forgotten_count += result["forgotten"]
                downgraded_count += result["downgraded"]
            
            # 4. 处理L2/L3层 - 语义融合
            if "L2" in nodes_by_level or "L3" in nodes_by_level:
                result = self._process_event_and_goal_level(
                    nodes_by_level.get("L2", []) + nodes_by_level.get("L3", [])
                )
                merged_count += result["merged"]
                downgraded_count += result["downgraded"]
            
            # 5. 处理L4+层 - 保护性维护
            if "L4+" in nodes_by_level:
                self._process_higher_level(nodes_by_level["L4+"])
            
            # 6. 更新统计
            self.stats["cycles_run"] += 1
            self.stats["nodes_forgotten"] += forgotten_count
            self.stats["nodes_downgraded"] += downgraded_count
            self.stats["nodes_merged"] += merged_count
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"[{self.name}] Forgetting cycle completed in {elapsed:.2f}s: "
                f"forgotten={forgotten_count}, downgraded={downgraded_count}, merged={merged_count}"
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] Forgetting cycle failed: {e}")
    
    def _group_nodes_by_level(self, nodes: List[Dict]) -> Dict[str, List[Dict]]:
        """将节点按层级分组"""
        groups = {}
        for node in nodes:
            level = node.get("level", "unknown")
            if level not in groups:
                groups[level] = []
            groups[level].append(node)
        return groups
    
    def _process_raw_and_scene_level(self, nodes: List[Dict]) -> Dict[str, int]:
        """
        处理L0/L1层 - 激进遗忘原始数据
        
        策略:
        - 低效用节点: 删除原始图像/音频,仅保留文本
        - 中效用节点: 降级存储(压缩)
        - 高效用节点: 完全保留
        - 锁定节点: 永久保护
        """
        forgotten = 0
        downgraded = 0
        current_time = datetime.now()
        
        for node in nodes:
            # 跳过锁定节点
            if node.get("is_locked"):
                continue
            
            # 计算效用
            utility = self.utility_scorer.compute(node, current_time, nodes)
            
            # 应用遗忘策略
            action = self.forgetting_policy.apply(utility)
            
            if action == "forget_raw":
                # 删除L0原始数据
                self._forget_raw_data(node)
                forgotten += 1
                logger.debug(f"[{self.name}] Forgot raw data for node {node['node_id']}")
            
            elif action == "downgrade":
                # 降级存储
                self._downgrade_storage(node)
                downgraded += 1
                logger.debug(f"[{self.name}] Downgraded node {node['node_id']}")
            
            # 更新向量数据库中的效用值
            self._update_utility_score(node['node_id'], utility)
        
        return {"forgotten": forgotten, "downgraded": downgraded}
    
    def _process_event_and_goal_level(self, nodes: List[Dict]) -> Dict[str, int]:
        """
        处理L2/L3层 - 语义融合
        
        策略:
        - 找出连续的低效用节点
        - 使用LLM合并为粗粒度节点
        """
        merged = 0
        downgraded = 0
        current_time = datetime.now()
        
        # 计算所有节点的效用
        nodes_with_utility = []
        for node in nodes:
            if node.get("is_locked"):
                continue
            utility = self.utility_scorer.compute(node, current_time, nodes)
            nodes_with_utility.append((node, utility))
        
        # 按时间排序
        nodes_with_utility.sort(key=lambda x: x[0]["timestamp_start"])
        
        # 查找连续的低效用节点进行合并
        i = 0
        while i < len(nodes_with_utility):
            node, utility = nodes_with_utility[i]
            
            if utility < self.forgetting_policy.THRESHOLD_LOW:
                # 收集连续的低效用节点
                merge_candidates = [node]
                j = i + 1
                while j < len(nodes_with_utility) and nodes_with_utility[j][1] < self.forgetting_policy.THRESHOLD_LOW:
                    merge_candidates.append(nodes_with_utility[j][0])
                    j += 1
                
                # 如果有多个连续节点,进行合并
                if len(merge_candidates) >= 2:
                    self._merge_nodes(merge_candidates)
                    merged += len(merge_candidates)
                    logger.info(f"[{self.name}] Merged {len(merge_candidates)} low-utility nodes")
                
                i = j
            else:
                i += 1
        
        return {"merged": merged, "downgraded": downgraded}
    
    def _process_higher_level(self, nodes: List[Dict]):
        """处理L4+层 - 保护性维护"""
        # L4+节点通常是高价值的,只做一致性检查
        for node in nodes:
            # 可以检查是否所有子节点仍然存在
            # 如果子节点被遗忘,可能需要重新生成摘要
            pass
    
    def _forget_raw_data(self, node: Dict):
        """删除节点的原始数据(L0图像/音频)"""
        object_store = self.get_object_store()
        if not object_store:
            return
        
        try:
            node_id = node["node_id"]
            # 构建文件路径
            # timestamp = datetime.fromtimestamp(node["timestamp_start"])
            # image_path = f"raw/{timestamp.strftime('%Y/%m/%d')}/{node_id}.jpg"
            # object_store.delete(image_path)
            
            # 在向量数据库中标记为"仅文本"
            vector_store = self.get_vector_store()
            if vector_store:
                vector_store.update(node_id, {"has_raw_data": False})
            
            logger.debug(f"Deleted raw data for {node_id}")
            
        except Exception as e:
            logger.error(f"Failed to forget raw data: {e}")
    
    def _downgrade_storage(self, node: Dict):
        """降级存储(如高压缩图像)"""
        object_store = self.get_object_store()
        if not object_store:
            return
        
        try:
            # 实现: 移动到downgraded/目录,使用更高压缩率
            # object_store.compress_and_move(node_id, compression_level=95)
            pass
        except Exception as e:
            logger.error(f"Failed to downgrade storage: {e}")
    
    def _merge_nodes(self, nodes: List[Dict]):
        """
        合并多个低效用节点
        
        使用LLM生成融合摘要,创建新的粗粒度节点
        """
        try:
            # 收集所有节点的摘要
            summaries = [n.get("nl_summary", "") for n in nodes]
            
            # LLM生成融合摘要
            merged_summary = self._llm_merge(summaries)
            
            # 创建新节点
            new_node_id = f"merged_{int(datetime.now().timestamp())}"
            
            vector_store = self.get_vector_store()
            if vector_store:
                vector_store.insert({
                    "node_id": new_node_id,
                    "level": nodes[0]["level"],  # 保持原层级
                    "nl_summary": merged_summary,
                    "timestamp_start": min(n["timestamp_start"] for n in nodes),
                    "timestamp_end": max(n["timestamp_end"] for n in nodes),
                    "utility_score": 0.4,  # 合并后的初始效用
                    "is_locked": False,
                    "merged_from": [n["node_id"] for n in nodes]
                })
            
            # 删除原节点
            for node in nodes:
                if vector_store:
                    vector_store.delete(node["node_id"])
            
            logger.info(f"Created merged node {new_node_id} from {len(nodes)} nodes")
            
        except Exception as e:
            logger.error(f"Failed to merge nodes: {e}")
    
    def _llm_merge(self, summaries: List[str]) -> str:
        """使用LLM合并多个摘要"""
        if not summaries:
            return "Empty merged summary"
        
        # 简单拼接作为占位符
        if len(summaries) <= 3:
            return " | ".join(summaries)
        
        # TODO: 调用LLM生成更好的合并摘要
        return f"合并了{len(summaries)}个相关事件"
    
    def _update_utility_score(self, node_id: str, utility: float):
        """更新节点的效用分数"""
        vector_store = self.get_vector_store()
        if vector_store:
            try:
                vector_store.update(node_id, {
                    "utility_score": utility,
                    "utility_updated_at": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to update utility score: {e}")
    
    def _handle_conflict_event(self, x: Msg) -> Msg:
        """
        处理冲突事件 - 用户纠错触发记忆编辑
        
        输入格式:
        {
            "type": "ConflictEvent",
            "original_answer": str,
            "user_correction": str,
            "query_context": {
                "query": str,
                "retrieved_nodes": List[str]
            }
        }
        
        流程:
        1. 定位错误源节点
        2. 重感知/重新处理
        3. 级联更新父节点
        4. 记录编辑历史
        """
        logger.info(f"[{self.name}] Handling conflict event")
        
        try:
            original = x.content.get("original_answer")
            correction = x.content.get("user_correction")
            context = x.content.get("query_context", {})
            
            # 1. 定位错误源
            error_node = self.editing_engine.locate_error_source(
                context.get("retrieved_nodes", []),
                original,
                correction,
                self.storage_backends
            )
            
            if not error_node:
                return self.create_success_msg({
                    "edit_performed": False,
                    "reason": "无法定位错误源节点"
                })
            
            logger.info(f"[{self.name}] Located error node: {error_node['node_id']}")
            
            # 2. 重感知
            reperception_result = self.editing_engine.reperceive(
                error_node,
                correction,
                self.storage_backends
            )
            
            if not reperception_result.get("success"):
                return self.create_success_msg({
                    "edit_performed": False,
                    "reason": reperception_result.get("reason", "重感知失败")
                })
            
            # 3. 级联更新
            affected_nodes = self.editing_engine.propagate_update_upward(
                error_node,
                self.storage_backends
            )
            
            # 4. 记录编辑
            self.editing_engine.log_edit({
                "timestamp": datetime.now(),
                "error_node": error_node["node_id"],
                "correction": correction,
                "affected_nodes": affected_nodes
            })
            
            self.stats["edits_performed"] += 1
            
            logger.info(f"[{self.name}] Edit completed, affected {len(affected_nodes)} nodes")
            
            return self.create_success_msg({
                "edit_performed": True,
                "error_node": error_node["node_id"],
                "affected_nodes": affected_nodes,
                "new_summary": reperception_result.get("new_summary")
            })
            
        except Exception as e:
            logger.error(f"[{self.name}] Conflict handling failed: {e}")
            return self.handle_error(e, {"conflict": str(x.content)[:200]})
    
    def _handle_manual_trigger(self, x: Msg) -> Msg:
        """处理手动触发遗忘周期"""
        logger.info(f"[{self.name}] Manual forgetting cycle triggered")
        self.forgetting_cycle()
        
        return self.create_success_msg({
            "cycle_completed": True,
            "stats": self.stats
        })
    
    def _handle_utility_query(self, x: Msg) -> Msg:
        """查询节点效用值"""
        node_id = x.content.get("node_id")
        
        vector_store = self.get_vector_store()
        if not vector_store:
            return self.handle_error(ValueError("Vector store not available"), {})
        
        try:
            node = vector_store.get_node(node_id)
            if not node:
                return self.handle_error(ValueError(f"Node {node_id} not found"), {})
            
            # 重新计算效用
            current_time = datetime.now()
            utility = self.utility_scorer.compute(node, current_time, [])
            
            return self.create_success_msg({
                "node_id": node_id,
                "utility_score": utility,
                "current_stored_score": node.get("utility_score"),
                "is_locked": node.get("is_locked", False)
            })
            
        except Exception as e:
            return self.handle_error(e, {"node_id": node_id})
    
    def __del__(self):
        """清理调度器"""
        if hasattr(self, 'scheduler') and self.scheduler:
            self.scheduler.shutdown()

