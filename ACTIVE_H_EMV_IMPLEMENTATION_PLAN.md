# Active-H-EMV 完整实施方案

## 1. 架构概述

本方案将您现有的 H-EMV 系统改造为基于 AgentScope 的多智能体协作架构，实现以下核心创新：

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Active-H-EMV System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Memory-Orchestrator Agent (L3+)                │  │
│  │  - 全局协调器                                            │  │
│  │  - 查询路由                                              │  │
│  │  │  - 递归摘要生成                                       │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │                                           │
│        ┌────────────┴────────────┐                             │
│        │                         │                             │
│  ┌─────▼──────────┐    ┌────────▼─────────┐                   │
│  │ Event-Agg      │    │  Memory-Gardener │  (后台运行)      │
│  │ Agent (L2)     │    │  Agent           │                   │
│  │ - 事件聚合     │    │  - 主动遗忘      │                   │
│  │ - 自然语言描述 │    │  - 记忆编辑      │                   │
│  └───────┬────────┘    │  - 效用评分      │                   │
│          │             └──────────────────┘                    │
│  ┌───────▼────────┐                                            │
│  │ Perception-    │                                            │
│  │ Worker Agent   │                                            │
│  │ (L0 → L1)      │                                            │
│  │ - YOLO+CLIP    │                                            │
│  │ - 场景图生成   │                                            │
│  └────────────────┘                                            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    数据存储层                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Milvus   │  │  Neo4j   │  │  MinIO   │  │  Redis   │      │
│  │ 向量检索 │  │  树结构  │  │  L0存储  │  │  消息队列│      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心创新点

#### 创新 1: 基于效用理论的主动遗忘机制

**数学模型**：
```
U(n, t) = α·A(n,t) + β·S(n) + γ·I(n)

其中：
- A(n,t): 访问热度（时间衰减）
- S(n): 语义显著性（LLM打分）
- I(n): 信息密度（独特性）
- α, β, γ: 可调权重
```

**遗忘策略**：
- L0/L1: 低效用节点删除原始数据，保留文本摘要
- L2/L3: 多个低效用事件融合为粗粒度节点
- 高显著性节点锁定保护

#### 创新 2: 追溯性记忆编辑

**人机回环修正流程**：
1. 用户纠错触发 ConflictEvent
2. Memory-Gardener 反向定位错误源（L1/L0）
3. 调用更强视觉模型重新感知
4. 级联向上更新 L2/L3 摘要
5. 保证树结构逻辑一致性

#### 创新 3: 并行化检索优化

**基于 AgentScope 的推测性并行搜索**：
- Map-Reduce 风格的多分支并发搜索
- 降低挂钟时间（Wall-clock Time）
- 充分利用多卡资源

---

## 2. 文件结构设计

```
AgentScope-Based-Active-H-EMV/
├── requirements.txt  ✅ (已更新)
├── README.md
├── ACTIVE_H_EMV_IMPLEMENTATION_PLAN.md  ✅ (本文件)
│
├── active_hemv/  (新增核心模块)
│   ├── __init__.py
│   ├── agents/  (AgentScope 智能体定义)
│   │   ├── __init__.py
│   │   ├── base_agent.py  (基础Agent类)
│   │   ├── perception_worker.py  (L0→L1)
│   │   ├── event_aggregator.py  (L2)
│   │   ├── memory_orchestrator.py  (L3+)
│   │   ├── memory_gardener.py  (遗忘+编辑)
│   │   └── search_worker.py  (并行搜索Worker)
│   │
│   ├── storage/  (数据存储抽象)
│   │   ├── __init__.py
│   │   ├── vector_store.py  (Milvus/Chroma接口)
│   │   ├── graph_store.py  (Neo4j接口)
│   │   ├── object_store.py  (MinIO接口)
│   │   └── message_queue.py  (Redis消息队列)
│   │
│   ├── memory/  (记忆管理)
│   │   ├── __init__.py
│   │   ├── utility_scorer.py  (效用函数U(n,t))
│   │   ├── forgetting_policy.py  (遗忘策略)
│   │   ├── editing_engine.py  (记忆编辑引擎)
│   │   └── consistency_checker.py  (一致性检查)
│   │
│   ├── config/  (配置文件)
│   │   ├── agent_config.yaml  (Agent配置)
│   │   ├── storage_config.yaml  (存储配置)
│   │   └── forgetting_config.yaml  (遗忘参数)
│   │
│   └── utils/  (工具函数)
│       ├── __init__.py
│       ├── logger.py  (日志系统)
│       └── metrics.py  (性能指标)
│
├── em/  (保留原有H-EMV实现)
│   ├── em_tree.py  (保持不变，作为数据结构基础)
│   ├── ...
│
├── llm_emv/  (改造为AgentScope适配层)
│   ├── emv_api.py  (重构为Agent消息接口)
│   ├── ...
│
├── experiments/  (评估实验)
│   ├── forgetting_ablation/  (遗忘机制消融实验)
│   ├── editing_validation/  (编辑准确性验证)
│   └── parallel_search_benchmark/  (并行搜索性能测试)
│
└── tests/  (单元测试)
    ├── test_agents/
    ├── test_memory/
    └── test_storage/
```

