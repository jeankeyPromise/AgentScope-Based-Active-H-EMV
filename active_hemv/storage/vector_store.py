"""
向量数据库接口 - 用于语义检索

支持:
- Milvus (推荐,企业级)
- Chroma (轻量级,开发用)
"""

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from loguru import logger
import numpy as np


class VectorStore(ABC):
    """向量数据库抽象基类"""
    
    @abstractmethod
    def insert(self, data: Dict[str, Any]):
        """
        插入单个节点
        
        Args:
            data: 节点数据,至少包含:
                - node_id: str
                - level: str (L0/L1/L2/L3/L4+)
                - nl_summary: str
                - embedding: np.ndarray或自动生成
                - timestamp_start: int
                - timestamp_end: int
                - utility_score: float
                - is_locked: bool
        """
        pass
    
    @abstractmethod
    def search(
        self, 
        query: str, 
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            top_k: 返回前k个结果
            filters: 过滤条件,如 {"level": "L2", "timestamp_start": (">", timestamp)}
            
        Returns:
            List[Dict]: 搜索结果,每个dict包含节点所有字段+similarity分数
        """
        pass
    
    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict]:
        """根据ID获取节点"""
        pass
    
    @abstractmethod
    def update(self, node_id: str, updates: Dict[str, Any]):
        """更新节点字段"""
        pass
    
    @abstractmethod
    def delete(self, node_id: str):
        """删除节点"""
        pass
    
    @abstractmethod
    def get_all_nodes(self, limit: int = 1000) -> List[Dict]:
        """获取所有节点(用于遗忘周期)"""
        pass
    
    @abstractmethod
    def update_access_count(self, node_id: str):
        """更新访问计数(用于效用函数)"""
        pass


class MilvusVectorStore(VectorStore):
    """
    Milvus向量数据库实现
    
    Schema:
    - node_id (VARCHAR, primary_key)
    - level (VARCHAR)
    - embedding (FLOAT_VECTOR, dim=768)
    - nl_summary (VARCHAR)
    - timestamp_start (INT64)
    - timestamp_end (INT64)
    - utility_score (FLOAT)
    - is_locked (BOOL)
    - access_count (INT64)
    - last_accessed (INT64)
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "memory_nodes",
        embedding_model=None,  # SentenceTransformer实例
        embedding_dim: int = 768
    ):
        """
        初始化Milvus连接
        
        Args:
            host: Milvus服务器地址
            port: Milvus端口
            collection_name: 集合名称
            embedding_model: 文本嵌入模型
            embedding_dim: 嵌入向量维度
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        
        try:
            from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType
            self._milvus_available = True
            self._Collection = Collection
            self._DataType = DataType
            self._FieldSchema = FieldSchema
            self._CollectionSchema = CollectionSchema
        except ImportError:
            logger.warning("pymilvus not installed, MilvusVectorStore will not work")
            self._milvus_available = False
            return
        
        # 连接到Milvus
        try:
            connections.connect(
                alias="default",
                host=host,
                port=port
            )
            logger.info(f"Connected to Milvus at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            self._milvus_available = False
            return
        
        # 创建或加载集合
        self._init_collection()
    
    def _init_collection(self):
        """初始化Milvus集合"""
        from pymilvus import utility
        
        if utility.has_collection(self.collection_name):
            self.collection = self._Collection(self.collection_name)
            logger.info(f"Loaded existing collection: {self.collection_name}")
        else:
            # 创建新集合
            fields = [
                self._FieldSchema(name="node_id", dtype=self._DataType.VARCHAR, is_primary=True, max_length=100),
                self._FieldSchema(name="level", dtype=self._DataType.VARCHAR, max_length=10),
                self._FieldSchema(name="embedding", dtype=self._DataType.FLOAT_VECTOR, dim=self.embedding_dim),
                self._FieldSchema(name="nl_summary", dtype=self._DataType.VARCHAR, max_length=2000),
                self._FieldSchema(name="timestamp_start", dtype=self._DataType.INT64),
                self._FieldSchema(name="timestamp_end", dtype=self._DataType.INT64),
                self._FieldSchema(name="utility_score", dtype=self._DataType.FLOAT),
                self._FieldSchema(name="is_locked", dtype=self._DataType.BOOL),
                self._FieldSchema(name="access_count", dtype=self._DataType.INT64),
                self._FieldSchema(name="last_accessed", dtype=self._DataType.INT64)
            ]
            
            schema = self._CollectionSchema(
                fields=fields,
                description="Active-H-EMV memory nodes"
            )
            
            self.collection = self._Collection(
                name=self.collection_name,
                schema=schema
            )
            
            # 创建索引
            index_params = {
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 128}
            }
            self.collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            
            logger.info(f"Created new collection: {self.collection_name}")
        
        # 加载到内存
        self.collection.load()
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """获取文本嵌入"""
        if self.embedding_model is None:
            # 返回随机向量作为占位符
            logger.warning("Embedding model not configured, using random vectors")
            return np.random.rand(self.embedding_dim).astype(np.float32)
        
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return np.random.rand(self.embedding_dim).astype(np.float32)
    
    def insert(self, data: Dict[str, Any]):
        """插入节点"""
        if not self._milvus_available:
            logger.warning("Milvus not available, skipping insert")
            return
        
        try:
            # 生成嵌入(如果没有提供)
            if "embedding" not in data:
                data["embedding"] = self._get_embedding(data["nl_summary"])
            
            # 设置默认值
            data.setdefault("access_count", 0)
            data.setdefault("last_accessed", 0)
            
            # 插入
            entities = [[data[field.name] for field in self.collection.schema.fields]]
            self.collection.insert(entities)
            self.collection.flush()
            
            logger.debug(f"Inserted node {data['node_id']}")
            
        except Exception as e:
            logger.error(f"Failed to insert node: {e}")
    
    def search(
        self, 
        query: str, 
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """语义搜索"""
        if not self._milvus_available:
            return []
        
        try:
            # 生成查询嵌入
            query_embedding = self._get_embedding(query)
            
            # 构建过滤表达式
            filter_expr = self._build_filter_expr(filters) if filters else None
            
            # 搜索
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=list(self.collection.schema.fields.keys())
            )
            
            # 转换结果
            output = []
            for hits in results:
                for hit in hits:
                    output.append({
                        "node_id": hit.entity.get("node_id"),
                        "level": hit.entity.get("level"),
                        "nl_summary": hit.entity.get("nl_summary"),
                        "timestamp_start": hit.entity.get("timestamp_start"),
                        "timestamp_end": hit.entity.get("timestamp_end"),
                        "utility_score": hit.entity.get("utility_score"),
                        "is_locked": hit.entity.get("is_locked"),
                        "similarity": hit.score
                    })
            
            return output
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def _build_filter_expr(self, filters: Dict) -> str:
        """构建Milvus过滤表达式"""
        expressions = []
        
        for field, condition in filters.items():
            if isinstance(condition, tuple):
                op, value = condition
                if op == ">=":
                    expressions.append(f"{field} >= {value}")
                elif op == "<=":
                    expressions.append(f"{field} <= {value}")
                elif op == ">":
                    expressions.append(f"{field} > {value}")
                elif op == "<":
                    expressions.append(f"{field} < {value}")
            else:
                expressions.append(f'{field} == "{condition}"')
        
        return " && ".join(expressions) if expressions else None
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """获取节点"""
        if not self._milvus_available:
            return None
        
        try:
            results = self.collection.query(
                expr=f'node_id == "{node_id}"',
                output_fields=list(self.collection.schema.fields.keys())
            )
            
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"Failed to get node {node_id}: {e}")
            return None
    
    def update(self, node_id: str, updates: Dict[str, Any]):
        """更新节点 (Milvus不支持直接更新,需要先删除再插入)"""
        if not self._milvus_available:
            return
        
        try:
            # 获取现有节点
            existing = self.get_node(node_id)
            if not existing:
                logger.warning(f"Node {node_id} not found for update")
                return
            
            # 合并更新
            existing.update(updates)
            
            # 删除旧节点
            self.delete(node_id)
            
            # 插入新节点
            self.insert(existing)
            
        except Exception as e:
            logger.error(f"Failed to update node {node_id}: {e}")
    
    def delete(self, node_id: str):
        """删除节点"""
        if not self._milvus_available:
            return
        
        try:
            expr = f'node_id == "{node_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            logger.debug(f"Deleted node {node_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete node {node_id}: {e}")
    
    def get_all_nodes(self, limit: int = 1000) -> List[Dict]:
        """获取所有节点"""
        if not self._milvus_available:
            return []
        
        try:
            results = self.collection.query(
                expr="",  # 空表达式表示所有
                output_fields=list(self.collection.schema.fields.keys()),
                limit=limit
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get all nodes: {e}")
            return []
    
    def update_access_count(self, node_id: str):
        """更新访问计数"""
        if not self._milvus_available:
            return
        
        try:
            node = self.get_node(node_id)
            if node:
                from datetime import datetime
                self.update(node_id, {
                    "access_count": node.get("access_count", 0) + 1,
                    "last_accessed": int(datetime.now().timestamp())
                })
        except Exception as e:
            logger.error(f"Failed to update access count: {e}")


# 简化的ChromaDB实现(用于开发/测试)
class ChromaVectorStore(VectorStore):
    """Chroma向量数据库实现(轻量级)"""
    
    def __init__(self, persist_directory: str = "./chroma_db", embedding_model=None):
        """
        初始化Chroma
        
        Args:
            persist_directory: 数据持久化目录
            embedding_model: 嵌入模型
        """
        self.persist_directory = persist_directory
        self.embedding_model = embedding_model
        
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection("memory_nodes")
            logger.info(f"Initialized ChromaDB at {persist_directory}")
        except ImportError:
            logger.error("chromadb not installed")
            self.client = None
    
    def insert(self, data: Dict[str, Any]):
        """插入节点"""
        if not self.client:
            return
        
        try:
            self.collection.add(
                ids=[data["node_id"]],
                documents=[data["nl_summary"]],
                metadatas=[{k: v for k, v in data.items() if k != "nl_summary"}]
            )
        except Exception as e:
            logger.error(f"Chroma insert failed: {e}")
    
    def search(self, query: str, top_k: int = 10, filters: Optional[Dict] = None) -> List[Dict]:
        """搜索"""
        if not self.client:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filters
            )
            
            output = []
            for i in range(len(results["ids"][0])):
                output.append({
                    "node_id": results["ids"][0][i],
                    "nl_summary": results["documents"][0][i],
                    **results["metadatas"][0][i],
                    "similarity": 1.0 - results["distances"][0][i]  # ChromaDB返回距离
                })
            
            return output
        except Exception as e:
            logger.error(f"Chroma search failed: {e}")
            return []
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """获取节点"""
        if not self.client:
            return None
        
        try:
            results = self.collection.get(ids=[node_id])
            if results["ids"]:
                return {
                    "node_id": results["ids"][0],
                    "nl_summary": results["documents"][0],
                    **results["metadatas"][0]
                }
            return None
        except Exception as e:
            logger.error(f"Chroma get node failed: {e}")
            return None
    
    def update(self, node_id: str, updates: Dict[str, Any]):
        """更新节点"""
        if not self.client:
            return
        
        try:
            existing = self.get_node(node_id)
            if existing:
                existing.update(updates)
                self.collection.update(
                    ids=[node_id],
                    documents=[existing.get("nl_summary", "")],
                    metadatas=[{k: v for k, v in existing.items() if k not in ["node_id", "nl_summary"]}]
                )
        except Exception as e:
            logger.error(f"Chroma update failed: {e}")
    
    def delete(self, node_id: str):
        """删除节点"""
        if not self.client:
            return
        
        try:
            self.collection.delete(ids=[node_id])
        except Exception as e:
            logger.error(f"Chroma delete failed: {e}")
    
    def get_all_nodes(self, limit: int = 1000) -> List[Dict]:
        """获取所有节点"""
        if not self.client:
            return []
        
        try:
            results = self.collection.get(limit=limit)
            output = []
            for i in range(len(results["ids"])):
                output.append({
                    "node_id": results["ids"][i],
                    "nl_summary": results["documents"][i],
                    **results["metadatas"][i]
                })
            return output
        except Exception as e:
            logger.error(f"Chroma get all nodes failed: {e}")
            return []
    
    def update_access_count(self, node_id: str):
        """更新访问计数"""
        node = self.get_node(node_id)
        if node:
            from datetime import datetime
            self.update(node_id, {
                "access_count": node.get("access_count", 0) + 1,
                "last_accessed": int(datetime.now().timestamp())
            })

