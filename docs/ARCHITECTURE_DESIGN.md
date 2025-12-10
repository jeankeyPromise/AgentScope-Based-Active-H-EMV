# Active-H-EMV 系统架构设计

## 🎯 设计理念

**从"被动存储"到"主动管理"**

原始H-EMV提供了优秀的层级化记忆结构，但缺乏主动管理能力。本项目在H-EMV基础上增加了三个后处理Agent，实现类似人脑的记忆管理机制。

---

## 🆚 原始H-EMV vs Active-H-EMV

### 原始H-EMV的特点

**优势** ✅:
- 层级化结构（L0→L4+）高效组织记忆
- 支持交互式检索（从摘要到细节）
- 多模态支持（图像、文本、传感器数据）

**局限** ❌:
- 记忆无限增长，存储空间爆炸
- 相似经验重复存储，冗余度高
- VLM误识别错误永久保留
- 缺乏泛化能力，每次经验独立存储

### Active-H-EMV的改进

| 问题 | 原H-EMV | Active-H-EMV |
|------|---------|--------------|
| **记忆爆炸** | ❌ 线性增长 | ✅ 效用驱动遗忘 |
| **冗余存储** | ❌ 重复保存 | ✅ 整合相似记忆 |
| **错误累积** | ❌ 永久保留 | ✅ 人机回环修正 |
| **知识泛化** | ❌ 无泛化 | ✅ 自动提取模式 |
| **长期运行** | ❌ 需人工清理 | ✅ 全自动维护 |

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│           第1层: 记忆构建（复用H-EMV）                   │
│                                                         │
│  机器人数据 → llm_emv → H-EMV Tree (L0→L4+)           │
│  (传感器/图像/文本)                                     │
│                                                         │
│  特点: 高效构建，已优化，无需修改                        │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ↓ 完整的记忆树
┌─────────────────────────────────────────────────────────┐
│         第2层: 记忆后处理（本项目创新）⭐                │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │  ForgettingAgent (遗忘Agent)             │          │
│  │  ─────────────────────────────           │          │
│  │  功能: 删除低效用记忆                      │          │
│  │  算法: U(n,t) = α·A + β·S + γ·I          │          │
│  │  频率: 每小时/每天                         │          │
│  │  Token: ~24K/天                          │          │
│  └──────────────────────────────────────────┘          │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │  ConsolidationAgent (整合Agent)          │          │
│  │  ───────────────────────────────         │          │
│  │  功能: 提取跨事件模式                      │          │
│  │  灵感: 睡眠记忆巩固                        │          │
│  │  频率: 每晚2点                            │          │
│  │  Token: ~5K/天                           │          │
│  └──────────────────────────────────────────┘          │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │  CorrectionAgent (修正Agent)             │          │
│  │  ────────────────────────────            │          │
│  │  功能: 追溯性错误修正                      │          │
│  │  机制: 用户纠错 + 级联更新                 │          │
│  │  频率: 按需触发                           │          │
│  │  Token: ~50K/天 (50次纠错)              │          │
│  └──────────────────────────────────────────┘          │
│                                                         │
│  MemoryManager: 统一调度和管理                         │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ↓ 优化后的记忆树
┌─────────────────────────────────────────────────────────┐
│         第3层: 存储与检索（复用H-EMV）                   │
│                                                         │
│  - 向量数据库 (Milvus/Chroma): 语义检索                │
│  - H-EMV Tree: 层级遍历                                │
│  - VQA: 查询L0原始图像                                 │
└─────────────────────────────────────────────────────────┘
```

---

## 🧠 认知科学映射

### 人类记忆机制 vs Active-H-EMV

| 人脑过程 | 认知理论 | Active-H-EMV实现 |
|---------|---------|-----------------|
| **感知** | 感觉记忆 | L0 (原始数据) |
| **编码** | 短期记忆 | L1-L2 (场景/事件) |
| **遗忘** | Ebbinghaus曲线 | ForgettingAgent |
| **巩固** | 睡眠整合 | ConsolidationAgent |
| **修正** | 认知失调 | CorrectionAgent |
| **检索** | 线索提取 | H-EMV检索 + VQA |

### 记忆生命周期

```
Day 1: 新记忆生成
  传感器 → L0 (原始) → L1 (场景图) → L2 (事件)
  效用值: U = 1.0 (高)

Day 3: 遗忘开始
  ForgettingAgent运行
  效用值: U = 0.7 (中等)
  → 删除L0原始图像，保留L1摘要

Day 7: 记忆整合
  ConsolidationAgent运行
  识别: "抓苹果" + "抓香蕉" + "抓橙子"
  → 提取模式: "抓取圆形水果"
  → 效用值提升: U = 0.9