---

## 3. 核心模块实现指南

### 3.1 Perception-Worker Agent (L0 → L1)

**职责**：
- 实时处理机器人传感器数据
- 基于变化检测触发 L0 数据持久化
- 集成 YOLO-World 和 CLIP 进行场景图生成

**关键技术点**（基于 H-EMV 论文）：
1. **Socratic Models 方法**：
   - CLIP 文本嵌入检索 LVIS 前100类别
   - 结合 L3 目标描述，Llama-3 生成潜在物体列表
   - YOLO-World 开放词汇检测

2. **变化检测策略**：
   - 场景图拓扑变化（新增/删除物体）
   - 空间关系变化（位置关系翻转）
   - 显著动作/语音事件

**AgentScope 接口**：
```python
class PerceptionWorkerAgent(AgentBase):
    def reply(self, x: Msg = None) -> Msg:
        # 处理传感器数据消息
        # 生成 SceneGraphInstant
        # 向 EventAggregator 发送状态变化消息
```

### 3.2 Event-Aggregator Agent (L2)

**职责**：
- 监听 L1 数据流
- 检测事件边界（动作完成、场景变化）
- 生成自然语言事件描述

**聚合规则**：
- 动作状态机转换（如 `<running>` → `<succeeded>`）
- 场景图显著变化
- 语音指令触发

**AgentScope 接口**：
```python
class EventAggregatorAgent(AgentBase):
    def reply(self, x: Msg = None) -> Msg:
        # 接收 L1 StateChange 消息
        # 应用事件边界检测逻辑
        # 创建 EventBasedSummary
        # 向 Orchestrator 报告
```

### 3.3 Memory-Orchestrator Agent (L3+)

**职责**：
- 全局记忆树管理
- 递归 LLM 摘要生成（L3 → L4+）
- 交互式检索路由

**检索策略**：
1. 解析用户查询（时间、实体、动作）
2. 从根节点开始语义匹配
3. 动态决策：直接回答 vs. 向下expand
4. 分发查询到 SearchWorker（并行）

**AgentScope 接口**：
```python
class MemoryOrchestratorAgent(AgentBase):
    def reply(self, x: Msg = None) -> Msg:
        # 维护记忆树根节点
        # 处理用户查询
        # 协调 SearchWorker
        # 调用 LLM 生成摘要
```

### 3.4 Memory-Gardener Agent (核心创新)

**职责**：
- 后台周期性扫描记忆树
- 计算节点效用值 U(n,t)
- 执行遗忘与编辑策略

**工作流程**：

#### A. 遗忘模块
```python
def forgetting_cycle(self):
    for node in self.traverse_tree():
        utility = self.utility_scorer.compute(node)
        
        if utility < THRESHOLD_LOW:
            # L0/L1: 删除原始数据
            if node.level in ['L0', 'L1']:
                self.storage.delete_raw_data(node)
                node.mark_as_summarized_only()
            
            # L2/L3: 语义融合
            elif node.level in ['L2', 'L3']:
                siblings = self.find_low_utility_siblings(node)
                merged_node = self.llm_merge(siblings)
                self.tree.replace(siblings, merged_node)
        
        elif utility < THRESHOLD_MED:
            # 降级存储（如压缩图像）
            self.storage.downgrade(node)
```

