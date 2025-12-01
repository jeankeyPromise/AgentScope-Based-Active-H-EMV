"""
CorrectionAgent - 修正Agent (增强版)

支持三级置信度驱动的修正策略：
1. 高置信度：直接采用用户纠正
2. 中置信度：VLM验证但优先用户
3. 低置信度：强制VLM验证
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger

from agentscope.agent import AgentBase
from agentscope.message import Msg
from em.em_tree import HigherLevelSummary


class CorrectionAgentEnhanced(AgentBase):
    """
    增强版修正Agent - 智能选择验证策略
    """
    
    def __init__(
        self,
        name: str = "CorrectionAgent",
        model_config_name: str = "gpt-4o",
        vlm_config_name: Optional[str] = "gpt-4o-vision",  # VLM配置
        confidence_threshold_high: float = 0.9,
        confidence_threshold_low: float = 0.5,
        enable_vlm_verification: bool = True,  # 是否启用VLM验证
        **kwargs
    ):
        """
        初始化增强版修正Agent
        
        Args:
            name: Agent名称
            model_config_name: LLM配置
            vlm_config_name: VLM配置（用于图像验证）
            confidence_threshold_high: 高置信度阈值
            confidence_threshold_low: 低置信度阈值
            enable_vlm_verification: 是否启用VLM验证
        """
        super().__init__(
            name=name,
            model_config_name=model_config_name,
            **kwargs
        )
        
        self.vlm_config_name = vlm_config_name
        self.confidence_threshold_high = confidence_threshold_high
        self.confidence_threshold_low = confidence_threshold_low
        self.enable_vlm_verification = enable_vlm_verification
        
        # VLM模型（延迟加载）
        self.vlm_model = None
        
        # 用户历史准确率跟踪
        self.user_correction_history = []
        
        # 统计信息
        self.stats = {
            "total_corrections": 0,
            "direct_corrections": 0,      # 直接采用用户纠正
            "vlm_verified": 0,            # VLM验证
            "user_vlm_conflicts": 0,      # 用户和VLM冲突
            "vlm_api_calls": 0,           # VLM调用次数
            "vlm_cost_usd": 0.0           # VLM成本
        }
        
        logger.info(f"[{self.name}] Enhanced CorrectionAgent initialized")
    
    def _assess_correction_confidence(
        self,
        error_node: Any,
        user_correction: str,
        query: str
    ) -> float:
        """
        评估用户纠正的置信度
        
        Returns:
            float: 置信度分数 [0, 1]
        """
        confidence = 0.5  # 基础值
        
        # 因素1: 时间间隔（越近越可信）
        try:
            if hasattr(error_node, 'raw') and hasattr(error_node.raw, 'timestamp'):
                time_gap = datetime.now() - error_node.raw.timestamp
                
                if time_gap < timedelta(hours=1):
                    confidence += 0.3
                    logger.debug("Time gap < 1 hour, +0.3 confidence")
                elif time_gap < timedelta(days=1):
                    confidence += 0.2
                    logger.debug("Time gap < 1 day, +0.2 confidence")
                elif time_gap < timedelta(weeks=1):
                    confidence += 0.1
                    logger.debug("Time gap < 1 week, +0.1 confidence")
        except:
            pass
        
        # 因素2: 用户历史准确率
        user_accuracy = self._get_user_accuracy()
        if user_accuracy > 0.9:
            confidence += 0.2
            logger.debug(f"High user accuracy {user_accuracy:.2f}, +0.2 confidence")
        elif user_accuracy > 0.7:
            confidence += 0.1
            logger.debug(f"Good user accuracy {user_accuracy:.2f}, +0.1 confidence")
        
        # 因素3: 纠正的具体性
        if self._is_specific_correction(user_correction):
            confidence += 0.1
            logger.debug("Specific correction, +0.1 confidence")
        
        # 因素4: 原VLM置信度（如果有）
        if hasattr(error_node, 'vlm_confidence'):
            if error_node.vlm_confidence < 0.5:
                confidence += 0.1
                logger.debug(f"Low VLM confidence {error_node.vlm_confidence:.2f}, +0.1 confidence")
        
        return min(confidence, 1.0)
    
    def _is_specific_correction(self, correction: str) -> bool:
        """判断纠正是否具体"""
        # 具体的纠正通常包含颜色、形状等细节
        specific_keywords = ['青', '红', '黄', '绿', '蓝', '大', '小', '圆', '方']
        return any(kw in correction for kw in specific_keywords)
    
    def _get_user_accuracy(self) -> float:
        """获取用户历史准确率"""
        if not self.user_correction_history:
            return 0.8  # 默认假设用户较可信
        
        correct = sum(1 for item in self.user_correction_history if item['verified'])
        total = len(self.user_correction_history)
        return correct / total if total > 0 else 0.8
    
    def _apply_direct_correction(
        self,
        error_node: Any,
        user_correction: str
    ) -> Dict[str, Any]:
        """
        直接应用用户纠正（高置信度策略）
        """
        logger.info(f"[{self.name}] Applying direct correction (high confidence)")
        
        original_summary = getattr(error_node, 'nl_summary', '')
        
        # 使用LLM生成修正后的描述
        corrected_summary = self._generate_corrected_summary(
            original_summary, user_correction
        )
        
        # 更新节点
        error_node.nl_summary = corrected_summary
        self._add_correction_history(error_node, user_correction, "direct")
        
        self.stats["direct_corrections"] += 1
        
        return {
            "success": True,
            "method": "direct",
            "corrected_summary": corrected_summary
        }
    
    def _apply_with_vlm_verification(
        self,
        error_node: Any,
        user_correction: str,
        priority: str = "user"  # "user" or "vlm"
    ) -> Dict[str, Any]:
        """
        使用VLM验证后修正（中/低置信度策略）
        """
        logger.info(f"[{self.name}] Verifying with VLM (priority={priority})")
        
        # 调用VLM重新识别
        vlm_result = self._call_vlm(error_node)
        self.stats["vlm_verified"] += 1
        self.stats["vlm_api_calls"] += 1
        self.stats["vlm_cost_usd"] += 0.02  # 假设每次$0.02
        
        if not vlm_result:
            logger.warning("VLM verification failed, falling back to user correction")
            return self._apply_direct_correction(error_node, user_correction)
        
        # 比较VLM结果和用户纠正
        if self._is_consistent(vlm_result, user_correction):
            # 一致：采用（增强用户信誉）
            logger.info("VLM confirms user correction")
            self._record_user_correction(True)
            return self._apply_direct_correction(error_node, user_correction)
        
        else:
            # 冲突：根据优先级决定
            logger.warning(f"Conflict: VLM says '{vlm_result}', user says '{user_correction}'")
            self.stats["user_vlm_conflicts"] += 1
            
            if priority == "user":
                # 优先用户（中置信度）
                logger.info("Using user correction (user priority)")
                self._add_correction_history(
                    error_node, user_correction, "user_priority",
                    vlm_result=vlm_result
                )
                return self._apply_direct_correction(error_node, user_correction)
            
            else:
                # 优先VLM（低置信度）
                logger.info("Using VLM result (vlm priority)")
                self._add_correction_history(
                    error_node, vlm_result, "vlm_verified",
                    user_input=user_correction
                )
                return self._apply_direct_correction(error_node, vlm_result)
    
    def _call_vlm(self, error_node: Any) -> Optional[str]:
        """
        调用VLM重新识别图像
        
        Returns:
            str: VLM识别结果，例如 "青苹果"
        """
        if not self.enable_vlm_verification:
            logger.warning("VLM verification disabled")
            return None
        
        # 获取原始图像
        if not hasattr(error_node, 'raw') or not hasattr(error_node.raw, 'image'):
            logger.warning("No raw image available for VLM verification")
            return None
        
        image = error_node.raw.image
        if image is None:
            logger.warning("Raw image data is None (may have been forgotten)")
            return None
        
        # 调用VLM（简化实现）
        try:
            # 实际实现需要调用VLM API
            # 这里是伪代码
            logger.info("Calling VLM API...")
            
            # prompt = "请识别图中的物体，给出具体名称和颜色"
            # vlm_result = vlm_api.analyze(image, prompt)
            
            # 模拟返回
            vlm_result = "青苹果"  # 实际应该调用真实VLM
            
            logger.info(f"VLM result: {vlm_result}")
            return vlm_result
            
        except Exception as e:
            logger.error(f"VLM call failed: {e}")
            return None
    
    def _is_consistent(self, vlm_result: str, user_correction: str) -> bool:
        """判断VLM结果和用户纠正是否一致"""
        # 简化的一致性检查（实际应该用语义相似度）
        return vlm_result.lower() in user_correction.lower() or \
               user_correction.lower() in vlm_result.lower()
    
    def _generate_corrected_summary(
        self,
        original: str,
        correction: str
    ) -> str:
        """生成修正后的摘要"""
        if not hasattr(self, 'model') or self.model is None:
            return f"[已修正] {correction}"
        
        try:
            prompt = f"""