Day 30: 长期记忆
  重要模式保留: U = 0.9
  不重要细节删除: U < 0.2
```

---

## 📝 三个Agent详细设计

### 1. ForgettingAgent (遗忘Agent)

#### 设计目标
解决原H-EMV的**记忆爆炸问题**，避免存储无限增长。

#### 核心算法

**效用函数**:
```
U(n, t) = α·A(n, t) + β·S(n) + γ·I(n)

其中:
- A(n, t): 访问热度 (基于Ebbinghaus遗忘曲线)
  A(n, t) = (1/(N+1)) Σ exp(-λ·Δt_i)
  
- S(n): 语义显著性 (LLM评估)
  S(n) ∈ [0, 1]
  
- I(n): 信息密度 (唯一性)
  I(n) = 1 - max_j similarity(n, n_j)

参数:
- α = 0.5 (访问权重)
- β = 0.3 (语义权重)
- γ = 0.2 (密度权重)
- λ = 0.1 (时间衰减率)
```

**三级遗忘策略**:
```python
if U(n) < 0.2:  # 低效用
    if n.level in [L0, L1]:
        delete_raw_data(n)  # 删除原始数据
    else:
        merge_with_siblings(n)  # 合并邻居节点

elif U(n) < 0.5:  # 中效用
    compress(n)  # 压缩存储

else:  # 高效用
    keep(n)  # 完整保留
```

#### 实现细节

**文件**: `active_hemv/agents/forgetting_agent.py`

**核心方法**:
```python
class ForgettingAgent(AgentBase):
    def reply(self, x: Msg) -> Msg:
        memory_tree = x.content["memory_tree"]
        current_time = x.content.get("time", datetime.now())
        
        # 1. 遍历树，计算效用
        for node in traverse_tree(memory_tree):
            node.utility = self.utility_scorer.compute(
                node, current_time
            )
        
        # 2. 应用遗忘策略
        stats = self.forgetting_policy.apply(memory_tree)
        
        # 3. 返回结果
        return Msg(
            name=self.name,
            content={
                "updated_tree": memory_tree,
                "forgotten_nodes": stats["forgotten"],
                "compressed_nodes": stats["compressed"]
            },
            role="assistant"
        )
```

#### 运行策略
- **频率**: 每小时自动运行（可配置）
- **Token消耗**: ~1000 tokens/次 × 24次 = 24K/天
- **效果**: 存储压缩60%+

---

### 2. ConsolidationAgent (整合Agent)

#### 设计目标
解决原H-EMV的**冗余存储和泛化能力弱**问题。

#### 灵感来源
人类在睡眠中会整合白天的记忆，提取通用模式，这一过程称为"记忆巩固"。

#### 核心算法

**相似记忆识别**:
```
similarity(m1, m2) = cosine(embedding(m1), embedding(m2))

如果 similarity > 0.85:
    → m1 和 m2 被归为一组
```

**模式提取**:
```python
# 示例: 3次抓取经验
memories = [
    "机器人抓取红苹果放入篮子",
    "机器人抓取青苹果放入篮子", 
    "机器人抓取黄香蕉放入篮子"
]

# LLM提取通用模式
pattern = consolidation_agent.extract_pattern(memories)
# → "机器人学会了抓取圆形水果的通用技能"

# 创建整合节点
consolidated_node = HigherLevelSummary(
    nl_summary=pattern,
    children=memories,
    consolidated=True,
    utility=0.9  # 整合节点效用高
)
```

#### 实现细节

**文件**: `active_hemv/agents/consolidation_agent.py`

**核心方法**:
```python
class ConsolidationAgent(AgentBase):
    def reply(self, x: Msg) -> Msg:
        memory_tree = x.content["memory_tree"]
        
        # 1. 查找相似记忆组
        similar_groups = self.find_similar_memories(
            memory_tree,
            threshold=0.85
        )
        
        # 2. 使用LLM提取模式
        patterns = []
        for group in similar_groups:
            pattern = self.llm_extract_pattern(group)
            patterns.append(pattern)
        
        # 3. 创建整合节点
        for pattern, group in zip(patterns, similar_groups):
            create_consolidated_node(
                memory_tree, pattern, group
            )
        
        # 4. 强化重要记忆
        reinforce_important_memories(memory_tree)
        
        return Msg(
            name=self.name,
            content={
                "updated_tree": memory_tree,
                "patterns_extracted": len(patterns)
            },
            role="assistant"
        )
```

#### 运行策略
- **频率**: 每晚2:00自动运行（模拟睡眠）
- **Token消耗**: ~5000 tokens/次 × 1次 = 5K/天
- **效果**: 提取通用模式，提升泛化能力

---

### 3. CorrectionAgent (修正Agent)

#### 设计目标
解决原H-EMV的**错误累积问题**，特别是VLM误识别。

#### 问题场景
```
Day 1: VLM误识别
  用户: "拿苹果"
  VLM: 识别为"梨子" ❌
  存储: L0[image] → L1["场景中有梨子"] → L2["拿梨子事件"]