#### B. 编辑模块
```python
def handle_conflict_event(self, conflict_msg: Msg):
    # 1. 定位错误源
    error_node = self.locate_error_source(
        conflict_msg.query_context,
        conflict_msg.user_correction
    )
    
    # 2. 重感知
    if error_node.has_raw_data:
        corrected_perception = self.vlm_reprocess(
            error_node.raw.image,
            prompt=conflict_msg.user_correction
        )
        error_node.update_perception(corrected_perception)
    
    # 3. 级联更新
    self.propagate_update_upward(error_node)
    
    # 4. 记录编辑历史
    self.log_edit(error_node, conflict_msg)
```

**AgentScope 接口**：
```python
class MemoryGardenerAgent(AgentBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.forgetting_cycle, 
            'interval', 
            hours=1
        )
    
    def reply(self, x: Msg = None) -> Msg:
        if x.content.type == 'ConflictEvent':
            return self.handle_conflict_event(x)
        elif x.content.type == 'ManualTrigger':
            return self.forgetting_cycle()
```

---

## 4. 数据存储实现

### 4.1 向量数据库 (Milvus)

**用途**：
- 存储 L1-L4 节点的文本嵌入
- 语义搜索快速索引

**Schema设计**：
```python
collection_schema = {
    "fields": [
        {"name": "node_id", "type": DataType.VARCHAR, "is_primary": True},
        {"name": "level", "type": DataType.VARCHAR},  # L1/L2/L3/L4
        {"name": "embedding", "type": DataType.FLOAT_VECTOR, "dim": 768},
        {"name": "timestamp_start", "type": DataType.INT64},
        {"name": "timestamp_end", "type": DataType.INT64},
        {"name": "nl_summary", "type": DataType.VARCHAR},
        {"name": "utility_score", "type": DataType.FLOAT},
        {"name": "is_locked", "type": DataType.BOOL},  # 高显著性锁定
    ]
}
```

### 4.2 图数据库 (Neo4j)

**用途**：
- 显式存储记忆树拓扑
- 支持复杂图遍历查询

**Cypher 查询示例**：
```cypher
// 查找所有涉及"苹果"的子目标
MATCH (g:GoalNode)-[:CONTAINS*]->(e:EventNode)
WHERE e.objects CONTAINS 'apple'
RETURN g.goal_description, collect(e.event_summary)

// 追溯错误源
MATCH path = (top:L4Node)-[:PARENT*]->(error:L1Node {node_id: $error_id})
RETURN path
```

### 4.3 对象存储 (MinIO)

**用途**：
- 存储 L0 层原始图像/音频
- 支持分层存储策略

**存储策略**：
```
Bucket: robot-memories
├── raw/           (原始数据，高压缩)
│   ├── 2024/
│   │   ├── 11/
│   │   │   ├── 24/
│   │   │   │   ├── {timestamp}_{node_id}.jpg
│   │   │   │   └── {timestamp}_{node_id}.wav
│
├── downgraded/    (降级数据，超高压缩)
│   └── ...
│
└── locked/        (锁定数据，无损压缩)
    └── ...
```

### 4.4 消息队列 (Redis)

**用途**：
- Agent 间异步通信
- 任务队列

**队列设计**：
```
perception_queue:    L0 数据 → Perception Worker
event_queue:         L1 变化 → Event Aggregator
orchestrator_queue:  L2 事件 → Orchestrator
gardener_queue:      冲突事件 → Gardener
```

---

## 5. 效用函数详细设计

### 5.1 访问热度 A(n, t)

**定义**：
```python
def access_frequency(node, current_time):
    """
    结合时间衰减的访问次数
    """
    total_score = 0.0
    for access_time in node.access_history:
        delta_days = (current_time - access_time).days
        decay = np.exp(-LAMBDA * delta_days)  # λ = 0.01
        total_score += decay
    
    return total_score / (len(node.access_history) + 1)
```

**数据来源**：AgentScope 日志系统自动记录每次节点被检索的时间戳

### 5.2 语义显著性 S(n)

**计算方法**：
```python
def semantic_salience(node, llm):
    """
    LLM 评估事件的异常性和重要性
    """
    prompt = f"""
    请对以下机器人记忆片段的显著性打分（0-1）：
    
    事件描述：{node.nl_summary}
    
    评分标准：
    - 异常事件（失败、错误）：0.8-1.0
    - 重要任务节点：0.6-0.8
    - 常规操作：0.3-0.5
    - 重复性动作：0.0-0.3
    
    请直接返回一个0-1的浮点数。
    """
    
    score = llm.invoke(prompt)
    # 缓存到节点，避免重复计算
    node.salience_cache = float(score)
    return node.salience_cache
```

