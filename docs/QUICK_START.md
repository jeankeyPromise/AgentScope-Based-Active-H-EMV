# Active-H-EMV 快速开始指南

## 🎯 5分钟快速开始

本指南将帮助你在5分钟内运行Active-H-EMV系统。

---

## 📋 前置要求

### 必需
- Python >= 3.10
- OpenAI API Key (或其他兼容的LLM API)

### 推荐
- 至少8GB RAM
- SSD存储（提升向量检索速度）

---

## ⚡ 快速安装

### 步骤1: 克隆项目

```bash
git clone https://github.com/your-repo/Active-H-EMV.git
cd Active-H-EMV
```

### 步骤2: 安装依赖

```bash
pip install -r requirements.txt
```

<details>
<summary>如果遇到安装问题，点击展开</summary>

**常见问题**:

1. **PyTorch安装失败**
   ```bash
   # CPU版本
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   
   # CUDA版本（如果有GPU）
   pip install torch --index-url https://download.pytorch.org/whl/cu118
   ```

2. **Chroma安装失败**
   ```bash
   pip install chromadb --no-cache-dir
   ```

3. **依赖冲突**
   ```bash
   # 使用虚拟环境
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或 venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
</details>

### 步骤3: 配置API Key

```bash
# Linux/Mac
export OPENAI_API_KEY="your-api-key-here"

# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key-here"

# 或者在Python代码中设置
```

---

## 🚀 运行第一个示例

### 方式1: 使用提供的示例数据

```bash
python examples/simple_usage.py
```

**预期输出**:
```
[2024-12-04 10:00:00] 初始化AgentScope...
[2024-12-04 10:00:01] 加载记忆树... (100个节点)
[2024-12-04 10:00:02] 创建MemoryManager...
[2024-12-04 10:00:03] ✅ ForgettingAgent: 删除了15个低效用节点
[2024-12-04 10:00:05] ✅ ConsolidationAgent: 提取了3个通用模式
[2024-12-04 10:00:06] ✅ 系统就绪！

记忆统计:
- 总节点数: 85
- 已遗忘: 15
- 已整合: 3组
- 压缩率: 15%
```

### 方式2: 使用自己的数据

```python
import agentscope
from active_hemv.agents import MemoryManager
import pickle

# 1. 初始化AgentScope
agentscope.init(model_configs=[{
    "model_type": "openai_chat",
    "config_name": "gpt-4o",
    "model_name": "gpt-4o",
    "api_key": "your-api-key"
}])

# 2. 加载你的H-EMV记忆树
with open("your_memory_tree.pkl", 'rb') as f:
    memory_tree = pickle.load(f)

# 3. 创建MemoryManager
manager = MemoryManager(
    memory_tree=memory_tree,
    enable_auto_schedule=True,  # 自动运行
    storage_path="./memory.pkl"
)

# 4. 完成！Agent会自动在后台运行
print("✅ Active-H-EMV已启动")
```

---

## 📖 基础使用

### 使用场景1: 自动后台管理

```python
from active_hemv.agents import MemoryManager

# 创建管理器（启用自动调度）
manager = MemoryManager(
    memory_tree=your_tree,
    enable_auto_schedule=True,
    forgetting_interval_hours=1.0,  # 每小时遗忘一次
    consolidation_time="02:00",     # 每晚2点整合
    storage_path="./memory.pkl"
)

# Agent会自动运行，你无需手动调用！
# - ForgettingAgent: 每小时自动清理
# - ConsolidationAgent: 每晚自动整合
# - CorrectionAgent: 用户纠错时运行

# 查看统计信息
stats = manager.get_stats()
print(f"""
记忆统计:
- 总节点数: {stats['total_nodes']}
- 已遗忘: {stats['forgotten_nodes']}
- 已整合: {stats['consolidated_groups']}
- 已修正: {stats['corrections']}
- 压缩率: {stats['compression_rate']:.1%}
""")
```

### 使用场景2: 手动控制

```python
from active_hemv.agents import MemoryManager

# 创建管理器（禁用自动调度）
manager = MemoryManager(
    memory_tree=your_tree,
    enable_auto_schedule=False  # 手动控制
)

