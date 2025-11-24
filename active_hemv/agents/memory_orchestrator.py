"""
Memory-Orchestrator Agent: L3+层的全局记忆协调器

核心职责:
1. 维护完整的记忆树结构
2. 递归生成L3 (Goal) 和 L4+ (Higher-Level Summary)
3. 处理用户查询,实现交互式检索
4. 协调并行SearchWorker进行高效搜索
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from agentscope.message import Msg
from .base_agent import BaseMemoryAgent
from em.em_tree import (
    EventBasedSummary, 
    GoalBasedSummary, 
    HigherLevelSummary,
    HighestPredefinedSummaryLevel
)


class MemoryOrchestratorAgent(BaseMemoryAgent):
    """
    记忆编排Agent - 管理整个记忆树并处理查询
    
    功能:
    - 维护L3和L4+节点
    - 递归LLM摘要生成
    - 交互式检索路由
    - 并行搜索调度
    """
    
    def __init__(
        self,
        name: str = "MemoryOrchestrator",
        model_config_name: Optional[str] = None,
        storage_backends: Optional[Dict] = None,
        summary_threshold: int = 5,  # 多少个子节点触发摘要
        enable_parallel_search: bool = True,
        max_search_workers: int = 3,
        **kwargs
    ):
        """
        初始化记忆编排Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置
            storage_backends: 存储后端
            summary_threshold: 触发摘要的子节点数量
            enable_parallel_search: 是否启用并行搜索
            max_search_workers: 最大并行搜索Worker数
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            storage_backends=storage_backends,
            **kwargs
        )
        
        self.summary_threshold = summary_threshold
        self.enable_parallel_search = enable_parallel_search
        self.max_search_workers = max_search_workers
        
        # 维护L3节点的缓冲区
        self.l3_buffer: List[GoalBasedSummary] = []
        
        # 记忆树根节点
        self.memory_root: Optional[HigherLevelSummary] = None
        
        # 搜索工作池
        if enable_parallel_search:
            self.search_executor = ThreadPoolExecutor(
                max_workers=max_search_workers,
                thread_name_prefix="SearchWorker"
            )
        
        logger.info(f"[{self.name}] Initialized with summary_threshold={summary_threshold}")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        处理不同类型的消息:
        1. 新事件通知 (来自Event Aggregator)
        2. 用户查询 (来自用户或其他Agent)
        3. 摘要触发请求
        
        消息格式:
        {
            "type": "new_event" | "user_query" | "trigger_summary",
            ... (根据type有不同字段)
        }
        """
        try:
            if x is None:
                return self.handle_error(ValueError("Empty message"), {})
            
            msg_type = x.content.get("type")
            
            if msg_type == "new_event":
                return self._handle_new_event(x)
            
            elif msg_type == "user_query":
                return self._handle_user_query(x)
            
            elif msg_type == "trigger_summary":
                return self._handle_summary_trigger(x)
            
            else:
                return self.handle_error(
                    ValueError(f"Unknown message type: {msg_type}"),
                    {"supported_types": ["new_event", "user_query", "trigger_summary"]}
                )
            
        except Exception as e:
            return self.handle_error(e, {"input": str(x)[:200]})
    
    def _handle_new_event(self, x: Msg) -> Msg:
        """
        处理来自Event Aggregator的新事件
        
        输入格式:
        {
            "type": "new_event",
            "event_summary": EventBasedSummary,
            "l2_node_id": str
        }
        """
        event_summary = x.content.get("event_summary")
        l2_node_id = x.content.get("l2_node_id")
        
        logger.info(f"[{self.name}] Received new event: {l2_node_id}")
        
        # 1. 判断是否应该创建新的L3目标节点
        # 简化策略: 如果l3_buffer为空或目标改变,创建新L3
        should_create_l3 = self._should_create_goal_node(event_summary)
        
        if should_create_l3:
            # 创建新的L3节点
            l3_node = self._create_goal_node([event_summary])
            l3_node_id = self._persist_goal_node(l3_node)
            
            self.l3_buffer.append(l3_node)
            logger.info(f"[{self.name}] Created new L3 node: {l3_node_id}")
        else:
            # 将事件添加到当前L3节点
            if self.l3_buffer:
                current_l3 = self.l3_buffer[-1]
                current_l3.events.append(event_summary)
                logger.debug(f"[{self.name}] Added event to current L3 node")
        
        # 2. 检查是否应该触发L4摘要
        if len(self.l3_buffer) >= self.summary_threshold:
            self._generate_higher_level_summary()
        
        return self.create_success_msg({
            "l3_created": should_create_l3,
            "l3_buffer_size": len(self.l3_buffer)
        })
    
    def _should_create_goal_node(self, event: EventBasedSummary) -> bool:
        """判断是否应该创建新的L3目标节点"""
        if not self.l3_buffer:
            return True
        
        # 如果目标描述改变,创建新L3
        current_goal = event.latest_raw.current_goal
        if current_goal:
            last_l3 = self.l3_buffer[-1]
            last_goal = last_l3.explicit_goal or last_l3.latest_raw.current_goal
            
            if current_goal != last_goal:
                logger.debug(f"[{self.name}] Goal changed: {last_goal} -> {current_goal}")
                return True
        
        # 如果当前L3已经包含太多事件,也创建新的
        if len(self.l3_buffer[-1].events) >= 10:
            logger.debug(f"[{self.name}] Current L3 node is full")
            return True
        
        return False
    
    def _create_goal_node(self, events: List[EventBasedSummary]) -> GoalBasedSummary:
        """创建L3目标节点"""
        return GoalBasedSummary(
            events=events,
            explicit_goal=events[-1].latest_raw.current_goal if events else None
        )
    
    def _persist_goal_node(self, goal: GoalBasedSummary) -> str:
        """持久化L3节点"""
        node_id = f"l3_{int(goal.latest_raw.timestamp.timestamp())}"
        
        # 向量数据库
        vector_store = self.get_vector_store()
        if vector_store:
            try:
                start_time, end_time = goal.range
                
                vector_store.insert({
                    "node_id": node_id,
                    "level": "L3",
                    "nl_summary": goal.nl_summary,
                    "timestamp_start": int(start_time.timestamp()),
                    "timestamp_end": int(end_time.timestamp()),
                    "utility_score": 0.6,  # L3初始效用略高
                    "is_locked": False,
                    "events_count": len(goal.events)
                })
            except Exception as e:
                logger.error(f"Failed to persist L3 to vector store: {e}")
        
        # 图数据库
        graph_store = self.get_graph_store()
        if graph_store:
            try:
                graph_store.create_node("L3Node", node_id, {
                    "nl_summary": goal.nl_summary,
                    "goal": goal.explicit_goal,
                    "timestamp_start": goal.range[0].isoformat(),
                    "timestamp_end": goal.range[1].isoformat()
                })
                
                # 连接到L2事件
                for event in goal.events:
                    l2_node_id = f"l2_{int(event.latest_raw.timestamp.timestamp())}"
                    graph_store.create_relation(node_id, l2_node_id, "CONTAINS")
                    
            except Exception as e:
                logger.error(f"Failed to persist L3 to graph store: {e}")
        
        self.log_access(node_id, "write")
        return node_id
    
    def _generate_higher_level_summary(self):
        """生成L4+更高层摘要"""
        if len(self.l3_buffer) < self.summary_threshold:
            return
        
        logger.info(f"[{self.name}] Generating L4+ summary from {len(self.l3_buffer)} L3 nodes")
        
        try:
            # 1. 使用LLM对L3节点进行摘要
            l3_summaries = [goal.nl_summary for goal in self.l3_buffer]
            higher_summary_text = self._llm_summarize(l3_summaries)
            
            # 2. 创建L4节点
            l4_node = HigherLevelSummary(
                nl_summary=higher_summary_text,
                children=self.l3_buffer.copy()
            )
            
            # 3. 持久化
            l4_node_id = self._persist_higher_summary(l4_node)
            
            # 4. 更新记忆树根节点
            if self.memory_root is None:
                self.memory_root = l4_node
            else:
                # 将新的L4节点添加到根节点的children
                if not hasattr(self.memory_root, 'children'):
                    # 根节点需要升级
                    old_root = self.memory_root
                    self.memory_root = HigherLevelSummary(
                        nl_summary="Complete robot experience history",
                        children=[old_root, l4_node]
                    )
                else:
                    self.memory_root.children.append(l4_node)
            
            # 5. 清空L3缓冲区
            self.l3_buffer = []
            
            logger.info(f"[{self.name}] L4+ summary created: {l4_node_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate higher-level summary: {e}")
    
    def _llm_summarize(self, summaries: List[str]) -> str:
        """
        使用LLM对多个摘要进行递归压缩
        
        Args:
            summaries: 子节点摘要列表
            
        Returns:
            str: 高层摘要
        """
        if not summaries:
            return "Empty summary"
        
        # 如果没有配置LLM,使用简单拼接
        if not self.model_config_name or not hasattr(self, 'model'):
            logger.warning("LLM not configured, using simple concatenation")
            return " | ".join(summaries[:3]) + f" ... (total {len(summaries)} goals)"
        
        try:
            prompt = f"""
            你是一个机器人记忆系统的摘要生成器。请对以下{len(summaries)}个子任务/目标进行高层次摘要:
            
            {chr(10).join(f'{i+1}. {s}' for i, s in enumerate(summaries))}
            
            要求:
            1. 用1-2句话概括整体活动主题
            2. 保留关键信息(地点、重要物体、主要动作)
            3. 省略重复性细节
            4. 使用中文
            
            摘要:
            """
            
            # 调用LLM
            # response = self.model.generate(prompt)
            # return response.strip()
            
            # 占位符
            return f"机器人完成了{len(summaries)}个相关任务"
            
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return " | ".join(summaries[:3]) + "..."
    
    def _persist_higher_summary(self, summary: HigherLevelSummary) -> str:
        """持久化L4+节点"""
        timestamp = int(datetime.now().timestamp())
        node_id = f"l4_{timestamp}"
        
        vector_store = self.get_vector_store()
        if vector_store:
            try:
                start_time, end_time = summary.range
                
                vector_store.insert({
                    "node_id": node_id,
                    "level": "L4+",
                    "nl_summary": summary.nl_summary,
                    "timestamp_start": int(start_time.timestamp()),
                    "timestamp_end": int(end_time.timestamp()),
                    "utility_score": 0.7,  # 高层节点效用更高
                    "is_locked": False,
                    "children_count": len(summary.children)
                })
            except Exception as e:
                logger.error(f"Failed to persist L4+ to vector store: {e}")
        
        graph_store = self.get_graph_store()
        if graph_store:
            try:
                graph_store.create_node("L4Node", node_id, {
                    "nl_summary": summary.nl_summary,
                    "timestamp_start": summary.range[0].isoformat(),
                    "timestamp_end": summary.range[1].isoformat()
                })
                
                # 连接到子节点
                for child in summary.children:
                    child_id = f"l3_{int(child.latest_raw.timestamp.timestamp())}"
                    graph_store.create_relation(node_id, child_id, "CONTAINS")
                    
            except Exception as e:
                logger.error(f"Failed to persist L4+ to graph store: {e}")
        
        self.log_access(node_id, "write")
        return node_id
    
    def _handle_user_query(self, x: Msg) -> Msg:
        """
        处理用户查询
        
        输入格式:
        {
            "type": "user_query",
            "query": str,
            "enable_parallel": bool (可选)
        }
        
        返回格式:
        {
            "type": "query_result",
            "answer": str,
            "retrieved_nodes": List[str],
            "search_strategy": str
        }
        """
        query = x.content.get("query")
        enable_parallel = x.content.get("enable_parallel", self.enable_parallel_search)
        
        logger.info(f"[{self.name}] Processing query: {query}")
        
        try:
            # 1. 解析查询 (提取时间、实体等)
            query_context = self._parse_query(query)
            
            # 2. 决策搜索策略
            if enable_parallel and query_context.get("uncertain_time"):
                # 并行搜索
                result = self._parallel_temporal_search(query, query_context)
                strategy = "parallel_temporal"
            else:
                # 标准层级搜索
                result = self._hierarchical_search(query, query_context)
                strategy = "hierarchical"
            
            # 3. 生成回答
            answer = self._generate_answer(query, result)
            
            return self.create_success_msg({
                "answer": answer,
                "retrieved_nodes": result.get("node_ids", []),
                "search_strategy": strategy,
                "nodes_examined": result.get("nodes_examined", 0)
            })
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return self.handle_error(e, {"query": query})
    
    def _parse_query(self, query: str) -> Dict[str, Any]:
        """解析查询,提取关键信息"""
        context = {
            "uncertain_time": False,
            "time_mentioned": None,
            "entities": [],
            "action": None
        }
        
        # 简化的关键词检测
        uncertain_keywords = ["哪天", "什么时候", "何时"]
        if any(kw in query for kw in uncertain_keywords):
            context["uncertain_time"] = True
        
        time_keywords = {"昨天": 1, "前天": 2, "上周": 7, "上个月": 30}
        for kw, days_ago in time_keywords.items():
            if kw in query:
                context["time_mentioned"] = datetime.now() - timedelta(days=days_ago)
                break
        
        return context
    
    def _hierarchical_search(self, query: str, context: Dict) -> Dict[str, Any]:
        """标准的层级化搜索 (H-EMV原有方法)"""
        vector_store = self.get_vector_store()
        if not vector_store:
            return {"node_ids": [], "nodes_examined": 0}
        
        # 从根节点开始搜索
        try:
            # 如果有时间信息,先过滤
            time_filter = {}
            if context.get("time_mentioned"):
                timestamp = int(context["time_mentioned"].timestamp())
                time_filter = {
                    "timestamp_start": ("<=", timestamp),
                    "timestamp_end": (">=", timestamp)
                }
            
            # 语义搜索
            results = vector_store.search(query, top_k=5, filters=time_filter)
            
            return {
                "node_ids": [r["node_id"] for r in results],
                "nodes_examined": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Hierarchical search failed: {e}")
            return {"node_ids": [], "nodes_examined": 0}
    
    def _parallel_temporal_search(self, query: str, context: Dict) -> Dict[str, Any]:
        """并行时间搜索 (创新点)"""
        if not self.enable_parallel_search:
            return self._hierarchical_search(query, context)
        
        # 分解时间范围
        now = datetime.now()
        time_ranges = [
            ("last_week", now - timedelta(days=7), now),
            ("last_month", now - timedelta(days=30), now - timedelta(days=7)),
            ("last_3_months", now - timedelta(days=90), now - timedelta(days=30))
        ]
        
        logger.info(f"[{self.name}] Starting parallel search across {len(time_ranges)} time ranges")
        
        all_results = []
        futures = []
        
        # 并行搜索各个时间段
        for name, start, end in time_ranges:
            future = self.search_executor.submit(
                self._search_time_range,
                query, start, end, name
            )
            futures.append(future)
        
        # 收集结果
        for future in as_completed(futures):
            try:
                result = future.result(timeout=10)
                if result["found"]:
                    all_results.extend(result["nodes"])
            except Exception as e:
                logger.error(f"Search worker failed: {e}")
        
        # 按相似度排序
        all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        return {
            "node_ids": [r["node_id"] for r in all_results[:5]],
            "nodes_examined": len(all_results),
            "results": all_results[:5]
        }
    
    def _search_time_range(
        self, 
        query: str, 
        start: datetime, 
        end: datetime,
        range_name: str
    ) -> Dict[str, Any]:
        """在特定时间范围内搜索"""
        vector_store = self.get_vector_store()
        if not vector_store:
            return {"found": False, "nodes": []}
        
        try:
            filters = {
                "timestamp_start": (">=", int(start.timestamp())),
                "timestamp_end": ("<=", int(end.timestamp()))
            }
            
            results = vector_store.search(query, top_k=3, filters=filters)
            
            logger.debug(f"[{self.name}] Search in {range_name}: {len(results)} results")
            
            return {
                "found": len(results) > 0,
                "nodes": results,
                "time_range": range_name
            }
            
        except Exception as e:
            logger.error(f"Search in {range_name} failed: {e}")
            return {"found": False, "nodes": []}
    
    def _generate_answer(self, query: str, search_result: Dict) -> str:
        """根据检索结果生成回答"""
        if not search_result.get("results"):
            return "抱歉,我在记忆中没有找到相关信息。"
        
        # 获取最相关的节点
        top_result = search_result["results"][0]
        nl_summary = top_result.get("nl_summary", "")
        
        # 如果有LLM,可以生成更好的回答
        if hasattr(self, 'model') and self.model_config_name:
            try:
                prompt = f"""
                用户问题: {query}
                
                检索到的记忆片段:
                {nl_summary}
                
                请根据这段记忆,用自然的中文回答用户的问题。如果记忆中没有直接答案,请诚实说明。
                
                回答:
                """
                
                # answer = self.model.generate(prompt)
                # return answer.strip()
                pass
            except Exception as e:
                logger.error(f"Answer generation failed: {e}")
        
        # 简单回答
        return f"根据记忆,{nl_summary}"
    
    def _handle_summary_trigger(self, x: Msg) -> Msg:
        """处理手动摘要触发请求"""
        self._generate_higher_level_summary()
        return self.create_success_msg({
            "summary_generated": True,
            "l3_buffer_cleared": len(self.l3_buffer) == 0
        })