### 5.3 信息密度 I(n)

**定义**：
```python
def information_density(node, history_tree):
    """
    衡量节点包含独特信息的程度
    """
    # 1. 计算该节点文本与历史的相似度
    node_emb = encode(node.nl_summary)
    all_embeddings = encode([n.nl_summary for n in history_tree.all_nodes])
    
    # 2. 找出最相似的其他节点
    similarities = cosine_similarity(node_emb, all_embeddings)
    similarities.sort()
    
    # 3. 信息密度 = 1 - 最高相似度（越独特，密度越高）
    return 1.0 - similarities[-2]  # -2是排除自身
```

### 5.4 完整效用函数

```python
class UtilityScorer:
    def __init__(self, alpha=0.5, beta=0.3, gamma=0.2):
        self.alpha = alpha  # 访问热度权重
        self.beta = beta    # 语义显著性权重
        self.gamma = gamma  # 信息密度权重
    
    def compute(self, node, current_time, history_tree, llm):
        A = access_frequency(node, current_time)
        S = semantic_salience(node, llm)
        I = information_density(node, history_tree)
        
        utility = self.alpha * A + self.beta * S + self.gamma * I
        
        # 记录到节点元数据
        node.utility_score = utility
        node.utility_timestamp = current_time
        
        return utility
```

---

## 6. 遗忘策略实施细节

### 6.1 三级阈值策略

```python
class ForgettingPolicy:
    THRESHOLD_HIGH = 0.7   # 高价值，完全保留
    THRESHOLD_MED = 0.4    # 中等价值，降级存储
    THRESHOLD_LOW = 0.2    # 低价值，激进遗忘
    
    def apply(self, node):
        if node.utility_score >= self.THRESHOLD_HIGH:
            return Action.KEEP_ALL
        
        elif node.utility_score >= self.THRESHOLD_MED:
            return Action.DOWNGRADE
        
        elif node.utility_score >= self.THRESHOLD_LOW:
            return Action.TEXT_ONLY
        
        else:
            return Action.MERGE_OR_DELETE
```

### 6.2 L0/L1 激进遗忘

```python
def forget_raw_data(node):
    """
    删除原始图像/音频，保留文本化场景图
    """
    if node.level == 'L0':
        # 删除 MinIO 中的原始文件
        object_store.delete(node.image_uri)
        object_store.delete(node.audio_uri)
        
        # 更新节点状态
        node.image = None
        node.sound = None
        node.is_summarized_only = True
    
    elif node.level == 'L1':
        # 保留场景图文本，删除原始 L0 引用
        for scene in node.scenes:
            forget_raw_data(scene.raw)
```

### 6.3 L2/L3 语义融合

```python
def merge_low_utility_events(nodes, llm):
    """
    将多个低效用事件合并为粗粒度节点
    """
    # 收集所有事件描述
    summaries = [n.nl_summary for n in nodes]
    
    # LLM 生成融合摘要
    prompt = f"""
    以下是{len(nodes)}个连续的机器人事件：
    
    {chr(10).join(f'{i+1}. {s}' for i, s in enumerate(summaries))}
    
    请生成一个更抽象的单一事件描述，捕捉核心动作，省略细节。
    """
    
    merged_summary = llm.invoke(prompt)
    
    # 创建新的合并节点
    merged_node = EventBasedSummary(
        scenes=[],  # 不保留具体场景
        nl_summary=merged_summary,
        time_range=(nodes[0].range[0], nodes[-1].range[-1]),
        merged_from=[n.node_id for n in nodes]
    )
    
    return merged_node
```

### 6.4 关键帧保护

```python
def lock_high_salience_nodes(node):
    """
    对高显著性节点进行锁定保护
    """
    if node.salience_score > 0.8:
        # 移动到 MinIO 的 locked/ 目录
        object_store.move(
            f"raw/{node.image_uri}",
            f"locked/{node.image_uri}"
        )
        
        # 在向量数据库中标记
        vector_store.update(
            node.node_id,
            {"is_locked": True}
        )
        
        # 永久禁止遗忘
        node.is_locked = True
```

---

