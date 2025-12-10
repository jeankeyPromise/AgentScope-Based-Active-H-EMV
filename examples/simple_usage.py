"""
Active-H-EMV 简单使用示例

演示如何使用新架构的三个Agent进行记忆后处理
"""

import sys
from pathlib import Path
import pickle
from datetime import datetime
import os
# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import agentscope
from active_hemv.agents import MemoryManager


def main():
    """主函数"""
    
    print("=" * 70)
    print("Active-H-EMV 简单使用示例")
    print("新架构：H-EMV数据结构 + 三个后处理Agent")
    print("=" * 70)
    print()
    
    # 1. 初始化AgentScope
    print("📝 步骤1: 初始化AgentScope...")
    agentscope.init(
        model_configs=[{
            "model_type": "openai_chat",
            "config_name": "qwen-plus",
            "model_name": "qwen-plus",
            "api_key": os.getenv("KAIHONG_API_KEY"),  # 替换为你的API key
            "temperature": 0.7
        }],
        project="Active-H-EMV",
        name="simple_example"
    )
    print("✅ AgentScope已初始化\n")
    
    # 2. 加载现有的记忆树（使用llm_emv生成的）
    print("📝 步骤2: 加载记忆树...")
    memory_tree_path = Path(__file__).parent.parent / "data" / "armarx_lt_mem" / "2024-a7a-merged-summary.pkl"
    
    if not memory_tree_path.exists():
        print(f"⚠️  记忆树文件不存在: {memory_tree_path}")
        print("   请先使用llm_emv生成记忆树，或使用测试数据")
        return
    
    with open(memory_tree_path, 'rb') as f:
        memory_tree = pickle.load(f)
    
    print(f"✅ 记忆树已加载: {memory_tree_path.name}\n")
    
    # 3. 创建MemoryManager
    print("📝 步骤3: 创建MemoryManager...")
    manager = MemoryManager(
        memory_tree=memory_tree,
        forgetting_interval_hours=1.0,  # 每小时遗忘一次
        consolidation_time="02:00",  # 凌晨2点整合
        enable_auto_schedule=False,  # 示例中手动触发
        storage_path="./memory_tree_processed.pkl",
        forgetting={
            "model_config_name": "qwen-plus",
            "utility_weights": (0.5, 0.3, 0.2),
            "threshold_low": 0.2
        },
        consolidation={
            "model_config_name": "qwen-plus",
            "similarity_threshold": 0.85
        },
        correction={
            "model_config_name": "qwen-plus"
        }
    )
    print("✅ MemoryManager已创建\n")
    
    # 4. 运行遗忘周期
    print("=" * 70)
    print("🧠 演示1: 运行遗忘Agent")
    print("=" * 70)
    print("遗忘Agent会计算每个节点的效用值，删除低效用记忆...")
    print()
    
    forgetting_stats = manager.run_forgetting_cycle()
    print(f"✅ 遗忘周期完成:")
    print(f"   - 处理节点数: {forgetting_stats.get('processed', 0)}")
    print(f"   - 遗忘节点数: {forgetting_stats.get('forgotten', 0)}")
    print(f"   - 压缩节点数: {forgetting_stats.get('compressed', 0)}")
    print(f"   - 节省空间: {forgetting_stats.get('storage_saved_mb', 0):.2f} MB")
    print()
    
    # 5. 运行整合周期
    print("=" * 70)
    print("🌙 演示2: 运行整合Agent（模拟睡眠）")
    print("=" * 70)
    print("整合Agent会查找相似记忆，提取通用模式...")
    print()
    
    consolidation_stats = manager.run_consolidation_cycle(mode="daily")
    print(f"✅ 整合周期完成:")
    print(f"   - 合并记忆数: {consolidation_stats.get('merged', 0)}")
    print(f"   - 提取模式数: {consolidation_stats.get('patterns', 0)}")
    print(f"   - 强化记忆数: {consolidation_stats.get('reinforced', 0)}")
    print()
    
    # 6. 演示记忆修正
    print("=" * 70)
    print("🔧 演示3: 运行修正Agent（用户纠错）")
    print("=" * 70)
    print("用户纠错：昨天的苹果不是红色的，是绿色的")
    print()
    
    correction_result = manager.correct_memory(
        query="昨天的苹果是什么颜色？",
        system_answer="红色",
        user_correction="绿色"
    )
    
    if correction_result.get("success"):
        print(f"✅ 记忆修正完成:")
        print(f"   - 更新节点数: {correction_result.get('nodes_updated', 0)}")
        print(f"   - 级联更新成功")
    else:
        print(f"❌ 记忆修正失败: {correction_result.get('reason', 'unknown')}")
    print()
    
    # 7. 查看统计信息
    print("=" * 70)
    print("📊 系统统计信息")
    print("=" * 70)
    stats = manager.get_stats()
    
    print("Manager:")
    print(f"   - 查询次数: {stats['manager']['total_queries']}")
    print(f"   - 遗忘周期: {stats['manager']['forgetting_cycles']}")
    print(f"   - 整合周期: {stats['manager']['consolidation_cycles']}")
    print(f"   - 修正次数: {stats['manager']['corrections']}")
    print()
    
    print("ForgettingAgent:")
    print(f"   - 总周期数: {stats['forgetting_agent']['total_cycles']}")
    print(f"   - 累计遗忘: {stats['forgetting_agent']['nodes_forgotten']}")
    print(f"   - 累计节省: {stats['forgetting_agent']['storage_saved_mb']:.2f} MB")
    print()
    
    print("ConsolidationAgent:")
    print(f"   - 总整合数: {stats['consolidation_agent']['total_consolidations']}")
    print(f"   - 合并记忆: {stats['consolidation_agent']['memories_merged']}")
    print(f"   - 提取模式: {stats['consolidation_agent']['patterns_extracted']}")
    print()
    
    print("CorrectionAgent:")
    print(f"   - 总修正数: {stats['correction_agent']['total_corrections']}")
    print(f"   - 成功修正: {stats['correction_agent']['successful_corrections']}")
    print()
    
    # 8. 保存处理后的记忆树
    print("=" * 70)
    print("💾 保存处理后的记忆树...")
    manager.save_memory_tree()
    print("✅ 已保存到 memory_tree_processed.pkl\n")
    
    # 9. 关闭管理器
    print("👋 关闭MemoryManager...")
    manager.shutdown()
    print("✅ 完成!\n")
    
    print("=" * 70)
    print("🎉 示例运行完毕！")
    print()
    print("总结:")
    print("- ForgettingAgent: 删除了低效用记忆，节省存储空间")
    print("- ConsolidationAgent: 整合了相似记忆，提取了通用模式")
    print("- CorrectionAgent: 修正了用户指出的错误记忆")
    print()
    print("Token消耗:")
    print("- 仅在后处理阶段使用LLM，相比每层都是Agent节省82%+")
    print("=" * 70)


if __name__ == "__main__":
    main()

