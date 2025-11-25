"""
对象存储层 - Active-H-EMV 系统
用于存储 L0 原始图像/音频数据（使用 MinIO）
"""

from typing import Optional, BinaryIO
from abc import ABC, abstractmethod
from io import BytesIO
from loguru import logger


class ObjectStore(ABC):
    """对象存储抽象基类"""
    
    @abstractmethod
    def put_object(self, bucket: str, object_name: str, data: bytes) -> bool:
        """存储对象"""
        pass
    
    @abstractmethod
    def get_object(self, bucket: str, object_name: str) -> Optional[bytes]:
        """获取对象"""
        pass
    
    @abstractmethod
    def delete_object(self, bucket: str, object_name: str) -> bool:
        """删除对象"""
        pass
    
    @abstractmethod
    def object_exists(self, bucket: str, object_name: str) -> bool:
        """检查对象是否存在"""
        pass


class MinIOObjectStore(ObjectStore):
    """MinIO 对象存储实现"""
    
    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        secure: bool = False
    ):
        """
        初始化 MinIO 客户端
        
        Args:
            endpoint: MinIO 服务器地址
            access_key: 访问密钥
            secret_key: 私密密钥
            secure: 是否使用 HTTPS
        """
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self._client = None
        
        try:
            from minio import Minio
            self._client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            logger.info(f"已连接到 MinIO: {endpoint}")
        except ImportError:
            logger.warning("未安装 minio 包，对象存储操作将被跳过")
        except Exception as e:
            logger.warning(f"连接 MinIO 失败: {e}，对象存储操作将被跳过")
    
    def _ensure_bucket(self, bucket: str) -> bool:
        """确保存储桶存在，不存在则创建"""
        if not self._client:
            return False
        
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                logger.info(f"已创建存储桶: {bucket}")
            return True
        except Exception as e:
            logger.error(f"确保存储桶 {bucket} 失败: {e}")
            return False
    
    def put_object(self, bucket: str, object_name: str, data: bytes) -> bool:
        """存储对象"""
        if not self._client:
            logger.warning("MinIO 不可用，跳过 put_object")
            return False
        
        try:
            self._ensure_bucket(bucket)
            data_stream = BytesIO(data)
            self._client.put_object(
                bucket,
                object_name,
                data_stream,
                length=len(data)
            )
            logger.debug(f"已存储对象 {bucket}/{object_name} ({len(data)} 字节)")
            return True
        except Exception as e:
            logger.error(f"存储对象 {bucket}/{object_name} 失败: {e}")
            return False
    
    def get_object(self, bucket: str, object_name: str) -> Optional[bytes]:
        """获取对象"""
        if not self._client:
            return None
        
        try:
            response = self._client.get_object(bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.debug(f"已获取对象 {bucket}/{object_name} ({len(data)} 字节)")
            return data
        except Exception as e:
            logger.error(f"获取对象 {bucket}/{object_name} 失败: {e}")
            return None
    
    def delete_object(self, bucket: str, object_name: str) -> bool:
        """删除对象"""
        if not self._client:
            logger.warning("MinIO 不可用，跳过 delete_object")
            return False
        
        try:
            self._client.remove_object(bucket, object_name)
            logger.debug(f"已删除对象 {bucket}/{object_name}")
            return True
        except Exception as e:
            logger.error(f"删除对象 {bucket}/{object_name} 失败: {e}")
            return False
    
    def object_exists(self, bucket: str, object_name: str) -> bool:
        """检查对象是否存在"""
        if not self._client:
            return False
        
        try:
            self._client.stat_object(bucket, object_name)
            return True
        except Exception:
            return False
    
    def list_objects(self, bucket: str, prefix: str = "") -> list:
        """列出存储桶中的对象"""
        if not self._client:
            return []
        
        try:
            objects = self._client.list_objects(bucket, prefix=prefix)
            return [obj.object_name for obj in objects]
        except Exception as e:
            logger.error(f"列出存储桶 {bucket} 中的对象失败: {e}")
            return []

