# Active-H-EMV 评估实验

## 目录结构

```
experiments/
├── run_teach_evaluation.py      # TEACh数据集完整评估
├── forgetting_ablation/          # 遗忘机制消融实验
│   └── run_ablation.py
├── editing_validation/           # 编辑准确性验证
│   └── simulate_corrections.py
└── metrics/                      # 指标计算
    ├── calculate_token_efficiency.py
    ├── calculate_storage_compression.py
    └── calculate_recall_after_forgetting.py
```

## 快速开始

### 1. TEACh数据集评估

```bash
python experiments/run_teach_evaluation.py \
    --method active_hemv \
    --dataset data/teach/test_set_100.pkl \
    --output results/active_hemv_teach.json
```

### 2. 消融实验

```bash
python experiments/forgetting_ablation/run_ablation.py \
    --alpha_range 0.0,0.5,1.0 \
    --beta_range 0.0,0.3,0.5 \
    --gamma_range 0.0,0.2,0.5
```

### 3. 指标计算

```bash
# Token效率
python experiments/metrics/calculate_token_efficiency.py \
    --baseline_results results/gemini_baseline.json \
    --ours_results results/active_hemv.json

# 存储压缩比
python experiments/metrics/calculate_storage_compression.py \
    --data_dir ./milvus_data

# 遗忘后召回率
python experiments/metrics/calculate_recall_after_forgetting.py \
    --before_results results/before_forgetting.json \
    --after_results results/after_forgetting.json
```

## 评估指标说明

### 1. 语义正确性 (Semantic Categorization)

沿用H-EMV论文的分类标准:
- **Correct**: 语义完全正确
- **Correct Summarized**: 核心正确但丢失细节
- **Correct TMI**: 正确但信息过载
- **Partially Correct**: 部分正确
- **Incorrect**: 完全错误

评估器: GPT-4o

### 2. Token效率

```
Token_Efficiency = (Active-H-EMV查询Token数) / (Gemini 1-pass Token数)
```

目标: < 0.15 (节省85%+)

### 3. 存储压缩比

```
Storage_Compression = (遗忘后存储空间GB) / (未遗忘存储空间GB)
```

目标: < 0.4 (压缩60%+)

### 4. 遗忘后召回率

```
Recall@Forgetting = (遗忘后正确回答数) / (遗忘前正确回答数)
```

目标: > 0.85

### 5. 编辑准确率

```
Edit_Accuracy = (编辑后正确节点数) / (编辑触发次数)
```

目标: > 0.90

### 6. 并行搜索加速比

```
Speedup = (串行搜索平均延迟s) / (并行搜索平均延迟s)
```

目标: > 2.5x

## 论文数据表格模板

### Table 1: 对比实验 - 语义正确性

| Method | Correct | Correct Summ. | Correct TMI | Partially | Incorrect | Avg Token |
|--------|---------|---------------|-------------|-----------|-----------|-----------|
| Gemini 1-pass | - | - | - | - | - | ~50000 |
| H-EMV (Original) | - | - | - | - | - | ~5000 |
| **Active-H-EMV (Ours)** | - | - | - | - | - | **~4000** |

### Table 2: 消融实验 - 效用函数权重

| Config (α, β, γ) | Recall@Forget | Storage Compress | 说明 |
|------------------|---------------|------------------|------|
| (1.0, 0.0, 0.0) | - | - | 仅访问热度 |
| (0.0, 1.0, 0.0) | - | - | 仅语义显著性 |
| (0.0, 0.0, 1.0) | - | - | 仅信息密度 |
| **(0.5, 0.3, 0.2)** | **-** | **-** | **完整 (Ours)** |

### Figure 1: 30天存储增长曲线

```
存储空间(GB)
│
│     ┌────────────────── 无遗忘 (线性增长)
│    ╱
│   ╱
│  ╱
│ ╱        ─────────────── Active-H-EMV (稳定)
│╱
└─────────────────────────────→ 时间(天)
 0   5   10  15  20  25  30
```

## 完整评估流程

```bash
# 1. 运行基线方法
python experiments/run_baseline.py --method gemini_1pass
python experiments/run_baseline.py --method original_hemv

# 2. 运行Active-H-EMV
python experiments/run_teach_evaluation.py --method active_hemv

# 3. 运行消融实验
./experiments/forgetting_ablation/run_all_configs.sh

# 4. 生成所有表格和图表
python experiments/generate_paper_tables.py
python experiments/generate_paper_figures.py
```

## 注意事项

1. **数据集准备**: 确保 `data/teach/test_set_100.pkl` 已下载
2. **LLM API**: 配置 OpenAI API Key (用于语义分类评估)
3. **计算资源**: 完整评估约需要8-12小时 (GPU推荐)
4. **随机种子**: 所有实验固定 `random_seed=42` 保证可复现性

