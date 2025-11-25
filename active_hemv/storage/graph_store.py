"""
图数据库存储层 - Active-H-EMV 系统
用于存储记忆树的拓扑结构（使用 Neo4j）
"""

from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from loguru import logger


class GraphStore(ABC):
    """图数据库抽象基类"""
    
    @abstractmethod
    def add_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """添加节点到图数据库"""
        pass
    
    @abstractmethod
    def add_edge(self, source_id: str, target_id: str, relationship: str, 
                 properties: Optional[Dict[str, Any]] = None) -> bool:
        """在两个节点之间添加边"""
        pass
    
    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取节点"""
        pass
    
    @abstractmethod
    def get_children(self, node_id: str) -> List[Dict[str, Any]]:
        """获取指定节点的所有子节点"""
        pass
    
    @abstractmethod
    def get_parent(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取指定节点的父节点"""
        pass
    
    @abstractmethod
    def delete_node(self, node_id: str) -> bool:
        """删除节点及其关联的边"""
        pass
    
    @abstractmethod
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """更新节点属性"""
        pass


class Neo4jGraphStore(GraphStore):
    """Neo4j 图数据库实现"""
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j"
    ):
        """
        初始化 Neo4j 连接
        
        Args:
            uri: Neo4j 连接 URI
            username: 数据库用户名
            password: 数据库密码
            database: 数据库名称
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self._driver = None
        
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(uri, auth=(username, password))
            logger.info(f"已连接到 Neo4j: {uri}")
        except ImportError:
            logger.warning("未安装 neo4j 包，图数据库操作将被跳过")
        except Exception as e:
            logger.warning(f"连接 Neo4j 失败: {e}，图数据库操作将被跳过")
    
    def add_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """添加节点到图数据库"""
        if not self._driver:
            logger.warning("Neo4j 不可用，跳过 add_node")
            return False
        
        try:
            with self._driver.session(database=self.database) as session:
                query = """
                MERGE (n:MemoryNode {id: $node_id})
                SET n += $properties
                RETURN n
                """
                session.run(query, node_id=node_id, properties=properties)
                logger.debug(f"已添加节点 {node_id} 到图数据库")
                return True
        except Exception as e:
            logger.error(f"添加节点 {node_id} 失败: {e}")
            return False
    
    def add_edge(self, source_id: str, target_id: str, relationship: str,
                 properties: Optional[Dict[str, Any]] = None) -> bool:
        """在两个节点之间添加边"""
        if not self._driver:
            logger.warning("Neo4j 不可用，跳过 add_edge")
            return False
        
        try:
            with self._driver.session(database=self.database) as session:
                query = f"""
                MATCH (a:MemoryNode {{id: $source_id}})
                MATCH (b:MemoryNode {{id: $target_id}})
                MERGE (a)-[r:{relationship}]->(b)
                SET r += $properties
                RETURN r
                """
                props = properties or {}
                session.run(query, source_id=source_id, target_id=target_id, properties=props)
                logger.debug(f"已添加边 {source_id} -{relationship}-> {target_id}")
                return True
        except Exception as e:
            logger.error(f"添加边失败: {e}")
            return False
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取节点"""
        if not self._driver:
            return None
        
        try:
            with self._driver.session(database=self.database) as session:
                query = "MATCH (n:MemoryNode {id: $node_id}) RETURN n"
                result = session.run(query, node_id=node_id)
                record = result.single()
                if record:
                    return dict(record["n"])
                return None
        except Exception as e:
            logger.error(f"获取节点 {node_id} 失败: {e}")
            return None
    
    def get_children(self, node_id: str) -> List[Dict[str, Any]]:
        """获取指定节点的所有子节点"""
        if not self._driver:
            return []
        
        try:
            with self._driver.session(database=self.database) as session:
                query = """
                MATCH (parent:MemoryNode {id: $node_id})-[:PARENT_OF]->(child)
                RETURN child
                """
                result = session.run(query, node_id=node_id)
                return [dict(record["child"]) for record in result]
        except Exception as e:
            logger.error(f"获取节点 {node_id} 的子节点失败: {e}")
            return []
    
    def get_parent(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取指定节点的父节点"""
        if not self._driver:
            return None
        
        try:
            with self._driver.session(database=self.database) as session:
                query = """
                MATCH (parent:MemoryNode)-[:PARENT_OF]->(child:MemoryNode {id: $node_id})
                RETURN parent
                """
                result = session.run(query, node_id=node_id)
                record = result.single()
                if record:
                    return dict(record["parent"])
                return None
        except Exception as e:
            logger.error(f"获取节点 {node_id} 的父节点失败: {e}")
            return None
    
    def delete_node(self, node_id: str) -> bool:
        """删除节点及其关联的边"""
        if not self._driver:
            logger.warning("Neo4j 不可用，跳过 delete_node")
            return False
        
        try:
            with self._driver.session(database=self.database) as session:
                query = """
                MATCH (n:MemoryNode {id: $node_id})
                DETACH DELETE n
                """
                session.run(query, node_id=node_id)
                logger.debug(f"已删除节点 {node_id}")
                return True
        except Exception as e:
            logger.error(f"删除节点 {node_id} 失败: {e}")
            return False
    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """更新节点属性"""
        if not self._driver:
            logger.warning("Neo4j 不可用，跳过 update_node")
            return False
        
        try:
            with self._driver.session(database=self.database) as session:
                query = """
                MATCH (n:MemoryNode {id: $node_id})
                SET n += $properties
                RETURN n
                """
                session.run(query, node_id=node_id, properties=properties)
                logger.debug(f"已更新节点 {node_id}")
                return True
        except Exception as e:
            logger.error(f"更新节点 {node_id} 失败: {e}")
            return False
    
    def close(self):
        """关闭 Neo4j 连接"""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j 连接已关闭")
    
    def __del__(self):
        """析构时清理资源"""
        self.close()