## 7. 记忆编辑实现

### 7.1 冲突检测触发

**用户交互示例**：
```
系统：昨天下午您抓取了红色的杯子。
用户：不对，那是蓝色的碗。

→ 触发 ConflictEvent:
  - original_answer: "红色的杯子"
  - user_correction: "蓝色的碗"
  - query_context: "昨天下午 + 抓取"
```

**AgentScope 消息格式**：
```python
conflict_msg = Msg(
    name="User",
    content={
        "type": "ConflictEvent",
        "original_answer": "红色的杯子",
        "user_correction": "蓝色的碗",
        "query_context": {
            "time": "昨天下午",
            "action": "抓取",
            "retrieved_nodes": ["node_123", "node_456"]
        }
    },
    role="user"
)
```

### 7.2 错误源定位

```python
def locate_error_source(self, conflict_msg):
    """
    反向追踪导致错误回答的节点
    """
    # 1. 从查询上下文获取相关节点
    candidate_nodes = conflict_msg.query_context.retrieved_nodes
    
    # 2. 使用 Neo4j 追溯到 L1/L0
    error_candidates = []
    for node_id in candidate_nodes:
        # 查找该节点的所有 L1 子孙
        l1_nodes = graph_store.query(f"""
            MATCH (n {{node_id: '{node_id}'}})-[:CONTAINS*]->(l1:L1Node)
            RETURN l1
        """)
        error_candidates.extend(l1_nodes)
    
    # 3. 通过语义匹配找出最可能的错误源
    #    （包含"杯子"且颜色描述错误的节点）
    for candidate in error_candidates:
        if "cup" in candidate.objects and "red" in candidate.nl_summary:
            return candidate
    
    return None
```

### 7.3 重感知流程

```python
def reperceive(self, error_node, user_correction):
    """
    使用更强视觉模型重新处理图像
    """
    # 1. 检查原始图像是否还存在
    if not error_node.raw.image:
        return {"success": False, "reason": "原始图像已被遗忘"}
    
    # 2. 调用 GPT-4o 进行VQA
    vlm_result = self.vlm.invoke([
        HumanMessage(content=[
            {"type": "text", "text": f"这张图中的物体是什么？用户说它是：{user_correction}"},
            {"type": "image_url", "image_url": error_node.raw.image}
        ])
    ])
    
    # 3. 更新场景图
    new_scene_graph = self.parse_vlm_output(vlm_result)
    error_node.update(new_scene_graph)
    
    # 4. 向量数据库更新
    new_embedding = embed(error_node.nl_summary)
    vector_store.update(error_node.node_id, {"embedding": new_embedding})
    
    return {"success": True, "new_graph": new_scene_graph}
```

### 7.4 级联更新

```python
def propagate_update_upward(self, corrected_node):
    """
    从纠正的节点向上更新所有父节点
    """
    # 1. 使用 Neo4j 找到所有祖先
    ancestors = graph_store.query(f"""
        MATCH path = (ancestor)-[:CONTAINS*]->(corrected {{node_id: '{corrected_node.node_id}'}})
        RETURN ancestor
        ORDER BY length(path) ASC
    """)
    
    # 2. 从最近的父节点开始逐层更新
    for ancestor in ancestors:
        if ancestor.level == 'L2':
            # 重新生成事件描述
            ancestor.nl_summary = self.regenerate_event_summary(ancestor)
        
        elif ancestor.level in ['L3', 'L4+']:
            # 重新调用 LLM 生成摘要
            children_summaries = [c.nl_summary for c in ancestor.children]
            ancestor.nl_summary = self.llm_summarize(children_summaries)
        
        # 更新向量数据库
        new_embedding = embed(ancestor.nl_summary)
        vector_store.update(ancestor.node_id, {"embedding": new_embedding})
    
    # 3. 记录编辑历史
    self.edit_log.append({
        "timestamp": datetime.now(),
        "corrected_node": corrected_node.node_id,
        "affected_ancestors": [a.node_id for a in ancestors],
        "user_correction": corrected_node.correction_text
    })
```

---

## 8. 并行搜索优化

### 8.1 推测性并行搜索

**场景**：用户查询"我哪天丢了钥匙？"（时间不确定）

**传统H-EMV**：
```
搜索顺序：今天 → 昨天 → 前天 → ...
→ 延迟高，O(n)
```

