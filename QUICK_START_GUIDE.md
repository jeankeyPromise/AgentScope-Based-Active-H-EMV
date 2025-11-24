# Active-H-EMV 快速启动指南

## 当前实施进度

### ✅ 已完成模块

1. **基础架构** (`active_hemv/agents/base_agent.py`)
   - BaseMemoryAgent基类
   - 统一的日志记录和错误处理
   - 访问跟踪机制

2. **Perception-Worker Agent** (`active_hemv/agents/perception_worker.py`)
   - L0→L1场景图生成
   - YOLO-World + CLIP集成框架
   - Socratic Models实现
   - 变化检测算法

3. **Event-Aggregator Agent** (`active_hemv/agents/event_aggregator.py`)
   - L2事件聚合逻辑
   - 事件边界检测
   - 自然语言描述生成

4. **Memory-Orchestrator Agent** (`active_hemv/agents/memory_orchestrator.py`)
   - L3/L4+摘要生成
   - 交互式检索路由
   - 并行搜索调度
   - LLM递归摘要

5. **Memory-Gardener Agent** (`active_hemv/agents/memory_gardener.py`) ⭐ **核心创新**
   - 效用驱动的遗忘周期
   - 追溯性记忆编辑
   - 定时调度器
   - L0/L1激进遗忘
   - L2/L3语义融合

6. **Search-Worker Agent** (`active_hemv/agents/search_worker.py`)
   - 并行搜索工作单元
   - 时间范围搜索

7. **存储层**
   - `active_hemv/storage/vector_store.py`: Milvus/Chroma向量数据库
   - 向量检索接口
   - 访问计数跟踪

### 🚧 需要继续创建的模块

#### 优先级 P0 (核心功能)

1. **Graph Store** (`active_hemv/storage/graph_store.py`)
```python
# 创建文件实现Neo4j图数据库接口
# 用于存储记忆树的拓扑结构
```

2. **Object Store** (`active_hemv/storage/object_store.py`)
```python
# 实现MinIO对象存储接口
# 用于存储L0原始图像/音频
```

3. **Memory 模块** (`active_hemv/memory/`)
   - `utility_scorer.py`: 效用函数U(n,t) = α·A + β·S + γ·I
   - `forgetting_policy.py`: 三级阈值策略
   - `editing_engine.py`: 追溯性编辑引擎
   - `consistency_checker.py`: 一致性检查

4. **配置文件** (`active_hemv/config/`)
   - `agent_config.yaml`: Agent配置
   - `storage_config.yaml`: 数据库配置
   - `forgetting_config.yaml`: 遗忘参数

#### 优先级 P1 (系统完善)

5. **集成层** (`active_hemv/integration/`)
   - `agentscope_adapter.py`: 现有H-EMV代码适配器
   - `system_initializer.py`: 系统启动器

6. **工具模块** (`active_hemv/utils/`)
   - `logger.py`: 日志配置
   - `metrics.py`: 性能指标收集

#### 优先级 P2 (评估验证)

7. **评估框架** (`experiments/`)
   - `forgetting_ablation/`: 遗忘机制消融实验
   - `editing_validation/`: 编辑准确性验证
   - `parallel_search_benchmark/`: 并行搜索性能测试

---

## 快速开始 (基于现有代码)

### 步骤 1: 安装依赖

```bash
# 激活虚拟环境
conda activate active_hemv  # 或你的环境名

# 安装更新的依赖
pip install -r requirements.txt
```

### 步骤 2: 启动数据库服务 (Docker)

创建 `docker-compose.yml`:

```yaml
version: '3.8'
services:
  milvus-standalone:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"
      - "9091:9091"
    volumes:
      - ./milvus_data:/var/lib/milvus
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
  
  neo4j:
    image: neo4j:5.14
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/password
    volumes:
      - ./neo4j_data:/data
  
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - ./minio_data:/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

启动:
```bash
docker-compose up -d
```

### 步骤 3: 测试现有Agent

创建 `test_agents.py`:

```python
import agentscope
from active_hemv.agents import PerceptionWorkerAgent, EventAggregatorAgent
from active_hemv.storage import ChromaVectorStore  # 使用轻量级Chroma测试
from PIL import Image
from datetime import datetime

# 初始化AgentScope
agentscope.init(
    model_configs={
        "model_type": "openai_chat",
        "config_name": "gpt-4o",
        "model_name": "gpt-4o",
        "api_key": "your-api-key"
    }
)

