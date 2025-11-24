"""
Perception-Worker Agent: 负责L0 (Raw) → L1 (Scene Graph) 的转换

核心职责:
1. 实时处理机器人传感器数据
2. 基于变化检测触发L0数据持久化
3. 集成YOLO-World和CLIP进行开放词汇场景图生成
4. 实现Socratic Models方法(论文1中的技术)
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import numpy as np
from PIL import Image
from loguru import logger

from agentscope.message import Msg
from .base_agent import BaseMemoryAgent
from em.em_tree import RawDataInstant, SceneGraphInstant, ObjectNode


class PerceptionWorkerAgent(BaseMemoryAgent):
    """
    感知工作Agent - 处理传感器数据并生成场景图
    
    对应H-EMV论文中的:
    - YOLO-World开放词汇目标检测
    - CLIP文本嵌入检索
    - Socratic Models动态类别生成
    """
    
    def __init__(
        self,
        name: str = "PerceptionWorker",
        model_config_name: Optional[str] = None,
        storage_backends: Optional[Dict] = None,
        yolo_model=None,  # YOLO-World模型
        clip_model=None,  # CLIP模型
        lvis_classes_path: str = "em/lvis_val_100_classes.json",
        change_detection_threshold: float = 0.3,
        **kwargs
    ):
        """
        初始化感知工作Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置名称(用于Socratic Models)
            storage_backends: 存储后端
            yolo_model: YOLO-World模型实例
            clip_model: CLIP模型实例
            lvis_classes_path: LVIS类别库路径
            change_detection_threshold: 场景变化检测阈值
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            storage_backends=storage_backends,
            **kwargs
        )
        
        self.yolo_model = yolo_model
        self.clip_model = clip_model
        self.lvis_classes_path = lvis_classes_path
        self.change_threshold = change_detection_threshold
        
        # 加载LVIS类别库
        self.lvis_classes = self._load_lvis_classes()
        
        # 记录上一次的场景图(用于变化检测)
        self.last_scene_graph: Optional[SceneGraphInstant] = None
        
        logger.info(f"[{self.name}] Initialized with YOLO+CLIP")
    
    def _load_lvis_classes(self) -> List[str]:
        """加载LVIS类别库"""
        import json
        from pathlib import Path
        
        try:
            path = Path(self.lvis_classes_path)
            if path.exists():
                with open(path, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"LVIS classes file not found: {self.lvis_classes_path}")
                return []
        except Exception as e:
            logger.error(f"Failed to load LVIS classes: {e}")
            return []
    
    def reply(self, x: Optional[Msg] = None) -> Msg:
        """
        处理传感器数据消息
        
        输入消息格式:
        {
            "type": "sensor_data",
            "image": PIL.Image,
            "sound": np.ndarray (可选),
            "asr_recognition": str (可选),
            "current_action": str,
            "current_action_state": str,
            "current_action_parameters": dict (可选),
            "current_goal": str (可选),
            "timestamp": datetime
        }
        
        返回消息格式:
        {
            "type": "perception_result",
            "scene_graph": SceneGraphInstant,
            "state_changed": bool,
            "l0_node_id": str,
            "l1_node_id": str
        }
        """
        try:
            if x is None or x.content.get("type") != "sensor_data":
                return self.handle_error(
                    ValueError("Invalid message type"),
                    {"expected": "sensor_data", "received": x.content.get("type") if x else None}
                )
            
            # 1. 创建L0原始数据节点
            l0_node = self._create_raw_instant(x.content)
            
            # 2. 生成场景图(L1)
            scene_graph = self._generate_scene_graph(l0_node, x.content.get("current_goal"))
            
            # 3. 变化检测
            state_changed = self._detect_state_change(scene_graph)
            
            # 4. 如果有变化,持久化L0数据
            l0_node_id = None
            if state_changed:
                l0_node_id = self._persist_l0_node(l0_node)
                self.log_access(l0_node_id, "write", {"has_image": l0_node.image is not None})
            
            # 5. 持久化L1场景图
            l1_node_id = self._persist_scene_graph(scene_graph, l0_node_id)
            self.log_access(l1_node_id, "write")
            
            # 6. 更新上一次场景图
            self.last_scene_graph = scene_graph
            
            # 7. 如果状态变化,向Event Aggregator发送通知
            if state_changed:
                logger.info(f"[{self.name}] State change detected, notifying Event Aggregator")
            
            return self.create_success_msg({
                "scene_graph": scene_graph,
                "state_changed": state_changed,
                "l0_node_id": l0_node_id,
                "l1_node_id": l1_node_id,
                "objects_detected": len(scene_graph.objects)
            })
            
        except Exception as e:
            return self.handle_error(e, {"input": str(x)[:200]})
    
    def _create_raw_instant(self, data: Dict[str, Any]) -> RawDataInstant:
        """从传感器数据创建L0原始数据节点"""
        return RawDataInstant(
            timestamp=data.get("timestamp", datetime.now()),
            image=data.get("image"),
            sound=data.get("sound"),
            asr_recognition=data.get("asr_recognition"),
            current_action=data.get("current_action"),
            current_action_state=data.get("current_action_state"),
            current_action_parameters=data.get("current_action_parameters"),
            current_goal=data.get("current_goal"),
            current_goal_state=data.get("current_goal_state")
        )
    
    def _generate_scene_graph(
        self, 
        raw: RawDataInstant, 
        current_goal: Optional[str] = None
    ) -> SceneGraphInstant:
        """
        生成场景图 - 实现Socratic Models方法
        
        论文1中的流程:
        1. CLIP检索LVIS前100类别
        2. 结合L3目标,用Llama-3生成潜在物体列表
        3. YOLO-World进行开放词汇检测
        
        Args:
            raw: L0原始数据
            current_goal: 当前目标描述(可选,用于引导检测)
            
        Returns:
            SceneGraphInstant: 场景图
        """
        objects = []
        relations = []
        
        if raw.image is None:
            # 没有图像,返回空场景图
            return SceneGraphInstant(objects=[], relations=[], raw=raw)
        
        try:
            # Step 1: CLIP检索相关类别
            relevant_classes = self._clip_retrieve_classes(raw.image, current_goal)
            
            # Step 2: YOLO-World检测
            detections = self._yolo_detect(raw.image, relevant_classes)
            
            # Step 3: 构建ObjectNode
            for i, det in enumerate(detections):
                obj_node = ObjectNode(
                    obj_class=det["class"],
                    instance_id=f"{det['class']}_{i}",
                    state=det.get("state")  # 可选的物体状态
                )
                objects.append(obj_node)
            
            # Step 4: 提取空间关系(简化版)
            relations = self._extract_spatial_relations(detections)
            
        except Exception as e:
            logger.error(f"[{self.name}] Scene graph generation failed: {e}")
            # 即使失败也返回空场景图,而非崩溃
        
        return SceneGraphInstant(objects=objects, relations=relations, raw=raw)
    
    def _clip_retrieve_classes(
        self, 
        image: Image.Image, 
        goal: Optional[str] = None,
        top_k: int = 100
    ) -> List[str]:
        """
        使用CLIP检索最相关的LVIS类别
        
        Args:
            image: 输入图像
            goal: 当前目标(可用于增强检索)
            top_k: 返回前k个类别
            
        Returns:
            List[str]: 相关类别列表
        """
        if self.clip_model is None or not self.lvis_classes:
            # 如果没有CLIP模型,返回默认类别
            return ["object", "furniture", "container", "tool"]
        
        try:
            # 这里应该调用实际的CLIP模型
            # 示例代码 - 实际实现需要根据您的CLIP接口调整
            # image_features = self.clip_model.encode_image(image)
            # text_features = self.clip_model.encode_text(self.lvis_classes)
            # similarities = cosine_similarity(image_features, text_features)
            # top_indices = np.argsort(similarities)[-top_k:]
            # return [self.lvis_classes[i] for i in top_indices]
            
            # 占位符实现
            logger.debug(f"[{self.name}] CLIP retrieval (placeholder)")
            return self.lvis_classes[:top_k]
            
        except Exception as e:
            logger.error(f"CLIP retrieval failed: {e}")
            return self.lvis_classes[:top_k]
    
    def _yolo_detect(
        self, 
        image: Image.Image, 
        classes: List[str]
    ) -> List[Dict[str, Any]]:
        """
        YOLO-World开放词汇检测
        
        Args:
            image: 输入图像
            classes: 候选类别列表
            
        Returns:
            List[Dict]: 检测结果 [{"class": str, "bbox": [x1,y1,x2,y2], "confidence": float}, ...]
        """
        if self.yolo_model is None:
            # 占位符实现
            logger.debug(f"[{self.name}] YOLO detection (placeholder)")
            return []
        
        try:
            # 实际的YOLO-World调用
            # detections = self.yolo_model.predict(image, classes=classes)
            # return detections
            
            # 占位符
            return []
            
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            return []
    
    def _extract_spatial_relations(
        self, 
        detections: List[Dict[str, Any]]
    ) -> List[Tuple[int, int, str]]:
        """
        从检测结果提取空间关系
        
        Args:
            detections: YOLO检测结果
            
        Returns:
            List[Tuple]: 关系列表 [(obj1_idx, obj2_idx, relation_type), ...]
        """
        relations = []
        
        # 简化版:只检测"on"关系(通过bbox垂直位置判断)
        for i, det1 in enumerate(detections):
            for j, det2 in enumerate(detections):
                if i != j:
                    # 如果det1的底部接近det2的顶部,则判定为"on"关系
                    bbox1 = det1.get("bbox", [0, 0, 0, 0])
                    bbox2 = det2.get("bbox", [0, 0, 0, 0])
                    
                    if len(bbox1) == 4 and len(bbox2) == 4:
                        y1_bottom = bbox1[3]
                        y2_top = bbox2[1]
                        
                        if abs(y1_bottom - y2_top) < 20:  # 阈值20像素
                            relations.append((i, j, "on"))
        
        return relations
    
    def _detect_state_change(self, current_graph: SceneGraphInstant) -> bool:
        """
        检测场景状态是否发生显著变化
        
        检测规则:
        1. 物体数量变化
        2. 物体类别变化
        3. 空间关系拓扑变化
        4. 动作状态转换
        
        Args:
            current_graph: 当前场景图
            
        Returns:
            bool: 是否发生变化
        """
        if self.last_scene_graph is None:
            # 第一次,算作变化
            return True
        
        last = self.last_scene_graph
        curr = current_graph
        
        # 1. 物体数量变化
        if len(last.objects) != len(curr.objects):
            logger.debug(f"[{self.name}] Object count changed: {len(last.objects)} -> {len(curr.objects)}")
            return True
        
        # 2. 物体类别集合变化
        last_classes = set(obj.obj_class for obj in last.objects)
        curr_classes = set(obj.obj_class for obj in curr.objects)
        if last_classes != curr_classes:
            logger.debug(f"[{self.name}] Object classes changed")
            return True
        
        # 3. 关系数量显著变化
        if abs(len(last.relations) - len(curr.relations)) > 2:
            logger.debug(f"[{self.name}] Spatial relations changed significantly")
            return True
        
        # 4. 动作状态转换
        if last.raw.current_action_state != curr.raw.current_action_state:
            logger.debug(f"[{self.name}] Action state changed: {last.raw.current_action_state} -> {curr.raw.current_action_state}")
            return True
        
        # 5. 语音指令出现
        if curr.raw.asr_recognition and curr.raw.asr_recognition != last.raw.asr_recognition:
            logger.debug(f"[{self.name}] New speech command detected")
            return True
        
        return False
    
    def _persist_l0_node(self, l0_node: RawDataInstant) -> str:
        """
        持久化L0原始数据到对象存储(MinIO)
        
        Args:
            l0_node: L0节点
            
        Returns:
            str: 节点ID
        """
        object_store = self.get_object_store()
        if object_store is None:
            logger.warning("Object store not configured, L0 data not persisted")
            return f"l0_{int(l0_node.timestamp.timestamp())}"
        
        try:
            node_id = f"l0_{int(l0_node.timestamp.timestamp())}"
            
            # 存储图像
            if l0_node.image:
                image_path = f"raw/{l0_node.timestamp.strftime('%Y/%m/%d')}/{node_id}.jpg"
                object_store.put_image(image_path, l0_node.image)
            
            # 存储音频
            if l0_node.sound is not None:
                audio_path = f"raw/{l0_node.timestamp.strftime('%Y/%m/%d')}/{node_id}.wav"
                object_store.put_audio(audio_path, l0_node.sound)
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to persist L0 node: {e}")
            return f"l0_{int(l0_node.timestamp.timestamp())}"
    
    def _persist_scene_graph(
        self, 
        scene_graph: SceneGraphInstant, 
        l0_node_id: Optional[str]
    ) -> str:
        """
        持久化L1场景图到向量数据库
        
        Args:
            scene_graph: 场景图
            l0_node_id: 对应的L0节点ID
            
        Returns:
            str: L1节点ID
        """
        vector_store = self.get_vector_store()
        graph_store = self.get_graph_store()
        
        node_id = f"l1_{int(scene_graph.raw.timestamp.timestamp())}"
        
        # 1. 向量数据库存储(用于语义检索)
        if vector_store:
            try:
                # 获取场景图的文本表示
                nl_summary = scene_graph.nl_graph_summary
                
                vector_store.insert({
                    "node_id": node_id,
                    "level": "L1",
                    "nl_summary": nl_summary,
                    "timestamp_start": int(scene_graph.raw.timestamp.timestamp()),
                    "timestamp_end": int(scene_graph.raw.timestamp.timestamp()),
                    "utility_score": 0.5,  # 初始效用分
                    "is_locked": False,
                    "l0_reference": l0_node_id
                })
            except Exception as e:
                logger.error(f"Failed to insert to vector store: {e}")
        
        # 2. 图数据库存储(用于树结构)
        if graph_store and l0_node_id:
            try:
                graph_store.create_node("L1Node", node_id, {
                    "nl_summary": scene_graph.nl_graph_summary,
                    "timestamp": scene_graph.raw.timestamp.isoformat()
                })
                graph_store.create_relation(node_id, l0_node_id, "CONTAINS")
            except Exception as e:
                logger.error(f"Failed to insert to graph store: {e}")
        
        return node_id