**Active-H-EMV (AgentScope)**：
```python
class MemoryOrchestratorAgent(AgentBase):
    def parallel_temporal_search(self, query):
        # 1. 分解搜索空间
        time_ranges = [
            ("last_week", date.today() - timedelta(days=7), date.today()),
            ("last_month", date.today() - timedelta(days=30), date.today() - timedelta(days=7)),
            ("last_3_months", date.today() - timedelta(days=90), date.today() - timedelta(days=30)),
        ]
        
        # 2. 并行实例化 SearchWorker
        workers = [
            SearchWorkerAgent(
                name=f"SearchWorker_{name}",
                time_range=(start, end),
                query=query
            )
            for name, start, end in time_ranges
        ]
        
        # 3. 并发执行
        with ThreadPoolExecutor(max_workers=len(workers)) as executor:
            futures = [executor.submit(w.search) for w in workers]
            results = [f.result() for f in futures]
        
        # 4. 合并结果
        all_matches = []
        for r in results:
            if r.found:
                all_matches.extend(r.nodes)
        
        return all_matches
```

### 8.2 Map-Reduce 风格聚合

```python
class SearchWorkerAgent(AgentBase):
    def search(self):
        # Map: 在分配的时间范围内搜索
        local_matches = []
        for node in self.tree.filter_by_time(self.time_range):
            similarity = self.semantic_match(self.query, node)
            if similarity > THRESHOLD:
                local_matches.append((node, similarity))
        
        # Reduce: 返回 top-k
        local_matches.sort(key=lambda x: x[1], reverse=True)
        return {
            "found": len(local_matches) > 0,
            "nodes": local_matches[:5],  # top-5
            "time_range": self.time_range
        }
```

---

## 9. AgentScope 集成实现

### 9.1 Agent 初始化与注册

```python
import agentscope
from agentscope.agents import AgentBase
from agentscope.message import Msg

# 初始化 AgentScope
agentscope.init(
    model_configs="active_hemv/config/model_config.json",
    project="Active-H-EMV",
    name="robot_memory_system",
    save_dir="./logs"
)

# 注册所有 Agent
perception_worker = PerceptionWorkerAgent(
    name="PerceptionWorker",
    model_config_name="gpt-4o"
)

event_aggregator = EventAggregatorAgent(
    name="EventAggregator",
    model_config_name="gpt-4o-mini"
)

memory_orchestrator = MemoryOrchestratorAgent(
    name="MemoryOrchestrator",
    model_config_name="gpt-4o",
    sub_agents=[perception_worker, event_aggregator]
)

memory_gardener = MemoryGardenerAgent(
    name="MemoryGardener",
    model_config_name="gpt-4o",
    storage_backends={
        "vector": vector_store,
        "graph": graph_store,
        "object": object_store
    }
)
```

### 9.2 消息流示例

```python
# 场景：机器人抓取物体
sensor_data = {
    "image": load_image("robot_camera.jpg"),
    "action": "grasp",
    "timestamp": datetime.now()
}

# 1. 传感器数据 → Perception Worker
perception_msg = Msg(
    name="RobotSensor",
    content=sensor_data,
    role="system"
)
perception_result = perception_worker(perception_msg)

# 2. Perception Worker → Event Aggregator
if perception_result.content["state_changed"]:
    event_msg = Msg(
        name="PerceptionWorker",
        content={
            "type": "StateChange",
            "scene_graph": perception_result.content["scene_graph"],
            "l0_ref": perception_result.content["l0_node_id"]
        },
        role="assistant"
    )
    event_result = event_aggregator(event_msg)

# 3. Event Aggregator → Memory Orchestrator
if event_result.content["event_created"]:
    orchestrator_msg = Msg(
        name="EventAggregator",
        content={
            "type": "NewEvent",
            "event_summary": event_result.content["event"],
            "l2_node_id": event_result.content["node_id"]
        },
        role="assistant"
    )
    memory_orchestrator(orchestrator_msg)
```

---

## 10. 评估框架设计

### 10.1 评估指标体系

**学术指标**：
1. **语义正确性**（沿用H-EMV论文）：
   - Correct / Correct Summarized / Correct TMI / Partially Correct / Incorrect
   - 使用 GPT-4o 作为评判器