Day 3: 用户发现错误
  用户: "那不是梨子，是青苹果"
  
  原H-EMV: 无法修正，错误永久保留 ❌
  Active-H-EMV: CorrectionAgent自动修正 ✅
```

#### 核心算法

**错误定位**:
```python
def locate_error_source(memory_tree, query, correction):
    # 1. 语义搜索找到相关节点
    candidates = semantic_search(memory_tree, query)
    
    # 2. 找到包含错误信息的节点
    for node in candidates:
        if "梨子" in node.nl_summary:
            return node  # 找到错误源
    
    return None
```

**级联更新**:
```python
def propagate_update(error_node, correction):
    # 1. 修正当前节点
    error_node.nl_summary = llm_correct(
        error_node.nl_summary,
        correction
    )
    
    # 2. 向上更新父节点
    parent = error_node.parent
    while parent:
        parent.nl_summary = llm_update_summary(
            parent.nl_summary,
            old="梨子",
            new="青苹果"
        )
        parent = parent.parent
    
    # 3. 记录修正历史
    error_node.correction_history.append({
        "time": datetime.now(),
        "original": "梨子",
        "corrected": "青苹果"
    })
```

#### 实现细节

**文件**: `active_hemv/agents/correction_agent.py`

**核心方法**:
```python
class CorrectionAgent(AgentBase):
    def reply(self, x: Msg) -> Msg:
        memory_tree = x.content["memory_tree"]
        query = x.content["query"]
        correction = x.content["user_correction"]
        
        # 1. 定位错误节点
        error_node = self.locate_error_source(
            memory_tree, query
        )
        
        if not error_node:
            return Msg(content={"error": "未找到错误源"})
        
        # 2. LLM生成修正
        corrected_summary = self.model(
            f"将'{error_node.nl_summary}'中的错误"
            f"根据用户纠正'{correction}'修改"
        ).text
        
        # 3. 更新节点
        error_node.nl_summary = corrected_summary
        error_node.corrected = True
        
        # 4. 级联更新父节点
        nodes_updated = self.propagate_update_upward(
            error_node, correction
        )
        
        return Msg(
            name=self.name,
            content={
                "updated_tree": memory_tree,
                "nodes_updated": nodes_updated
            },
            role="assistant"
        )
```

#### 运行策略
- **频率**: 按需触发（用户纠错时）
- **Token消耗**: ~1000 tokens/次 × 50次 = 50K/天
- **效果**: 确保记忆准确性，避免错误传播

---

## 🔄 Agent协作流程

### 场景1: 正常运行（无用户干预）

```
Hour 0: 初始化
  └─ 加载H-EMV Tree

Hour 1: 第一次遗忘周期
  └─ ForgettingAgent运行
     ├─ 计算所有节点效用
     ├─ 删除低效用L0数据
     └─ 压缩中效用节点

Hour 2-23: 持续运行
  └─ 每小时运行ForgettingAgent

Day 1, 02:00: 第一次整合
  └─ ConsolidationAgent运行
     ├─ 查找相似记忆
     ├─ 提取3个通用模式
     └─ 强化重要记忆
```

### 场景2: 用户纠错

```
用户操作:
  Query: "昨天晚上整理的最后一个水果是什么颜色？"
  System: "红色"
  User: "不对，是青苹果，绿色的"

系统响应:
  1. CorrectionAgent被触发
  2. 定位错误节点: L0[image_123]
  3. 修正: "红苹果" → "青苹果"
  4. 级联更新:
     - L1: 场景图中的对象
     - L2: "整理红苹果" → "整理青苹果"
     - L3: 更新事件摘要
  5. 返回: "已修正3个节点"
```

---

## 💾 数据流

### 记忆树数据结构

```python
class MemoryNode:
    """记忆节点（扩展自H-EMV）"""
    
    # H-EMV原有字段
    nl_summary: str          # 自然语言摘要
    level: str               # L0/L1/L2/L3/L4+
    children: List[MemoryNode]
    parent: MemoryNode
    timestamp: datetime
    
    # Active-H-EMV新增字段 ⭐
    utility_score: float     # 效用值 [0,1]
    access_history: List[datetime]  # 访问历史
    consolidated: bool       # 是否为整合节点
    corrected: bool          # 是否被修正过
    correction_history: List[dict]  # 修正历史
    
    # 访问计数（用于A(n,t)计算）
    access_count: int
    last_access: datetime
