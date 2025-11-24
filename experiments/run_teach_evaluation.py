"""
TEACh数据集评估 - Active-H-EMV系统完整评估

用法:
    python experiments/run_teach_evaluation.py \
        --method active_hemv \
        --dataset data/teach/test_set_100.pkl \
        --output results/active_hemv_teach.json
"""

import argparse
import json
import pickle
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from loguru import logger

# 导入Active-H-EMV组件
from active_hemv.agents import (
    PerceptionWorkerAgent,
    EventAggregatorAgent,
    MemoryOrchestratorAgent,
    MemoryGardenerAgent
)
from active_hemv.storage import ChromaVectorStore
from active_hemv.memory import UtilityScorer, ForgettingPolicy


class TEAChEvaluator:
    """TEACh数据集评估器"""
    
    def __init__(
        self,
        method: str = "active_hemv",
        enable_forgetting: bool = True,
        enable_editing: bool = True,
        output_path: str = "results/evaluation.json"
    ):
        """
        初始化评估器
        
        Args:
            method: 评估方法 (active_hemv/original_hemv/gemini_1pass)
            enable_forgetting: 是否启用遗忘机制
            enable_editing: 是否启用记忆编辑
            output_path: 结果输出路径
        """
        self.method = method
        self.enable_forgetting = enable_forgetting
        self.enable_editing = enable_editing
        self.output_path = Path(output_path)
        
        # 初始化系统组件
        if method == "active_hemv":
            self._init_active_hemv()
        elif method == "original_hemv":
            self._init_original_hemv()
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # 评估统计
        self.stats = {
            "total_questions": 0,
            "correct": 0,
            "correct_summarized": 0,
            "correct_tmi": 0,
            "partially_correct": 0,
            "incorrect": 0,
            "total_tokens": 0,
            "avg_latency_ms": 0
        }
        
        logger.info(f"TEAChEvaluator initialized with method={method}")
    
    def _init_active_hemv(self):
        """初始化Active-H-EMV系统"""
        # 存储
        self.vector_store = ChromaVectorStore(persist_directory="./eval_chroma_db")
        storage_backends = {"vector": self.vector_store}
        
        # Agents
        self.perception_agent = PerceptionWorkerAgent(
            name="PerceptionWorker",
            storage_backends=storage_backends
        )
        
        self.event_agent = EventAggregatorAgent(
            name="EventAggregator",
            storage_backends=storage_backends
        )
        
        self.orchestrator = MemoryOrchestratorAgent(
            name="Orchestrator",
            storage_backends=storage_backends,
            enable_parallel_search=True
        )
        
        if self.enable_forgetting:
            self.gardener = MemoryGardenerAgent(
                name="Gardener",
                storage_backends=storage_backends,
                schedule_enabled=False  # 手动触发,用于评估
            )
        
        logger.info("Active-H-EMV system initialized")
    
    def _init_original_hemv(self):
        """初始化原始H-EMV系统 (对比基线)"""
        # TODO: 集成现有的llm_emv代码
        pass
    
    def evaluate_dataset(self, dataset_path: str):
        """
        评估完整数据集
        
        Args:
            dataset_path: 数据集文件路径 (pickle格式)
        """
        logger.info(f"Loading dataset from {dataset_path}")
        
        with open(dataset_path, 'rb') as f:
            dataset = pickle.load(f)
        
        logger.info(f"Dataset loaded: {len(dataset)} episodes")
        
        results = []
        
        for i, episode in enumerate(dataset):
            logger.info(f"Evaluating episode {i+1}/{len(dataset)}")
            
            # 1. 构建记忆 (处理episode的所有帧)
            self._build_memory_from_episode(episode)
            
            # 2. 回答问题
            qa_results = self._answer_questions(episode['questions'])
            
            # 3. 统计结果
            for qa in qa_results:
                self._update_stats(qa)
            
            results.append({
                "episode_id": episode.get('id', f'ep_{i}'),
                "qa_results": qa_results,
                "tokens_used": sum(qa['tokens'] for qa in qa_results),
                "avg_latency": sum(qa['latency_ms'] for qa in qa_results) / len(qa_results)
            })
            
            # 4. 定期触发遗忘 (每10个episode)
            if self.enable_forgetting and (i + 1) % 10 == 0:
                logger.info("Triggering forgetting cycle")
                self.gardener.forgetting_cycle()
        
        # 保存结果
        self._save_results(results)
        
        logger.info("Evaluation completed")
        logger.info(f"Results saved to {self.output_path}")
        self._print_summary()
    
    def _build_memory_from_episode(self, episode: Dict):
        """从episode构建记忆"""
        # TODO: 实现episode数据到Active-H-EMV的转换
        # 需要处理episode中的:
        # - frames (图像序列)
        # - actions (动作序列)
        # - dialogue (对话)
        pass
    
    def _answer_questions(self, questions: List[Dict]) -> List[Dict]:
        """回答问题列表"""
        results = []
        
        for question in questions:
            start_time = datetime.now()
            
            # 使用Orchestrator回答
            from agentscope.message import Msg
            
            query_msg = Msg(
                name="Evaluator",
                content={
                    "type": "user_query",
                    "query": question['question']
                },
                role="user"
            )
            
            answer_msg = self.orchestrator(query_msg)
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            # 评估答案
            category = self._evaluate_answer(
                question['question'],
                answer_msg.content.get('answer', ''),
                question.get('ground_truth', '')
            )
            
            results.append({
                "question": question['question'],
                "answer": answer_msg.content.get('answer', ''),
                "ground_truth": question.get('ground_truth', ''),
                "category": category,
                "tokens": answer_msg.content.get('tokens_used', 0),
                "latency_ms": latency
            })
        
        return results
    
    def _evaluate_answer(self, question: str, answer: str, ground_truth: str) -> str:
        """
        评估答案质量 (使用GPT-4o作为评判器)
        
        Returns:
            str: "correct" | "correct_summarized" | "correct_tmi" | 
                 "partially_correct" | "incorrect"
        """
        # TODO: 调用GPT-4o进行语义分类
        # 参考H-EMV论文的评估方法
        
        # 占位符: 简单字符串匹配
        if ground_truth.lower() in answer.lower():
            return "correct"
        else:
            return "incorrect"
    
    def _update_stats(self, qa_result: Dict):
        """更新统计信息"""
        self.stats['total_questions'] += 1
        self.stats['total_tokens'] += qa_result['tokens']
        self.stats['avg_latency_ms'] += qa_result['latency_ms']
        
        category = qa_result['category']
        self.stats[category] += 1
    
    def _save_results(self, results: List[Dict]):
        """保存评估结果"""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        output = {
            "method": self.method,
            "enable_forgetting": self.enable_forgetting,
            "enable_editing": self.enable_editing,
            "timestamp": datetime.now().isoformat(),
            "stats": self.stats,
            "results": results
        }
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    
    def _print_summary(self):
        """打印评估摘要"""
        total = self.stats['total_questions']
        
        print("\n" + "="*60)
        print("Evaluation Summary")
        print("="*60)
        print(f"Method: {self.method}")
        print(f"Total Questions: {total}")
        print(f"\nSemantic Categorization:")
        print(f"  Correct:            {self.stats['correct']:3d} ({self.stats['correct']/total*100:.1f}%)")
        print(f"  Correct Summarized: {self.stats['correct_summarized']:3d} ({self.stats['correct_summarized']/total*100:.1f}%)")
        print(f"  Correct TMI:        {self.stats['correct_tmi']:3d} ({self.stats['correct_tmi']/total*100:.1f}%)")
        print(f"  Partially Correct:  {self.stats['partially_correct']:3d} ({self.stats['partially_correct']/total*100:.1f}%)")
        print(f"  Incorrect:          {self.stats['incorrect']:3d} ({self.stats['incorrect']/total*100:.1f}%)")
        print(f"\nPerformance:")
        print(f"  Total Tokens: {self.stats['total_tokens']:,}")
        print(f"  Avg Latency:  {self.stats['avg_latency_ms']/total:.1f} ms")
        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="TEACh Dataset Evaluation")
    parser.add_argument("--method", type=str, default="active_hemv",
                        choices=["active_hemv", "original_hemv", "gemini_1pass"],
                        help="Evaluation method")
    parser.add_argument("--dataset", type=str, required=True,
                        help="Path to TEACh dataset (pickle file)")
    parser.add_argument("--output", type=str, default="results/evaluation.json",
                        help="Output results path")
    parser.add_argument("--no-forgetting", action="store_true",
                        help="Disable forgetting mechanism")
    parser.add_argument("--no-editing", action="store_true",
                        help="Disable memory editing")
    
    args = parser.parse_args()
    
    evaluator = TEAChEvaluator(
        method=args.method,
        enable_forgetting=not args.no_forgetting,
        enable_editing=not args.no_editing,
        output_path=args.output
    )
    
    evaluator.evaluate_dataset(args.dataset)


if __name__ == "__main__":
    main()

