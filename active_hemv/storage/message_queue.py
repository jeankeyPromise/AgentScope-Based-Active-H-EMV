"""
消息队列层 - Active-H-EMV 系统
处理 Agent 之间的异步通信（使用 Redis）
"""

from typing import Optional, Any, List
from abc import ABC, abstractmethod
import json
from loguru import logger


class MessageQueue(ABC):
    """消息队列抽象基类"""
    
    @abstractmethod
    def publish(self, channel: str, message: Any) -> bool:
        """发布消息到频道"""
        pass
    
    @abstractmethod
    def subscribe(self, channel: str) -> Any:
        """订阅频道"""
        pass
    
    @abstractmethod
    def push(self, queue_name: str, message: Any) -> bool:
        """推送消息到队列"""
        pass
    
    @abstractmethod
    def pop(self, queue_name: str, timeout: int = 0) -> Optional[Any]:
        """从队列弹出消息"""
        pass


class RedisMessageQueue(MessageQueue):
    """Redis 消息队列实现"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None
    ):
        """
        初始化 Redis 连接
        
        Args:
            host: Redis 主机地址
            port: Redis 端口
            db: Redis 数据库编号
            password: Redis 密码（如果需要）
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self._client = None
        
        try:
            import redis
            self._client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True
            )
            self._client.ping()
            logger.info(f"已连接到 Redis: {host}:{port}")
        except ImportError:
            logger.warning("未安装 redis 包，消息队列操作将被跳过")
        except Exception as e:
            logger.warning(f"连接 Redis 失败: {e}，消息队列操作将被跳过")
    
    def publish(self, channel: str, message: Any) -> bool:
        """发布消息到频道"""
        if not self._client:
            logger.warning("Redis 不可用，跳过 publish")
            return False
        
        try:
            message_str = json.dumps(message) if not isinstance(message, str) else message
            self._client.publish(channel, message_str)
            logger.debug(f"已发布消息到频道 {channel}")
            return True
        except Exception as e:
            logger.error(f"发布消息到频道 {channel} 失败: {e}")
            return False
    
    def subscribe(self, channel: str) -> Any:
        """订阅频道并返回 pubsub 对象"""
        if not self._client:
            logger.warning("Redis 不可用，无法订阅")
            return None
        
        try:
            pubsub = self._client.pubsub()
            pubsub.subscribe(channel)
            logger.debug(f"已订阅频道 {channel}")
            return pubsub
        except Exception as e:
            logger.error(f"订阅频道 {channel} 失败: {e}")
            return None
    
    def push(self, queue_name: str, message: Any) -> bool:
        """推送消息到队列（列表）"""
        if not self._client:
            logger.warning("Redis 不可用，跳过 push")
            return False
        
        try:
            message_str = json.dumps(message) if not isinstance(message, str) else message
            self._client.rpush(queue_name, message_str)
            logger.debug(f"已推送消息到队列 {queue_name}")
            return True
        except Exception as e:
            logger.error(f"推送消息到队列 {queue_name} 失败: {e}")
            return False
    
    def pop(self, queue_name: str, timeout: int = 0) -> Optional[Any]:
        """从队列弹出消息（如果 timeout > 0 则阻塞等待）"""
        if not self._client:
            return None
        
        try:
            if timeout > 0:
                result = self._client.blpop(queue_name, timeout=timeout)
                if result:
                    _, message = result
                    return json.loads(message) if message.startswith('{') or message.startswith('[') else message
            else:
                message = self._client.lpop(queue_name)
                if message:
                    return json.loads(message) if message.startswith('{') or message.startswith('[') else message
            return None
        except Exception as e:
            logger.error(f"从队列 {queue_name} 弹出消息失败: {e}")
            return None
    
    def queue_length(self, queue_name: str) -> int:
        """获取队列长度"""
        if not self._client:
            return 0
        
        try:
            return self._client.llen(queue_name)
        except Exception as e:
            logger.error(f"获取队列 {queue_name} 长度失败: {e}")
            return 0
    
    def clear_queue(self, queue_name: str) -> bool:
        """清空队列中的所有消息"""
        if not self._client:
            return False
        
        try:
            self._client.delete(queue_name)
            logger.debug(f"已清空队列 {queue_name}")
            return True
        except Exception as e:
            logger.error(f"清空队列 {queue_name} 失败: {e}")
            return False