# 初始化存储
vector_store = ChromaVectorStore(persist_directory="./test_chroma_db")

storage_backends = {
    "vector": vector_store
}

# 创建Perception Worker
perception_agent = PerceptionWorkerAgent(
    name="TestPerceptionWorker",
    storage_backends=storage_backends
)

# 创建Event Aggregator
event_agent = EventAggregatorAgent(
    name="TestEventAggregator",
    storage_backends=storage_backends
)

# 测试感知流程
from agentscope.message import Msg

sensor_msg = Msg(
    name="Sensor",
    content={
        "type": "sensor_data",
        "image": Image.new("RGB", (640, 480), color="blue"),  # 测试图像
        "current_action": "grasp",
        "current_action_state": "running",
        "timestamp": datetime.now()
    },
    role="system"
)

# 调用Perception Agent
perception_result = perception_agent(sensor_msg)
print("Perception Result:", perception_result.content)

# 如果有状态变化,调用Event Aggregator
if perception_result.content.get("state_changed"):
    event_result = event_agent(perception_result)
    print("Event Result:", event_result.content)
```

运行:
```bash
python test_agents.py
```

---

## 与现有H-EMV代码集成

您现有的 `em/em_tree.py` 定义了完整的数据结构。Active-H-EMV可以无缝集成:

### 方法 1: 适配器模式 (推荐)

```python
# 在 active_hemv/integration/legacy_adapter.py

from em.em_tree import HigherLevelSummary
from llm_emv.emv_api import EMVerbalizationAPI
from active_hemv.agents import MemoryOrchestratorAgent

class LegacyHEMVAdapter:
    """将现有H-EMV与Active-H-EMV桥接"""
    
    def __init__(self, legacy_history: HigherLevelSummary):
        self.legacy_history = legacy_history
        
        # 将现有记忆树导入到向量数据库
        self.import_to_vector_store()
    
    def import_to_vector_store(self):
        """将现有记忆树导入Active-H-EMV"""
        # 遍历树,导入每个节点到Milvus/Chroma
        pass
    
    def query(self, user_query: str):
        """使用Active-H-EMV的Orchestrator处理查询"""
        orchestrator = MemoryOrchestratorAgent(...)
        result = orchestrator.reply(Msg(...))
        return result
```

### 方法 2: 渐进式迁移

1. **阶段1**: 保留现有 `llm_emv/emv_api.py` 作为只读接口
2. **阶段2**: 新数据使用 Active-H-EMV Agent 写入
3. **阶段3**: 后台任务将历史数据逐步迁移到新系统

---

## 核心创新功能演示

### 1. 主动遗忘

```python
from active_hemv.agents import MemoryGardenerAgent
from active_hemv.memory import UtilityScorer, ForgettingPolicy

# 创建Gardener Agent
gardener = MemoryGardenerAgent(
    name="Gardener",
    storage_backends=storage_backends,
    utility_weights=(0.5, 0.3, 0.2),  # α, β, γ
    schedule_enabled=True,
    schedule_interval_hours=1.0  # 每小时扫描一次
)

# 手动触发遗忘周期(用于测试)
from agentscope.message import Msg

trigger_msg = Msg(
    name="Admin",
    content={"type": "ManualTrigger"},
    role="user"
)

result = gardener(trigger_msg)
print("Forgetting Cycle Result:", result.content)
```

### 2. 记忆编辑

```python
# 模拟用户纠错场景
conflict_msg = Msg(
    name="User",
    content={
        "type": "ConflictEvent",
        "original_answer": "你抓取了红色的杯子",
        "user_correction": "不对,那是蓝色的碗",
        "query_context": {
            "query": "昨天下午我抓了什么?",
            "retrieved_nodes": ["l1_12345", "l2_67890"]
        }
    },
    role="user"
)

edit_result = gardener(conflict_msg)
print("Edit Result:", edit_result.content)
```

### 3. 并行搜索

```python
from active_hemv.agents import MemoryOrchestratorAgent

orchestrator = MemoryOrchestratorAgent(
    name="Orchestrator",
    storage_backends=storage_backends,
    enable_parallel_search=True,
    max_search_workers=3
)

query_msg = Msg(
    name="User",
    content={
        "type": "user_query",
        "query": "我哪天丢了钥匙?",
        "enable_parallel": True
    },
    role="user"
)

