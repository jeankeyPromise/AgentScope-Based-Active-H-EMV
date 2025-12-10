# Active-H-EMV 文档索引

## 📚 文档导航

### 🚀 快速入门

| 文档 | 描述 | 适合人群 |
|-----|------|---------|
| [README.md](../README.md) | 项目概览和快速开始 | 所有人 ⭐ |
| [QUICK_START.md](./QUICK_START.md) | 详细安装和配置指南 | 新用户 |
| [examples/README.md](../examples/README.md) | 代码示例说明 | 开发者 |

### 🏗️ 系统设计

| 文档 | 描述 | 适合人群 |
|-----|------|---------|
| [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) | 完整的架构设计文档 | 研究者、开发者 ⭐ |
| [WHY_USE_AGENT_FRAMEWORK.md](./WHY_USE_AGENT_FRAMEWORK.md) | 为什么使用Agent框架 | 答辩准备 |
| [CORRECTION_STRATEGY_ANALYSIS.md](./CORRECTION_STRATEGY_ANALYSIS.md) | 修正策略详细分析 | 深入研究 |

### 🎓 论文写作

| 文档 | 描述 | 适合人群 |
|-----|------|---------|
| [THESIS_GUIDE.md](./THESIS_GUIDE.md) | 完整的论文写作指南 | 毕设学生 ⭐⭐⭐ |
| [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) | 项目总结和创新点 | 论文撰写、答辩 |

---

## 🎯 按需求查找

### 我想要...

#### 快速运行系统
→ [QUICK_START.md](./QUICK_START.md)  
→ [examples/simple_usage.py](../examples/simple_usage.py)

#### 了解系统设计
→ [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md)  
→ [README.md](../README.md) 的架构部分

#### 撰写毕业论文
→ [THESIS_GUIDE.md](./THESIS_GUIDE.md) ⭐⭐⭐  
→ [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)

#### 准备答辩
→ [THESIS_GUIDE.md](./THESIS_GUIDE.md) 的答辩部分  
→ [WHY_USE_AGENT_FRAMEWORK.md](./WHY_USE_AGENT_FRAMEWORK.md)  
→ [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)

#### 深入研究某个Agent
→ [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) 第3节  
→ [CORRECTION_STRATEGY_ANALYSIS.md](./CORRECTION_STRATEGY_ANALYSIS.md) (修正Agent)

#### 理解与H-EMV的关系
→ [README.md](../README.md) 的"相比原始H-EMV的改进"部分  
→ [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) 第2节

---

## 📖 文档详细说明

### [README.md](../README.md)
**主项目说明文档**

重点内容：
- 项目简介和核心创新
- 与原始H-EMV的对比
- 三个Agent的功能说明
- 快速开始代码
- 学术声明

适合：首次了解项目的人

---

### [QUICK_START.md](./QUICK_START.md)
**5分钟快速开始指南**

重点内容：
- 详细的安装步骤
- 配置说明
- 基础使用示例
- 常见问题解决
- 监控和调试

适合：需要实际运行代码的人

---

### [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md)
**完整的系统架构设计**

重点内容：
- 原H-EMV vs Active-H-EMV对比
- 三个Agent的详细设计
  - 数学公式和算法
  - 伪代码
  - 复杂度分析
- 系统集成和数据流
- 关键设计决策

适合：需要理解技术细节的研究者和开发者

---

### [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)
**项目总结文档**

重点内容：
- 核心创新总结
- 与原H-EMV的关系
- 实现细节和代码统计
- 学术贡献
- 论文撰写要点
- 答辩问题准备

适合：撰写论文和准备答辩

---

### [THESIS_GUIDE.md](./THESIS_GUIDE.md)
**毕业论文写作完整指南** ⭐⭐⭐

重点内容：
- 完整的论文结构（1-6章）
- 每章的详细内容建议
- 摘要、引言、相关工作、方法、实验、结论
- 必需的图表清单
- 答辩PPT建议
- 答辩问题及回答技巧
- 检查清单

适合：正在撰写毕业论文的学生

---

### [WHY_USE_AGENT_FRAMEWORK.md](./WHY_USE_AGENT_FRAMEWORK.md)
**为什么使用Agent框架**

重点内容：
- Agent框架 vs 普通Python类
- 6大核心价值
  - LLM集成
  - 统一接口
  - 并发执行
  - 分布式部署
  - 日志监控
  - 人机交互
- 具体场景对比
- 答辩回答建议

适合：需要理解架构选型的人，准备答辩

---

### [CORRECTION_STRATEGY_ANALYSIS.md](./CORRECTION_STRATEGY_ANALYSIS.md)
**修正Agent策略详细分析**