2. **遗忘后召回率**：
   ```
   Recall@Forgetting = 
       (遗忘后正确回答数) / (遗忘前正确回答数)
   ```
   目标：> 0.85

3. **编辑修正准确率**：
   ```
   Edit_Accuracy = 
       (编辑后正确节点数) / (编辑触发次数)
   ```
   目标：> 0.90

**工程指标**：
1. **Token效率**：
   ```
   Token_Efficiency = 
       (Active-H-EMV查询Token数) / (1-pass Baseline查询Token数)
   ```
   目标：< 0.15（即节省85%）

2. **存储压缩比**：
   ```
   Storage_Compression = 
       (遗忘后存储空间) / (未遗忘存储空间)
   ```
   目标：< 0.4（即压缩60%）

3. **并行搜索加速比**：
   ```
   Speedup = 
       (串行搜索延迟) / (并行搜索延迟)
   ```
   目标：> 2.5x

### 10.2 对比实验设计

```python
# experiments/comprehensive_eval.py

experiments = {
    "Baseline_Gemini_1pass": {
        "method": ZeroShotOnePassQA,
        "config": {"model": "gemini-pro"},
        "metrics": ["semantic_correctness", "token_cost", "latency"]
    },
    
    "H-EMV_Original": {
        "method": OriginalHEMV,
        "config": {"hierarchy": "deep"},
        "metrics": ["semantic_correctness", "token_cost", "storage_growth"]
    },
    
    "Active-H-EMV_No_Forgetting": {
        "method": ActiveHEMV,
        "config": {"enable_forgetting": False, "enable_editing": True},
        "metrics": ["semantic_correctness", "token_cost", "edit_accuracy"]
    },
    
    "Active-H-EMV_Full": {
        "method": ActiveHEMV,
        "config": {"enable_forgetting": True, "enable_editing": True},
        "metrics": ["all"]
    }
}
```

### 10.3 消融实验

**遗忘机制消融**：
```python
# experiments/forgetting_ablation/

ablation_configs = [
    {"alpha": 1.0, "beta": 0.0, "gamma": 0.0},  # 仅访问热度
    {"alpha": 0.0, "beta": 1.0, "gamma": 0.0},  # 仅语义显著性
    {"alpha": 0.0, "beta": 0.0, "gamma": 1.0},  # 仅信息密度
    {"alpha": 0.5, "beta": 0.3, "gamma": 0.2},  # 完整组合（Ours）
]

for config in ablation_configs:
    gardener = MemoryGardenerAgent(utility_weights=config)
    results = run_long_term_test(gardener, duration="30_days")
    log_metrics(results, config)
```

---

## 11. 实施路线图

### 阶段 1: 基础架构 (第1-2周)
- ✅ 更新 requirements.txt
- [ ] 搭建数据库环境（Docker Compose）
- [ ] 实现 storage/ 模块接口
- [ ] 创建 AgentScope 基础 Agent 类

### 阶段 2: 核心 Agent 实现 (第3-5周)
- [ ] Perception-Worker Agent (集成 YOLO + CLIP)
- [ ] Event-Aggregator Agent
- [ ] Memory-Orchestrator Agent
- [ ] 端到端写入链路测试

### 阶段 3: 创新模块 (第6-8周)
- [ ] 效用函数实现（UtilityScorer）
- [ ] 遗忘策略实现（ForgettingPolicy）
- [ ] Memory-Gardener Agent
- [ ] 记忆编辑引擎

### 阶段 4: 优化与集成 (第9-10周)
- [ ] 并行搜索实现（SearchWorker）
- [ ] 容错机制（检查点、死信队列）
- [ ] 性能调优

### 阶段 5: 评估与论文撰写 (第11-14周)
- [ ] TEACh 数据集评估
- [ ] Ego4D 数据集评估
- [ ] 消融实验
- [ ] 撰写毕业论文

---

## 12. 关键技术挑战与解决方案

### 挑战 1: AgentScope 与现有 H-EMV 代码的兼容性

**解决方案**：
- 保留 `em/em_tree.py` 作为数据结构基础
- 创建适配层（Adapter Pattern）
- 逐步迁移，而非重写

