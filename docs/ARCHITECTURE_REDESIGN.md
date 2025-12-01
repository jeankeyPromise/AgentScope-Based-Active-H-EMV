# Active-H-EMV 架构重新设计

## 🎯 核心理念变化

### 原设计（已废弃）
```
每一层 = 一个Agent
├─ PerceptionWorkerAgent (L0→L1)
├─ EventAggregatorAgent (L2)
├─ MemoryOrchestratorAgent (L3+)
└─ MemoryGardenerAgent (维护)

问题：
❌ Token消耗巨大（每层都要LLM调用）
❌ 架构过度复杂
❌ 不符合实际记忆机制
```

### 新设计（推荐）⭐
```
H-EMV Tree (数据结构) + 三个后处理Agent

1. H-EMV Tree (em/em_tree.py)
   - 保持原有的层级结构 (L0→L4+)
   - 纯数据结构，不涉及Agent
   - 使用现有的llm_emv代码构建

2. 三个记忆后处理Agent (模拟人脑)
   ├─ ForgettingAgent   (主动遗忘)
   ├─ ConsolidationAgent (记忆整合/巩固)
   └─ CorrectionAgent   (记忆修正)
```

---

## 🧠 类比人类记忆机制

```
人类记忆过程:
  感知 → 短期记忆 → 睡眠整合 → 长期记忆
   ↓        ↓           ↓           ↓
  L0      L1-L2     整合Agent    L3-L4+
                        ↓
                   遗忘Agent (删除不重要)
                        ↓
                   修正Agent (纠正错误)
```

---

## 📊 新架构图

```
┌─────────────────────────────────────────────────────────────┐
│                  输入层 (现有H-EMV)                          │
│  机器人传感器 → em_tree.py → 构建 L0-L4+ 树结构             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ↓ 初始记忆树 (未优化)
┌─────────────────────────────────────────────────────────────┐
│            记忆后处理层 (AgentScope)                         │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │  ForgettingAgent (遗忘Agent)                 │          │
│  │  - 计算效用值 U(n,t)                         │          │
│  │  - 删除低效用节点                             │          │
│  │  - 压缩存储                                   │          │
│  │  周期: 每小时/每天                            │          │
│  └──────────────────────────────────────────────┘          │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │  ConsolidationAgent (整合Agent)              │          │
│  │  - 合并相似记忆                               │          │
│  │  - 提取跨事件模式                             │          │
│  │  - 生成高层抽象                               │          │
│  │  周期: 每晚 (模拟睡眠)                        │          │
│  └──────────────────────────────────────────────┘          │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │  CorrectionAgent (修正Agent)                 │          │
│  │  - 检测矛盾记忆                               │          │
│  │  - 人机回环纠错                               │          │
│  │  - 级联更新                                   │          │
│  │  触发: 按需 (用户纠错时)                      │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ↓ 优化后的记忆树
┌─────────────────────────────────────────────────────────────┐
│              存储层 (向量/图/对象数据库)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 工作流程

### 阶段1: 记忆构建（使用现有代码）

```python
# 使用现有的 llm_emv 代码
from llm_emv.setup import setup_llm_emv
from em.em_tree import HigherLevelSummary

# 构建初始记忆树 (不涉及Agent)
lmp = setup_llm_emv(config, history=None)
memory_tree = build_memory_from_robot_data(robot_data)

# memory_tree 是标准的 HigherLevelSummary 结构
# 包含 L0-L4+ 所有层级
```

### 阶段2: 记忆后处理（AgentScope Agent）

```python
from active_hemv.agents import (
    ForgettingAgent,
    ConsolidationAgent,
    CorrectionAgent
)
import agentscope

# 初始化AgentScope
agentscope.init(
    model_configs={"model_type": "openai_chat", ...}
)

# 创建三个Agent
forgetting_agent = ForgettingAgent(
    name="ForgettingAgent",
    model_config_name="gpt-4o-mini",  # 遗忘用简单模型
    utility_weights=(0.5, 0.3, 0.2)
)

consolidation_agent = ConsolidationAgent(
    name="ConsolidationAgent",
    model_config_name="gpt-4o",  # 整合用强模型
    similarity_threshold=0.85
)

correction_agent = CorrectionAgent(
    name="CorrectionAgent",
    model_config_name="gpt-4o"  # 修正用强模型
)

