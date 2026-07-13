"""阶段5：AI效果评估框架。

评估AI助手的回答质量：
- 意图识别准确率
- 工具调用准确率
- 回答相关性评分
- 用户满意度（thumbs up/down）
- 黄金样本回归测试
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvaluationCase:
    """评估用例。"""
    id: str
    category: str  # L1/L2/L3/L4/L5
    input_text: str
    expected_intent: str = ''
    expected_tool: str = ''
    expected_output_contains: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category,
            'input_text': self.input_text,
            'expected_intent': self.expected_intent,
            'expected_tool': self.expected_tool,
            'expected_output_contains': self.expected_output_contains,
            'tags': self.tags,
        }


@dataclass
class EvaluationResult:
    """评估结果。"""
    case_id: str
    passed: bool
    actual_intent: str = ''
    actual_tool: str = ''
    actual_output: str = ''
    score: float = 0.0  # 0-1
    failure_reason: str = ''
    evaluated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'case_id': self.case_id,
            'passed': self.passed,
            'actual_intent': self.actual_intent,
            'actual_tool': self.actual_tool,
            'actual_output': self.actual_output[:200],
            'score': self.score,
            'failure_reason': self.failure_reason,
            'evaluated_at': self.evaluated_at.isoformat(),
        }


@dataclass
class EvaluationReport:
    """评估报告。"""
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    avg_score: float = 0.0
    category_scores: dict[str, dict] = field(default_factory=dict)
    results: list[EvaluationResult] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=datetime.now)

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return round(self.passed_cases / self.total_cases * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_cases': self.total_cases,
            'passed_cases': self.passed_cases,
            'failed_cases': self.failed_cases,
            'pass_rate': self.pass_rate,
            'avg_score': round(self.avg_score, 3),
            'category_scores': self.category_scores,
            'evaluated_at': self.evaluated_at.isoformat(),
            'failed_cases_detail': [
                r.to_dict() for r in self.results if not r.passed
            ][:10],
        }


class Evaluator:
    """AI效果评估器。"""

    def __init__(self):
        self._cases: list[EvaluationCase] = []
        self._feedback: list[dict] = []  # thumbs up/down

    def add_case(self, case: EvaluationCase) -> None:
        """添加评估用例。"""
        self._cases.append(case)

    def add_cases_from_file(self, filepath: str) -> int:
        """从JSON文件批量添加用例。"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for item in data:
                case = EvaluationCase(
                    id=item.get('id', f'case_{len(self._cases)+1}'),
                    category=item.get('category', 'L1'),
                    input_text=item.get('input_text', ''),
                    expected_intent=item.get('expected_intent', ''),
                    expected_tool=item.get('expected_tool', ''),
                    expected_output_contains=item.get('expected_output_contains', []),
                    tags=item.get('tags', []),
                )
                self._cases.append(case)
                count += 1

            return count
        except Exception as e:
            logger.error('Failed to load cases from %s: %s', filepath, e)
            return 0

    def record_feedback(
        self,
        run_id: str,
        user_id: int,
        thumbs: str,  # 'up' or 'down'
        comment: str = '',
    ) -> None:
        """记录用户反馈。"""
        self._feedback.append({
            'run_id': run_id,
            'user_id': user_id,
            'thumbs': thumbs,
            'comment': comment,
            'timestamp': datetime.now(),
        })

    def evaluate(
        self,
        intent_func: Any = None,
        tool_func: Any = None,
        chat_func: Any = None,
    ) -> EvaluationReport:
        """执行评估。

        Args:
            intent_func: 意图识别函数 (input_text) -> intent_dict
            tool_func: 工具选择函数 (intent_dict) -> tool_name
            chat_func: 对话函数 (input_text) -> response_text

        Returns:
            EvaluationReport
        """
        report = EvaluationReport(total_cases=len(self._cases))
        category_stats: dict[str, dict] = {}

        for case in self._cases:
            result = self._evaluate_case(case, intent_func, tool_func, chat_func)
            report.results.append(result)

            if result.passed:
                report.passed_cases += 1
            else:
                report.failed_cases += 1

            # 分类统计
            cat = case.category
            if cat not in category_stats:
                category_stats[cat] = {'total': 0, 'passed': 0, 'scores': []}
            category_stats[cat]['total'] += 1
            if result.passed:
                category_stats[cat]['passed'] += 1
            category_stats[cat]['scores'].append(result.score)

        # 计算平均分
        if report.results:
            report.avg_score = sum(r.score for r in report.results) / len(report.results)

        # 分类通过率
        for cat, stats in category_stats.items():
            stats['pass_rate'] = round(stats['passed'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
            stats['avg_score'] = round(sum(stats['scores']) / len(stats['scores']), 3) if stats['scores'] else 0
            del stats['scores']

        report.category_scores = category_stats
        report.evaluated_at = datetime.now()

        return report

    def _evaluate_case(
        self,
        case: EvaluationCase,
        intent_func: Any,
        tool_func: Any,
        chat_func: Any,
    ) -> EvaluationResult:
        """评估单个用例。"""
        result = EvaluationResult(case_id=case.id, passed=True, score=1.0)

        # 意图识别评估
        if intent_func and case.expected_intent:
            try:
                actual_intent = intent_func(case.input_text)
                result.actual_intent = str(actual_intent)
                if case.expected_intent not in str(actual_intent):
                    result.passed = False
                    result.score -= 0.3
                    result.failure_reason = f'Intent mismatch: expected {case.expected_intent}, got {actual_intent}'
            except Exception as e:
                result.passed = False
                result.score -= 0.3
                result.failure_reason = f'Intent function error: {str(e)[:100]}'

        # 工具调用评估
        if tool_func and case.expected_tool:
            try:
                actual_tool = tool_func(case.input_text)
                result.actual_tool = str(actual_tool)
                if case.expected_tool not in str(actual_tool):
                    result.passed = False
                    result.score -= 0.3
                    result.failure_reason += f' Tool mismatch: expected {case.expected_tool}, got {actual_tool}'
            except Exception as e:
                result.passed = False
                result.score -= 0.3
                result.failure_reason += f' Tool function error: {str(e)[:100]}'

        # 回答内容评估
        if chat_func and case.expected_output_contains:
            try:
                actual_output = chat_func(case.input_text)
                result.actual_output = str(actual_output)
                for expected in case.expected_output_contains:
                    if expected not in str(actual_output):
                        result.passed = False
                        result.score -= 0.2
                        result.failure_reason += f' Missing: {expected}'
            except Exception as e:
                result.passed = False
                result.score -= 0.2
                result.failure_reason += f' Chat function error: {str(e)[:100]}'

        result.score = max(0, result.score)
        return result

    def get_feedback_stats(self) -> dict[str, Any]:
        """获取反馈统计。"""
        total = len(self._feedback)
        thumbs_up = sum(1 for f in self._feedback if f['thumbs'] == 'up')
        thumbs_down = total - thumbs_up

        return {
            'total_feedback': total,
            'thumbs_up': thumbs_up,
            'thumbs_down': thumbs_down,
            'satisfaction_rate': round(thumbs_up / total * 100, 1) if total > 0 else 0,
            'recent_comments': [
                f['comment'] for f in self._feedback[-10:]
                if f['comment']
            ],
        }


# 全局评估器实例
_evaluator = Evaluator()


def get_evaluator() -> Evaluator:
    """获取全局评估器实例。"""
    return _evaluator