```python
# active_hemv/adapters/legacy_adapter.py

class LegacyHEMVAdapter:
    """将现有 EMVerbalizationAPI 包装为 Agent 消息接口"""
    
    def __init__(self, original_api: EMVerbalizationAPI):
        self.api = original_api
    
    def to_agentscope_msg(self, query: str) -> Msg:
        # 转换现有 API 调用为 AgentScope 消息
        return Msg(name="User", content={"query": query}, role="user")
    
    def from_agentscope_msg(self, msg: Msg) -> str:
        # 将 AgentScope 消息转换为现有 API 可处理的格式
        return self.api.answer(msg.content["query"])
```

### 挑战 2: 效用函数参数调优

**解决方案**：
- 使用贝叶斯优化（Bayesian Optimization）
- 目标函数：遗忘后召回率 × 存储压缩比

```python
from bayes_opt import BayesianOptimization

def objective(alpha, beta, gamma):
    gardener = MemoryGardenerAgent(utility_weights=(alpha, beta, gamma))
    results = run_test(gardener)
    return results["recall"] * results["compression"]

optimizer = BayesianOptimization(
    f=objective,
    pbounds={"alpha": (0, 1), "beta": (0, 1), "gamma": (0, 1)},
    constraint=lambda alpha, beta, gamma: alpha + beta + gamma == 1.0
)

optimizer.maximize(n_iter=50)
```

### 挑战 3: 分布式系统的一致性

**解决方案**：
- 引入版本号机制
- 乐观锁（Optimistic Locking）

```python
class ConsistencyChecker:
    def update_with_version_check(self, node_id, new_data):
        current_version = graph_store.get_version(node_id)
        
        if new_data["version"] != current_version:
            # 版本冲突，触发合并策略
            return self.resolve_conflict(node_id, new_data)
        
        # 无冲突，直接更新
        graph_store.update(node_id, new_data, version=current_version + 1)
```

---

## 13. 预期成果与创新点总结

### 学术贡献
1. **首次**将层级记忆结构（H-EMV）与多智能体框架（AgentScope）深度融合
2. 提出基于效用理论的**自适应遗忘算法**，解决长时序记忆的存储爆炸问题
3. 实现**追溯性记忆编辑**，有效降低视觉误差传播
4. 完整评估体系，包括遗忘后召回率、编辑准确率等新指标

### 工程价值
1. 企业级可扩展架构（支持分布式部署）
2. 存储空间压缩 60%+，Token 成本降低 85%+
3. 并行搜索加速 2.5x+
4. 完善的容错与监控机制

### 论文结构建议
```
1. 引言
   - 背景：具身智能与长时序记忆
   - 挑战：静态H-EMV的局限性
   - 贡献：Active-H-EMV的三大创新

2. 相关工作
   - 机器人情景记忆（H-EMV, REM, etc）
   - 多智能体系统（AgentScope, AutoGen）
   - 记忆遗忘理论

3. 方法
   3.1 AgentScope 架构设计
   3.2 效用驱动的遗忘机制
   3.3 追溯性记忆编辑
   3.4 并行化优化

4. 实验
   4.1 数据集与设置
   4.2 对比实验（vs Gemini, H-EMV）
   4.3 消融实验
   4.4 长期运行测试（30天模拟）

5. 结论与展望
   - 局限性：依赖LLM打分的主观性
   - 未来工作：强化学习优化遗忘策略
```

---

## 14. 附录：快速开始指南

### 14.1 环境搭建

```bash
# 1. 克隆项目
git clone <your-repo>
cd AgentScope-Based-Active-H-EMV

# 2. 创建虚拟环境
conda create -n active_hemv python=3.10
conda activate active_hemv

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动数据库（Docker Compose）
docker-compose up -d milvus neo4j minio redis

# 5. 初始化数据库
python scripts/init_databases.py

# 6. 运行测试
python -m pytest tests/
```

### 14.2 运行示例

```bash
# 运行 TEACh 数据集评估
python experiments/run_teach_eval.py \
    --method active_hemv \
    --config active_hemv/config/agent_config.yaml \
    --dataset data/teach/test_set_100.pkl

# 启动交互式问答
python -m active_hemv.demo \
    --history data/armarx_lt_mem/2024-a7a-merged-summary.pkl
```

---

## 15. 联系与支持

如有问题，请参考：
- 代码仓库 Issues
- AgentScope 官方文档: https://github.com/agentscope-ai/agentscope
- H-EMV 论文: https://arxiv.org/abs/[paper-id]

祝您毕业设计顺利！🎓

