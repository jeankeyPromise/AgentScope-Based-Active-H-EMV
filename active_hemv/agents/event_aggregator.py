"""
Event-Aggregator Agent: 负责将L1场景图聚合为L2事件

核心职责:
1. 监听L1数据流
2. 检测事件边界(动作完成、场景变化)
3. 生成自然语言事件描述
4. 向Memory Orchestrator报告新事件
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from agentscope.message import Msg
from .base_agent import BaseMemoryAgent
from em.em_tree import SceneGraphInstant, EventBasedSummary


class EventAggregatorAgent(BaseMemoryAgent):
    """
    事件聚合Agent - 将连续的场景图聚合为事件节点
    
    聚合规则:
    - 动作状态机转换 (running -> succeeded/failed)
    - 场景图显著变化
    - 语音指令触发
    """
    
    def __init__(
        self,
        name: str = "EventAggregator",
        model_config_name: Optional[str] = None,
        storage_backends: Optional[Dict] = None,
        event_window_size: int = 5,  # 事件窗口大小(场景图数量)
        **kwargs
    ):
        """
        初始化事件聚合Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置(用于生成事件描述)
            storage_backends: 存储后端
            event_window_size: 事件滑动窗口大小
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            storage_backends=storage_backends,
            **kwargs
        )
        
        self.event_window_size = event_window_size
        
        # 维护一个滑动窗口,存储最近的场景图
        self.scene_window: List[SceneGraphInstant] = []
        
        # 当前正在构建的事件
        self.current_event_scenes: List[SceneGraphInstant] = []
        
        logger.info(f"[{self.name}] Initialized with window size={event_window_size}")
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        处理来自Perception Worker的状态变化消息
        
        输入消息格式:
        {
            "type": "perception_result" | "state_change",
            "scene_graph": SceneGraphInstant,
            "state_changed": bool,
            "l1_node_id": str
        }
        
        返回消息格式:
        {
            "type": "event_aggregation_result",
            "event_created": bool,
            "event": EventBasedSummary (if created),
            "l2_node_id": str (if created)
        }
        """
        try:
            if x is None:
                return self.handle_error(ValueError("Empty message"), {})
            
            msg_type = x.content.get("type")
            if msg_type not in ["perception_result", "state_change"]:
                return self.handle_error(
                    ValueError("Invalid message type"),
                    {"expected": ["perception_result", "state_change"], "received": msg_type}
                )
            
            scene_graph = x.content.get("scene_graph")
            state_changed = x.content.get("state_changed", False)
            l1_node_id = x.content.get("l1_node_id")
            
            # 1. 添加到场景窗口
            self.scene_window.append(scene_graph)
            self.current_event_scenes.append(scene_graph)
            
            # 2. 检查是否应该创建事件
            should_create_event = self._should_create_event(scene_graph, state_changed)
            
            if should_create_event:
                # 3. 创建事件节点
                event = self._create_event()
                
                # 4. 生成事件描述
                event = self._enrich_event_description(event)
                
                # 5. 持久化事件
                l2_node_id = self._persist_event(event)
                self.log_access(l2_node_id, "write")
                
                # 6. 清空当前事件场景缓冲
                self.current_event_scenes = []
                
                # 7. 维护滑动窗口大小
                if len(self.scene_window) > self.event_window_size:
                    self.scene_window = self.scene_window[-self.event_window_size:]
                
                logger.info(f"[{self.name}] Event created: {l2_node_id}")
                
                return self.create_success_msg({
                    "event_created": True,
                    "event_summary": event.nl_summary,
                    "l2_node_id": l2_node_id,
                    "scenes_count": len(event.scenes)
                })
            
            else:
                # 未创建事件,仅确认接收
                return self.create_success_msg({
                    "event_created": False,
                    "buffered_scenes": len(self.current_event_scenes)
                })
            
        except Exception as e:
            return self.handle_error(e, {"input": str(x)[:200]})
    
    def _should_create_event(
        self, 
        current_scene: SceneGraphInstant, 
        state_changed: bool
    ) -> bool:
        """
        判断是否应该创建事件节点
        
        事件边界检测规则:
        1. 动作状态完成 (succeeded/failed/stopped)
        2. 新的动作开始
        3. 语音指令出现
        4. 场景窗口满
        
        Args:
            current_scene: 当前场景图
            state_changed: 是否发生状态变化
            
        Returns:
            bool: 是否创建事件
        """
        if len(self.current_event_scenes) == 0:
            return False
        
        # 规则1: 动作状态完成
        action_state = current_scene.raw.current_action_state
        if action_state in ["succeeded", "failed", "stopped", "aborted"]:
            logger.debug(f"[{self.name}] Event boundary: action {action_state}")
            return True
        
        # 规则2: 动作切换
        if len(self.current_event_scenes) > 1:
            last_action = self.current_event_scenes[-2].raw.current_action
            curr_action = current_scene.raw.current_action
            if last_action != curr_action:
                logger.debug(f"[{self.name}] Event boundary: action change {last_action} -> {curr_action}")
                return True
        
        # 规则3: 语音指令(通常标志新任务)
        if current_scene.raw.asr_recognition:
            logger.debug(f"[{self.name}] Event boundary: speech command")
            return True
        
        # 规则4: 窗口满
        if len(self.current_event_scenes) >= self.event_window_size:
            logger.debug(f"[{self.name}] Event boundary: window full")
            return True
        
        return False
    
    def _create_event(self) -> EventBasedSummary:
        """
        从缓冲的场景图创建EventBasedSummary
        
        Returns:
            EventBasedSummary: 事件节点
        """
        if not self.current_event_scenes:
            raise ValueError("No scenes to create event from")
        
        # 提取音频描述(如果有)
        audio_description = self._extract_audio_description()
        
        # 提取动作参数摘要
        action_param_summary = self._extract_action_parameters()
        
        event = EventBasedSummary(
            scenes=self.current_event_scenes.copy(),
            audio_description=audio_description,
            action_parameter_summary=action_param_summary
        )
        
        return event
    
    def _extract_audio_description(self) -> Optional[str]:
        """提取事件中的音频描述"""
        audio_texts = []
        for scene in self.current_event_scenes:
            if scene.raw.asr_recognition:
                audio_texts.append(scene.raw.asr_recognition)
        
        if audio_texts:
            return " | ".join(audio_texts)
        return None
    
    def _extract_action_parameters(self) -> Optional[str]:
        """提取并摘要动作参数"""
        # 获取最后一个场景的动作参数
        last_scene = self.current_event_scenes[-1]
        params = last_scene.raw.current_action_parameters
        
        if params:
            # 简单的参数摘要(可以用LLM优化)
            param_strs = [f"{k}={v}" for k, v in params.items()]
            return ", ".join(param_strs)
        
        return None
    
    def _enrich_event_description(self, event: EventBasedSummary) -> EventBasedSummary:
        """
        使用LLM增强事件描述的自然语言质量
        
        Args:
            event: 原始事件
            
        Returns:
            EventBasedSummary: 增强后的事件
        """
        # 这里可以调用LLM优化nl_summary
        # 目前使用em_tree.py中的内置方法
        
        # 如果有LLM,可以这样调用:
        if self.model_config_name and hasattr(self, 'model'):
            try:
                prompt = f"""
                以下是一个机器人事件的原始描述:
                
                {event.nl_summary}
                
                请将其改写为更自然、简洁的中文描述,保留关键信息。
                """
                
                # enhanced = self.model.generate(prompt)
                # event._enhanced_summary = enhanced  # 可以添加增强版本
                pass
            except Exception as e:
                logger.warning(f"Failed to enrich event description: {e}")
        
        return event
    
    def _persist_event(self, event: EventBasedSummary) -> str:
        """
        持久化L2事件节点
        
        Args:
            event: 事件节点
            
        Returns:
            str: L2节点ID
        """
        node_id = f"l2_{int(event.latest_raw.timestamp.timestamp())}"
        
        # 1. 向量数据库
        vector_store = self.get_vector_store()
        if vector_store:
            try:
                start_time, end_time = event.range
                
                vector_store.insert({
                    "node_id": node_id,
                    "level": "L2",
                    "nl_summary": event.nl_summary,
                    "timestamp_start": int(start_time.timestamp()),
                    "timestamp_end": int(end_time.timestamp()),
                    "utility_score": 0.5,
                    "is_locked": False,
                    "scenes_count": len(event.scenes),
                    "has_audio": event.audio_description is not None
                })
            except Exception as e:
                logger.error(f"Failed to insert event to vector store: {e}")
        
        # 2. 图数据库
        graph_store = self.get_graph_store()
        if graph_store:
            try:
                # 创建L2节点
                graph_store.create_node("L2Node", node_id, {
                    "nl_summary": event.nl_summary,
                    "timestamp_start": event.range[0].isoformat(),
                    "timestamp_end": event.range[1].isoformat()
                })
                
                # 连接到L1场景图
                for scene in event.scenes:
                    l1_node_id = f"l1_{int(scene.raw.timestamp.timestamp())}"
                    graph_store.create_relation(node_id, l1_node_id, "CONTAINS")
                    
            except Exception as e:
                logger.error(f"Failed to insert event to graph store: {e}")
        
        return node_id