# Agent之间的协作
from agentscope.message import Msg

# 每小时: 遗忘
forgetting_msg = Msg(
    name="Scheduler",
    content={"type": "forgetting_cycle", "memory_tree": memory_tree},
    role="system"
)
memory_tree = forgetting_agent(forgetting_msg).content["updated_tree"]

# 每晚: 整合（模拟睡眠）
consolidation_msg = Msg(
    name="Scheduler",
    content={"type": "consolidate", "memory_tree": memory_tree},
    role="system"
)
memory_tree = consolidation_agent(consolidation_msg).content["updated_tree"]

# 按需: 修正（用户纠错时）
if user_correction:
    correction_msg = Msg(
        name="User",
        content={
            "type": "correction",
            "query": "昨天的苹果是红色的",
            "correction": "不，是绿色的",
            "memory_tree": memory_tree
        },
        role="user"
    )
    memory_tree = correction_agent(correction_msg).content["updated_tree"]
```

---

## 📝 三个Agent的详细设计

### 1. ForgettingAgent (遗忘Agent)

**输入**:
- `memory_tree`: 完整的记忆树
- `current_time`: 当前时间

**处理逻辑**:
```python
def reply(self, x: Msg) -> Msg:
    memory_tree = x.content["memory_tree"]
    
    # 1. 遍历树，计算每个节点的效用值
    for node in traverse_tree(memory_tree):
        utility = self.utility_scorer.compute(node)
        node.utility_score = utility
    
    # 2. 根据效用值决定保留/删除/压缩
    for node in traverse_tree(memory_tree):
        if node.utility_score < THRESHOLD_LOW:
            if node.level in ["L0", "L1"]:
                # 删除原始数据，保留摘要
                delete_raw_data(node)
            elif node.level in ["L2", "L3"]:
                # 合并为更粗粒度节点
                merge_with_neighbors(node)
    
    # 3. 返回优化后的树
    return Msg(
        name=self.name,
        content={
            "type": "forgetting_result",
            "updated_tree": memory_tree,
            "nodes_forgotten": stats
        },
        role="assistant"
    )
```

**创新点**:
- ✅ 仅一个Agent，处理整棵树
- ✅ 不改变树结构，只删除/压缩数据
- ✅ Token消耗：仅在需要LLM评估显著性时

---

### 2. ConsolidationAgent (整合Agent)

**灵感**: 模拟人类睡眠中的记忆巩固过程

**输入**:
- `memory_tree`: 一天的记忆树
- `consolidation_mode`: "daily" | "weekly"

**处理逻辑**:
```python
def reply(self, x: Msg) -> Msg:
    memory_tree = x.content["memory_tree"]
    
    # 1. 查找相似的记忆片段
    similar_groups = self.find_similar_memories(memory_tree)
    # 例如: ["抓取苹果", "抓取香蕉", "抓取橙子"]
    
    # 2. 使用LLM提取跨事件模式
    for group in similar_groups:
        pattern = self.llm_extract_pattern(group)
        # "机器人学会了抓取圆形水果的通用模式"
        
        # 创建一个新的高层节点
        consolidated_node = HigherLevelSummary(
            nl_summary=pattern,
            children=group,
            consolidated=True  # 标记为整合节点
        )
    
    # 3. 强化重要记忆（增加效用值）
    for node in memory_tree:
        if node.consolidated or node.access_count > 10:
            node.utility_score += 0.2  # 巩固加分
    
    return Msg(
        name=self.name,
        content={
            "type": "consolidation_result",
            "updated_tree": memory_tree,
            "patterns_found": len(similar_groups)
        },
        role="assistant"
    )