# 手动运行遗忘周期
print("运行遗忘Agent...")
forgetting_stats = manager.run_forgetting_cycle()
print(f"✅ 遗忘了 {forgetting_stats['forgotten']} 个节点")

# 手动运行整合周期
print("运行整合Agent...")
consolidation_stats = manager.run_consolidation_cycle(mode="daily")
print(f"✅ 提取了 {consolidation_stats['patterns']} 个模式")

# 保存到磁盘
manager.save("./memory.pkl")
print("✅ 已保存记忆树")
```

### 使用场景3: 用户纠错

```python
# 场景: 用户发现系统回答错误
query = "昨天晚上的苹果是什么颜色？"
system_answer = "红色"
user_correction = "不对，是青苹果，绿色的"

# 调用修正Agent
result = manager.correct_memory(
    query=query,
    system_answer=system_answer,
    user_correction=user_correction
)

print(f"""
修正结果:
- 找到错误节点: {result['error_node_id']}
- 更新节点数: {result['nodes_updated']}
- 修正时间: {result['correction_time']}
""")
```

---

## 🔧 配置选项

### MemoryManager参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `memory_tree` | HigherLevelSummary | 必需 | H-EMV记忆树 |
| `enable_auto_schedule` | bool | True | 启用自动调度 |
| `forgetting_interval_hours` | float | 1.0 | 遗忘间隔（小时） |
| `consolidation_time` | str | "02:00" | 整合时间（HH:MM） |
| `utility_weights` | tuple | (0.5, 0.3, 0.2) | 效用函数权重(α,β,γ) |
| `forgetting_threshold_low` | float | 0.2 | 低效用阈值 |
| `forgetting_threshold_med` | float | 0.5 | 中效用阈值 |
| `similarity_threshold` | float | 0.85 | 整合相似度阈值 |
| `storage_path` | str | None | 自动保存路径 |

### 示例：自定义配置

```python
manager = MemoryManager(
    memory_tree=your_tree,
    enable_auto_schedule=True,
    
    # 更激进的遗忘策略
    forgetting_interval_hours=0.5,  # 每30分钟
    utility_weights=(0.6, 0.2, 0.2),  # 更看重访问频率
    forgetting_threshold_low=0.3,  # 更高的删除阈值
    
    # 更宽松的整合条件
    similarity_threshold=0.80,  # 更容易整合
    
    # 自动保存
    storage_path="./backups/memory.pkl"
)
```

---

## 📊 监控与调试

### 查看运行日志

```python
# Active-H-EMV使用Loguru记录日志
from loguru import logger

# 设置日志级别
logger.add("active_hemv.log", level="DEBUG")

# 日志会自动记录：
# - Agent运行时间
# - 删除/整合/修正的节点
# - Token消耗
# - 错误和警告
```

### 查看实时统计

```python
# 实时查看统计信息
stats = manager.get_stats()

print(f"""
系统状态:
├─ 节点总数: {stats['total_nodes']}
├─ 存储大小: {stats['storage_size_mb']:.2f} MB
├─ 压缩率: {stats['compression_rate']:.1%}
│
├─ ForgettingAgent
│  ├─ 运行次数: {stats['forgetting_runs']}
│  ├─ 删除节点: {stats['forgotten_nodes']}
│  └─ 最后运行: {stats['last_forgetting_time']}
│
├─ ConsolidationAgent
│  ├─ 运行次数: {stats['consolidation_runs']}
│  ├─ 提取模式: {stats['patterns_extracted']}
│  └─ 最后运行: {stats['last_consolidation_time']}
│
└─ CorrectionAgent
   ├─ 修正次数: {stats['corrections']}
   └─ 平均更新节点: {stats['avg_nodes_updated']:.1f}
""")
```

### 可视化记忆树

```python
# 导出记忆树为JSON（可用于可视化）
manager.export_tree_json("memory_tree.json")

# 生成统计报告
manager.generate_report("report.html")
```

---

## 🐛 常见问题

### Q1: "No model configs loaded"错误

**原因**: 没有初始化AgentScope

**解决**:
```python
import agentscope