原始描述: {original}
用户纠正: {correction}

请生成修正后的描述，要求：
1. 保留原描述中的正确部分
2. 根据纠正修改错误部分
3. 保持流畅自然

修正后的描述:
"""
            response = self.model.generate(prompt)
            return response.strip()
        except:
            return f"[已修正] {correction}"
    
    def _add_correction_history(
        self,
        node: Any,
        correction: str,
        method: str,
        **kwargs
    ):
        """添加修正历史"""
        if not hasattr(node, 'correction_history'):
            node.correction_history = []
        
        node.correction_history.append({
            "timestamp": datetime.now(),
            "correction": correction,
            "method": method,
            **kwargs
        })
    
    def _record_user_correction(self, verified: bool):
        """记录用户纠正的验证结果"""
        self.user_correction_history.append({
            "timestamp": datetime.now(),
            "verified": verified
        })
        
        # 只保留最近100条
        if len(self.user_correction_history) > 100:
            self.user_correction_history = self.user_correction_history[-100:]
    
    def correct_memory(
        self,
        memory_tree: HigherLevelSummary,
        query: str,
        system_answer: str,
        user_correction: str
    ) -> Dict[str, Any]:
        """
        智能修正记忆
        
        根据置信度自动选择策略
        """
        self.stats["total_corrections"] += 1
        
        # 1. 定位错误节点
        error_node = self._locate_error_node(
            memory_tree, query, system_answer, user_correction
        )
        
        if error_node is None:
            return {
                "success": False,
                "reason": "无法定位错误节点"
            }
        
        # 2. 评估置信度
        confidence = self._assess_correction_confidence(
            error_node, user_correction, query
        )
        
        logger.info(f"[{self.name}] Correction confidence: {confidence:.2f}")
        
        # 3. 根据置信度选择策略
        if confidence >= self.confidence_threshold_high:
            # 高置信度：直接采用
            result = self._apply_direct_correction(error_node, user_correction)
            
        elif confidence >= self.confidence_threshold_low:
            # 中置信度：VLM验证，优先用户
            result = self._apply_with_vlm_verification(
                error_node, user_correction, priority="user"
            )
            
        else:
            # 低置信度：VLM验证，优先VLM
            result = self._apply_with_vlm_verification(
                error_node, user_correction, priority="vlm"
            )
        
        # 4. 级联更新父节点
        if result["success"]:
            affected_nodes = self._propagate_update(memory_tree, error_node)
            result["nodes_updated"] = 1 + len(affected_nodes)
        
        return result
    
    def _locate_error_node(self, tree, query, answer, correction):
        """定位错误节点（简化实现）"""
        # 实际实现参考原correction_agent.py
        return tree  # 临时返回根节点
    
    def _propagate_update(self, tree, node):
        """级联更新（简化实现）"""
        # 实际实现参考原correction_agent.py
        return []