重点内容：
- 直接采用用户纠正 vs VLM重新验证
- 混合策略设计（置信度驱动）
- 代码实现细节
- 优缺点对比

适合：对修正机制感兴趣的研究者

---

### [examples/README.md](../examples/README.md)
**代码示例说明**

重点内容：
- 示例文件列表
- 运行方法
- 预期输出
- 使用场景
- 配置选项
- 故障排查

适合：需要运行代码的开发者

---

## 🔍 按主题查找

### 主题1: 与H-EMV的关系

相关文档：
1. [README.md](../README.md) - "相比原始H-EMV的改进"
2. [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) - 第2节对比
3. [THESIS_GUIDE.md](./THESIS_GUIDE.md) - 第2.1节相关工作

关键论点：
- Active-H-EMV是H-EMV的**扩展和优化**，而非替代
- 保留了H-EMV的优秀数据结构
- 添加了主动管理能力（遗忘、整合、修正）
- 解决了H-EMV的三大问题（存储爆炸、冗余、错误累积）

---

### 主题2: 三个Agent的必要性

相关文档：
1. [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) - 第3节
2. [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) - 核心创新部分
3. [examples/README.md](../examples/README.md) - 三个Agent的作用

关键论点：
- **ForgettingAgent**: 解决存储爆炸，基于Ebbinghaus遗忘曲线
- **ConsolidationAgent**: 解决冗余和泛化，基于睡眠记忆巩固理论
- **CorrectionAgent**: 解决错误累积，基于认知修正理论
- 每个Agent都有明确的理论依据和实际价值

---

### 主题3: 为什么用Agent框架

相关文档：
1. [WHY_USE_AGENT_FRAMEWORK.md](./WHY_USE_AGENT_FRAMEWORK.md) ⭐⭐⭐
2. [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) - 第3.5节

关键论点：
- LLM集成：自动处理API调用、重试、成本跟踪
- 统一接口：标准Msg格式，易于扩展
- 分布式支持：未来可轻松扩展
- 学术意义：使用主流多智能体框架

---

### 主题4: 效用函数设计

相关文档：
1. [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) - 第3.2节
2. [THESIS_GUIDE.md](./THESIS_GUIDE.md) - 第3.2节方法

关键内容：
- 数学公式：`U(n,t) = α·A(n,t) + β·S(n) + γ·I(n)`
- 三个维度：访问热度、语义显著性、信息密度
- 参数设置：α=0.5, β=0.3, γ=0.2
- 三级遗忘策略

---

### 主题5: 论文撰写

相关文档：
1. [THESIS_GUIDE.md](./THESIS_GUIDE.md) ⭐⭐⭐
2. [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)

包含内容：
- 完整的6章结构
- 每章的详细内容
- 必需的图表
- 答辩PPT
- 答辩问题及回答
- 引用建议

---

## ⚡ 快捷链接

### 最常用的3个文档

1. [README.md](../README.md) - 项目概览
2. [THESIS_GUIDE.md](./THESIS_GUIDE.md) - 论文写作
3. [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) - 技术细节

### 答辩准备必读

1. [THESIS_GUIDE.md](./THESIS_GUIDE.md) - 答辩部分
2. [WHY_USE_AGENT_FRAMEWORK.md](./WHY_USE_AGENT_FRAMEWORK.md)
3. [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)

### 代码相关

1. [QUICK_START.md](./QUICK_START.md)
2. [examples/README.md](../examples/README.md)
3. [examples/simple_usage.py](../examples/simple_usage.py)

---

## 📊 文档完成度

| 文档 | 状态 | 最后更新 |
|-----|------|---------|
| README.md | ✅ 完成 | 2024-12-04 |
| QUICK_START.md | ✅ 完成 | 2024-12-04 |
| ARCHITECTURE_DESIGN.md | ✅ 完成 | 2024-12-04 |
| PROJECT_SUMMARY.md | ✅ 完成 | 2024-12-04 |
| THESIS_GUIDE.md | ✅ 完成 | 2024-12-04 |
| WHY_USE_AGENT_FRAMEWORK.md | ✅ 完成 | 2024-12-04 |
| CORRECTION_STRATEGY_ANALYSIS.md | ✅ 完成 | 2024-12-03 |
| examples/README.md | ✅ 完成 | 2024-12-04 |

---

## 💬 获取帮助

找不到需要的信息？

1. 查看本索引找到相关文档
2. 阅读文档中的"常见问题"部分
3. 提交Issue到GitHub
4. 联系项目维护者

---

**📖 祝你顺利完成毕业设计！** 🎓🚀