```

### Msg通信格式

所有Agent使用统一的`Msg`格式通信：

```python
# ForgettingAgent输入
Msg(
    name="Scheduler",
    content={
        "type": "forgetting_cycle",
        "memory_tree": tree,
        "time": datetime.now()
    },
    role="system"
)

# ForgettingAgent输出
Msg(
    name="ForgettingAgent",
    content={
        "updated_tree": tree,
        "forgotten_nodes": 42,
        "compressed_nodes": 18
    },
    role="assistant"
)
```

---

## 🎯 关键设计决策

### 决策1: 为什么是3个Agent而不是5个？

**废弃方案**: 每层都是Agent (L0→L1, L2, L3+, 维护, 检索)
- ❌ Token消耗巨大
- ❌ 架构过于复杂
- ❌ 每次查询都要经过多个Agent

**当前方案**: 3个后处理Agent
- ✅ 低频运行，Token消耗低
- ✅ 职责清晰（遗忘、整合、修正）
- ✅ 符合人类记忆机制

### 决策2: 为什么复用H-EMV而不是从零开始？

**理由**:
1. H-EMV的层级结构已被证明有效
2. llm_emv的检索代码已高度优化
3. 我们的重点是**主动管理**，而非重新发明数据结构
4. 站在巨人肩膀上，专注于创新点

### 决策3: 为什么使用AgentScope框架？

**原因**:
1. **LLM集成**: 自动处理API调用、重试、成本跟踪
2. **统一接口**: 标准`Msg`格式，易于扩展
3. **分布式支持**: 未来可轻松扩展到多台服务器
4. **学术意义**: 主流多智能体框架，体现前沿技术

详见: `docs/WHY_USE_AGENT_FRAMEWORK.md`

---

## 📊 性能指标

### 预期目标

| 指标 | 目标值 | 说明 |
|-----|--------|------|
| **存储压缩** | 60%+ | 遗忘后节点数减少 |
| **检索加速** | 2-3x | 节点减少带来的速度提升 |
| **召回率** | >85% | 遗忘后仍能回答关键问题 |
| **修正准确率** | >90% | 级联更新的正确性 |
| **模式提取率** | >70% | 从重复经验中提取规律 |

### 与原H-EMV对比

| 维度 | 原H-EMV | Active-H-EMV | 提升 |
|------|---------|--------------|------|
| 存储空间 | 无限增长 | 收敛到稳定值 | ✅ |
| 冗余度 | 高 | 低（整合后） | ✅ |
| 错误率 | 累积 | 可修正 | ✅ |
| 泛化能力 | 无 | 自动提取模式 | ✅ |
| 维护成本 | 需人工 | 全自动 | ✅ |

---

## 🚀 部署架构

### 单机部署（毕设阶段）

```
┌─────────────────────────────┐
│  Python进程                 │
│  ├─ MemoryManager           │
│  ├─ ForgettingAgent         │
│  ├─ ConsolidationAgent      │
│  └─ CorrectionAgent         │
│                             │
│  ├─ H-EMV Tree (内存)       │
│  └─ Vector Store (Chroma)   │
└─────────────────────────────┘
```

### 分布式部署（未来扩展）

```
┌─────────────────┐
│  服务器1        │
│  MemoryManager  │  ← 调度中心
└────┬────┬───┬───┘
     │    │   │
   ┌─┘  ┌─┘  └─┐
   │    │      │
┌──▼──┐ ┌▼───┐ ┌▼────┐
│ SV2 │ │SV3 │ │ SV4 │
│Forg │ │Cons│ │Corr │
└─────┘ └────┘ └─────┘

AgentScope自动处理分布式通信 ✅
```

---

## 📚 技术栈总结

| 组件 | 技术选型 | 用途 |
|------|---------|------|
| **多智能体框架** | AgentScope | Agent基础设施 |
| **记忆结构** | H-EMV | 层级化数据组织 |
| **LLM接口** | LangChain | 模型调用封装 |
| **向量检索** | Chroma | 语义搜索 |
| **调度器** | APScheduler | 定时任务 |
| **日志** | Loguru | 结构化日志 |

---

## ✅ 总结

Active-H-EMV通过**分离式架构**实现了：

1. **保留H-EMV优势**: 层级结构、高效检索
2. **添加主动管理**: 遗忘、整合、修正
3. **降低运行成本**: 低频后处理，Token消耗低
4. **提升系统质量**: 存储压缩、知识泛化、错误修正

**核心思想**: 不是重新发明轮子，而是在优秀的基础上添加智能管理！

---

**📖 相关文档**:
- `docs/WHY_USE_AGENT_FRAMEWORK.md` - 为什么用Agent框架
- `examples/simple_usage.py` - 使用示例
- `README.md` - 项目概览