answer = orchestrator(query_msg)
print("Answer:", answer.content["answer"])
print("Search Strategy:", answer.content["search_strategy"])
```

---

## 下一步工作

### 1. 完成剩余存储层 (立即)

创建以下文件(参考已有的`vector_store.py`结构):

```bash
# Graph Store
active_hemv/storage/graph_store.py

# Object Store  
active_hemv/storage/object_store.py

# Message Queue
active_hemv/storage/message_queue.py
```

### 2. 实现记忆管理模块 (核心算法)

```bash
# 效用评分器
active_hemv/memory/utility_scorer.py
# 实现 U(n,t) = α·A(n,t) + β·S(n) + γ·I(n)

# 遗忘策略
active_hemv/memory/forgetting_policy.py
# 实现三级阈值 (HIGH/MED/LOW)

# 编辑引擎
active_hemv/memory/editing_engine.py
# 实现错误定位、重感知、级联更新

# 一致性检查
active_hemv/memory/consistency_checker.py
```

### 3. 创建端到端测试 (验证)

```bash
tests/test_e2e_pipeline.py
# 测试: 传感器数据 → Perception → Event → Orchestrator → Gardener
```

### 4. 评估实验 (论文数据)

```bash
experiments/run_teach_evaluation.py
# 在TEACh数据集上运行完整评估

experiments/forgetting_ablation/run_ablation.py
# 消融实验: 不同效用函数权重

experiments/metrics/calculate_all_metrics.py
# 计算所有指标: Token效率、存储压缩比、召回率等
```

---

## 故障排查

### 问题 1: AgentScope导入错误

```python
# 如果 agentscope 版本不兼容
pip install agentscope==0.0.5 --upgrade
```

### 问题 2: Milvus连接失败

```bash
# 检查Docker服务
docker ps | grep milvus

# 查看日志
docker logs <milvus_container_id>

# 备用方案: 使用Chroma (无需Docker)
from active_hemv.storage import ChromaVectorStore
vector_store = ChromaVectorStore()
```

### 问题 3: 内存不足 (大规模数据)

```python
# 在Gardener的forgetting_cycle中分批处理
all_nodes = vector_store.get_all_nodes(limit=1000)  # 限制批次大小
```

---

## 论文撰写建议

基于已实现的代码,您可以这样组织论文:

### 第3章: 方法 (Methods)

**3.1 系统架构**
- 引用 `ACTIVE_H_EMV_IMPLEMENTATION_PLAN.md` 中的架构图
- 代码: `active_hemv/agents/base_agent.py` (基础设计)

**3.2 主动遗忘机制**
- 算法伪代码来自 `active_hemv/agents/memory_gardener.py::forgetting_cycle()`
- 效用函数公式: U(n,t) = α·A + β·S + γ·I
- 代码: `active_hemv/memory/utility_scorer.py`

**3.3 追溯性记忆编辑**
- 流程图展示 `_handle_conflict_event()` 的4个步骤
- 代码: `active_hemv/memory/editing_engine.py`

**3.4 并行搜索优化**
- 对比实验: 串行 vs 并行延迟
- 代码: `active_hemv/agents/memory_orchestrator.py::_parallel_temporal_search()`

### 第4章: 实验 (Experiments)

**4.1 数据集与设置**
- TEACh, Ego4D, ARMAR-7

**4.2 对比实验**
- Table 1: Token效率对比 (Gemini 1-pass vs H-EMV vs Active-H-EMV)
- 代码: `experiments/compare_baselines.py`

**4.3 消融实验**
- Table 2: 效用函数权重消融
- 代码: `experiments/forgetting_ablation/run_ablation.py`

**4.4 长期运行测试**
- Figure 3: 30天存储增长曲线
- 代码: `experiments/long_term_simulation.py`

---

## 致谢

本实施方案基于:
1. **H-EMV论文** (KIT, 2024): 层级化情景记忆口语化算法
2. **AgentScope框架** (阿里巴巴达摩院): 企业级多智能体协作平台

---

## 联系与支持

如遇到问题,请:
1. 检查 `debug.log` 文件
2. 查看 `ACTIVE_H_EMV_IMPLEMENTATION_PLAN.md` 的详细设计
3. 参考 AgentScope 文档: https://github.com/agentscope-ai/agentscope

祝您的毕业设计顺利完成! 🎓🚀

