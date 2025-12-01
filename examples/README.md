# Active-H-EMV 使用示例

## 📁 文件说明

- `simple_usage.py` - 简单使用示例，演示三个Agent的基本用法
- (待添加) `advanced_usage.py` - 高级用法，包括自动调度
- (待添加) `integration_with_llm_emv.py` - 与现有llm_emv代码集成

## 🚀 快速开始

### 1. 准备环境

```bash
# 安装依赖
pip install -r requirements.txt

# 配置API Key
export OPENAI_API_KEY="your-key-here"
# 或在代码中直接设置
```

### 2. 运行简单示例

```bash
python examples/simple_usage.py
```

**预期输出**:
```
======================================================================
Active-H-EMV 简单使用示例
新架构：H-EMV数据结构 + 三个后处理Agent
======================================================================

📝 步骤1: 初始化AgentScope...
✅ AgentScope已初始化

📝 步骤2: 加载记忆树...
✅ 记忆树已加载: 2024-a7a-merged-summary.pkl

📝 步骤3: 创建MemoryManager...
✅ MemoryManager已创建

======================================================================
🧠 演示1: 运行遗忘Agent
======================================================================
✅ 遗忘周期完成:
   - 处理节点数: 245
   - 遗忘节点数: 32
   - 压缩节点数: 18
   - 节省空间: 28.50 MB

======================================================================
🌙 演示2: 运行整合Agent（模拟睡眠）
======================================================================
✅ 整合周期完成:
   - 合并记忆数: 12
   - 提取模式数: 3
   - 强化记忆数: 45

======================================================================
🔧 演示3: 运行修正Agent（用户纠错）
======================================================================
✅ 记忆修正完成:
   - 更新节点数: 5
   - 级联更新成功

======================================================================
📊 系统统计信息
======================================================================
...

🎉 示例运行完毕！
```

## 📖 核心概念

### 新架构 vs 旧架构

**旧架构**（已废弃）:
```python
# 每一层都是Agent（Token消耗大）
PerceptionWorkerAgent (L0→L1)
EventAggregatorAgent (L2)
MemoryOrchestratorAgent (L3+)
```

**新架构**（推荐）:
```python
# H-EMV作为数据结构 + 三个后处理Agent
memory_tree = build_h_emv_tree(data)  # 使用现有llm_emv

# 后处理Agent（低频运行，Token消耗少）
ForgettingAgent()      # 每小时
ConsolidationAgent()   # 每晚
CorrectionAgent()      # 按需
```

### 三个Agent的作用

1. **ForgettingAgent（遗忘Agent）**
   - 灵感：Ebbinghaus遗忘曲线
   - 功能：计算效用值U(n,t)，删除低效用记忆
   - 运行：每小时/每天
   - Token消耗：低（仅评估显著性时需要LLM）

2. **ConsolidationAgent（整合Agent）**
   - 灵感：睡眠记忆巩固理论
   - 功能：合并相似记忆，提取跨事件模式
   - 运行：每晚（模拟睡眠）
   - Token消耗：中等（需要LLM生成模式）

3. **CorrectionAgent（修正Agent）**
   - 灵感：认知失调理论
   - 功能：定位并修正错误记忆，级联更新
   - 运行：按需（用户纠错时）
   - Token消耗：低-中等（需要LLM生成修正描述）

## 💡 使用场景

### 场景1: 日常运行

```python
# 初始化
manager = MemoryManager(
    memory_tree=tree,
    enable_auto_schedule=True  # 自动调度
)

# 系统会自动：
# - 每小时运行遗忘周期
# - 每晚2点运行整合周期
# - 按需处理用户纠错
```

### 场景2: 手动控制

```python
# 初始化（禁用自动调度）
manager = MemoryManager(
    memory_tree=tree,
    enable_auto_schedule=False
)

# 手动触发
manager.run_forgetting_cycle()         # 遗忘
manager.run_consolidation_cycle()      # 整合
manager.correct_memory(...)            # 修正
```

### 场景3: 与现有代码集成

```python
# 使用现有llm_emv构建记忆树
from llm_emv.setup import setup_llm_emv

lmp = setup_llm_emv(config)
memory_tree = build_memory(lmp, robot_data)

# 交给MemoryManager后处理
manager = MemoryManager(memory_tree=memory_tree)
manager.run_forgetting_cycle()
manager.run_consolidation_cycle()
```

## 📊 Token消耗对比

| 方法 | 每次查询 | 每天（1000次查询） | 月成本 |
|------|---------|-------------------|--------|
| 旧架构（每层Agent） | ~3300 tokens | 3,300,000 tokens | ~$1500 |
| 新架构（后处理Agent） | ~500 tokens | 579,000 tokens | ~$240 |
| **节省** | **85%** | **82%** | **84%** |

## ⚙️ 配置选项

```python
manager = MemoryManager(
    memory_tree=tree,
    
    # 调度配置
    forgetting_interval_hours=1.0,      # 遗忘间隔
    consolidation_time="02:00",         # 整合时间
    enable_auto_schedule=True,          # 自动调度
    
    # 存储配置
    storage_path="./memory_tree.pkl",   # 自动保存路径
    
    # Agent配置
    forgetting={
        "model_config_name": "gpt-4o-mini",  # 遗忘用轻量模型
        "utility_weights": (0.5, 0.3, 0.2),  # α, β, γ
        "threshold_low": 0.2                 # 低效用阈值
    },
    consolidation={
        "model_config_name": "gpt-4o",       # 整合用强模型
        "similarity_threshold": 0.85          # 相似度阈值
    },
    correction={
        "model_config_name": "gpt-4o"        # 修正用强模型
    }
)
```

## 🐛 故障排查

### 问题1: 记忆树加载失败
```python
# 检查文件是否存在
if not Path(memory_tree_path).exists():
    print("文件不存在，请先生成记忆树")
    
# 检查pickle格式
try:
    with open(path, 'rb') as f:
        tree = pickle.load(f)
except Exception as e:
    print(f"加载失败: {e}")
```

### 问题2: LLM调用失败
```python
# 检查API Key
import os
print(os.getenv("OPENAI_API_KEY"))

# 检查模型配置
agentscope.init(model_configs=[...])
```

### 问题3: 调度器不工作
```python
# 检查调度器状态
if manager.scheduler:
    print("调度器已启动")
    print(manager.scheduler.get_jobs())
else:
    print("调度器未启用")
```

## 📚 更多资源

- [完整文档](../ARCHITECTURE_REDESIGN.md)
- [API参考](../PROJECT_SUMMARY.md)
- [论文思路](../QUICK_START_GUIDE.md)