agentscope.init(model_configs=[{
    "model_type": "openai_chat",
    "config_name": "gpt-4o",
    "model_name": "gpt-4o",
    "api_key": "your-api-key"
}])
```

### Q2: ForgettingAgent运行很慢

**原因**: 计算语义显著性需要调用LLM

**解决**:
```python
# 1. 使用更快的模型
agentscope.init(model_configs=[{
    "model_type": "openai_chat",
    "config_name": "gpt-4o-mini",  # 更快更便宜
    "model_name": "gpt-4o-mini"
}])

# 2. 调整权重，减少语义计算
manager = MemoryManager(
    utility_weights=(0.7, 0.1, 0.2),  # 降低β（语义权重）
    ...
)
```

### Q3: 如何暂停自动调度？

```python
# 暂停
manager.pause_scheduling()

# 恢复
manager.resume_scheduling()

# 停止（无法恢复）
manager.stop_scheduling()
```

### Q4: 如何回滚到之前的状态？

```python
# 启用版本控制
manager = MemoryManager(
    memory_tree=your_tree,
    enable_versioning=True,  # 每次更新前保存版本
    max_versions=10  # 最多保留10个版本
)

# 查看历史版本
versions = manager.list_versions()
# [(1, '2024-12-01 10:00:00'), (2, '2024-12-01 11:00:00'), ...]

# 回滚到版本2
manager.rollback_to_version(2)
```

---

## 📚 进阶使用

### 自定义效用函数

```python
from active_hemv.memory import UtilityScorer

class MyUtilityScorer(UtilityScorer):
    def compute(self, node, current_time):
        # 你的自定义逻辑
        access = self.compute_access_heat(node, current_time)
        semantic = self.compute_semantic_significance(node)
        density = self.compute_information_density(node)
        
        # 自定义公式
        utility = 0.4 * access + 0.4 * semantic + 0.2 * density
        
        # 额外考虑：节点层级
        if node.level == "L0":
            utility *= 0.8  # L0节点更容易被遗忘
        
        return utility

# 使用自定义Scorer
manager = MemoryManager(
    memory_tree=your_tree,
    utility_scorer=MyUtilityScorer()
)
```

### 集成到机器人系统

```python
class RobotMemorySystem:
    def __init__(self):
        # 初始化H-EMV
        self.hemv = setup_llm_emv(...)
        
        # 初始化Active-H-EMV
        self.manager = MemoryManager(
            memory_tree=self.hemv.memory_tree,
            enable_auto_schedule=True
        )
    
    def on_new_experience(self, sensor_data):
        """机器人有新经验时调用"""
        # 使用H-EMV添加新记忆
        self.hemv.add_experience(sensor_data)
        
        # Active-H-EMV会自动管理
        # (遗忘/整合在后台运行)
    
    def on_user_query(self, query):
        """用户查询时调用"""
        # 使用H-EMV检索
        answer = self.hemv.query(query)
        return answer
    
    def on_user_correction(self, query, answer, correction):
        """用户纠错时调用"""
        # 使用CorrectionAgent修正
        result = self.manager.correct_memory(
            query, answer, correction
        )
        return result
```

---

## 🎯 下一步

### 建议学习路径

1. ✅ **快速开始** (本文档)
   - 运行示例
   - 了解基本用法

2. 📖 **阅读架构设计**
   - `docs/ARCHITECTURE_DESIGN.md`
   - 理解系统设计思想

3. 💻 **查看代码示例**
   - `examples/simple_usage.py`
   - `examples/README.md`

4. 🔬 **运行实验**
   - `experiments/run_teach_evaluation.py`
   - 在TEACh数据集上评估

5. 🎓 **撰写论文**
   - `docs/THESIS_GUIDE.md`
   - 论文写作指导

---

## 📮 获取帮助

遇到问题？
- 查看 [常见问题](#常见问题)
- 阅读 [文档](../README.md)
- 提交 [Issue](https://github.com/your-repo/issues)

---

## ✅ 检查清单

安装后检查：
- [ ] Python版本 >= 3.10
- [ ] 所有依赖安装成功
- [ ] API Key配置正确
- [ ] 示例运行成功
- [ ] 日志正常输出

---

**🎉 恭喜！你已经成功启动Active-H-EMV！**

**下一步**: 阅读 `docs/ARCHITECTURE_DESIGN.md` 了解系统设计