```

**创新点**:
- ✅ 提取跨事件模式（类似人脑的泛化能力）
- ✅ 强化重要记忆（模拟记忆巩固）
- ✅ 减少冗余（合并相似记忆）

---

### 3. CorrectionAgent (修正Agent)

**触发**: 用户纠错时

**输入**:
- `memory_tree`: 记忆树
- `query`: 原始查询
- `system_answer`: 系统的错误回答
- `user_correction`: 用户的纠正

**处理逻辑**:
```python
def reply(self, x: Msg) -> Msg:
    memory_tree = x.content["memory_tree"]
    query = x.content["query"]
    correction = x.content["correction"]
    
    # 1. 定位错误源节点
    error_node = self.locate_error_source(
        memory_tree, query, correction
    )
    
    # 2. 使用LLM生成修正后的描述
    corrected_summary = self.llm_correct(
        original=error_node.nl_summary,
        correction=correction
    )
    
    # 3. 更新节点
    error_node.nl_summary = corrected_summary
    error_node.corrected = True
    error_node.correction_history.append({
        "time": datetime.now(),
        "correction": correction
    })
    
    # 4. 级联更新父节点
    self.propagate_update_upward(error_node, memory_tree)
    
    return Msg(
        name=self.name,
        content={
            "type": "correction_result",
            "updated_tree": memory_tree,
            "corrected_node": error_node.node_id
        },
        role="assistant"
    )
```

**创新点**:
- ✅ 不需要VQA（直接基于用户纠正）
- ✅ 保留修正历史（可追溯）
- ✅ 级联更新保证一致性

---

## 💰 Token消耗对比

### 原设计（每层都是Agent）
```
每次查询:
├─ PerceptionWorker: 500 tokens (YOLO结果 → 场景图)
├─ EventAggregator: 800 tokens (场景图 → 事件描述)
├─ Orchestrator: 2000 tokens (递归摘要生成)
└─ 总计: ~3300 tokens/查询

每天1000次查询 → 3,300,000 tokens/天 ≈ $50/天
```

### 新设计（仅后处理Agent）
```
记忆构建: 使用现有llm_emv代码（已优化）
├─ H-EMV原有流程: ~500 tokens/查询

后处理（低频）:
├─ ForgettingAgent: 每小时1次 × 1000 tokens = 24,000 tokens/天
├─ ConsolidationAgent: 每晚1次 × 5000 tokens = 5,000 tokens/天
└─ CorrectionAgent: 按需 × ~50次/天 × 1000 tokens = 50,000 tokens/天

每天1000次查询 → 500,000 + 79,000 = 579,000 tokens/天 ≈ $8/天

节省: 82% ✅
```

---

## 🔧 实现优先级

### P0: 核心功能（第1周）
- [ ] 重构 ForgettingAgent（基于现有memory_gardener.py）
- [ ] 实现 ConsolidationAgent（新建）
- [ ] 实现 CorrectionAgent（基于现有editing_engine.py）
- [ ] 集成现有 llm_emv 代码

### P1: 系统整合（第2周）
- [ ] 创建 MemoryManager（统一管理三个Agent）
- [ ] 实现调度器（定时触发Agent）
- [ ] 添加Agent间协作机制

### P2: 评估验证（第3-4周）
- [ ] Token消耗对比实验
- [ ] 记忆质量评估
- [ ] 论文撰写

---

## 📖 论文叙述角度

### 创新点1: 分离数据结构与处理逻辑
> "与传统方法将每层映射为Agent不同，我们将H-EMV作为纯数据结构，
> 仅在记忆后处理阶段引入Agent，显著降低Token消耗（降低82%）"

### 创新点2: 模拟人脑记忆机制
> "受人类记忆巩固理论启发，我们设计了三个后处理Agent：
> - ForgettingAgent模拟遗忘曲线
> - ConsolidationAgent模拟睡眠记忆巩固
> - CorrectionAgent模拟认知修正"

### 创新点3: 低频高效处理
> "三个Agent以低频率运行（小时/天级别），而非实时处理，
> 在保证记忆质量的同时，极大降低计算成本"

---

## 🎯 与导师讨论的对齐

✅ **取消每层Agent映射** - 改为纯数据结构  
✅ **降低Token消耗** - 仅后处理使用LLM  
✅ **三个功能Agent** - 遗忘、整合、修正  
✅ **模拟人脑** - 初级记忆→深层记忆转化  
✅ **保留H-EMV优势** - 层级结构和检索效率  

---

## 📚 参考文献补充

新增需要引用的理论：
1. **Ebbinghaus遗忘曲线** - ForgettingAgent理论基础
2. **记忆巩固理论（Memory Consolidation）** - ConsolidationAgent灵感来源
3. **认知失调理论（Cognitive Dissonance）** - CorrectionAgent原理

---

这个新设计更加务实、创新，且符合您导师的建议！

