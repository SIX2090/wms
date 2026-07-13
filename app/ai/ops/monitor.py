"""阶段5：AI运维监控看板模块。

提供：
- 实时健康检查（LLM连通性/数据库/队列）
- 运行指标统计（请求数/成功率/平均耗时/错误分布）
- 熔断器状态监控
- 告警规则配置
- 趋势数据（按小时/天聚合）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """健康状态。"""
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


@dataclass
class HealthCheck:
    """单项健康检查。"""
    name: str
    status: HealthStatus
    message: str = ''
    latency_ms: float = 0.0
    checked_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'latency_ms': round(self.latency_ms, 1),
            'checked_at': self.checked_at.isoformat(),
        }


@dataclass
class AIMetrics:
    """AI运行指标。"""
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    fallback_count: int = 0  # 降级到本地规则的次数
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_distribution: dict[str, int] = field(default_factory=dict)
    tool_usage: dict[str, int] = field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.success_count / self.total_requests * 100, 1)

    @property
    def fallback_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.fallback_count / self.total_requests * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_requests': self.total_requests,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'fallback_count': self.fallback_count,
            'success_rate': self.success_rate,
            'fallback_rate': self.fallback_rate,
            'avg_latency_ms': round(self.avg_latency_ms, 1),
            'p95_latency_ms': round(self.p95_latency_ms, 1),
            'p99_latency_ms': round(self.p99_latency_ms, 1),
            'error_distribution': self.error_distribution,
            'tool_usage': self.tool_usage,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
        }


@dataclass
class AlertRule:
    """告警规则。"""
    name: str
    metric: str  # success_rate / fallback_rate / avg_latency_ms / breaker_state
    operator: str  # lt / gt / eq
    threshold: float
    severity: str = 'warning'  # warning / critical
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0

    def evaluate(self, value: float) -> bool:
        """评估是否触发告警。"""
        if not self.enabled:
            return False

        triggered = False
        if self.operator == 'lt' and value < self.threshold:
            triggered = True
        elif self.operator == 'gt' and value > self.threshold:
            triggered = True
        elif self.operator == 'eq' and value == self.threshold:
            triggered = True

        if triggered:
            self.last_triggered = datetime.now()
            self.trigger_count += 1

        return triggered

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'metric': self.metric,
            'operator': self.operator,
            'threshold': self.threshold,
            'severity': self.severity,
            'enabled': self.enabled,
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'trigger_count': self.trigger_count,
        }


class OpsMonitor:
    """AI运维监控器。"""

    def __init__(self):
        self._alert_rules: list[AlertRule] = []
        self._latency_history: list[float] = []
        self._request_history: list[dict] = []

    def add_alert_rule(self, rule: AlertRule) -> None:
        """添加告警规则。"""
        self._alert_rules.append(rule)

    def remove_alert_rule(self, name: str) -> bool:
        """移除告警规则。"""
        before = len(self._alert_rules)
        self._alert_rules = [r for r in self._alert_rules if r.name != name]
        return len(self._alert_rules) < before

    def record_request(
        self,
        success: bool,
        latency_ms: float,
        tool_name: str = '',
        error_type: str = '',
        fallback: bool = False,
    ) -> None:
        """记录请求。"""
        self._latency_history.append(latency_ms)
        self._request_history.append({
            'success': success,
            'latency_ms': latency_ms,
            'tool_name': tool_name,
            'error_type': error_type,
            'fallback': fallback,
            'timestamp': datetime.now(),
        })

        # 保留最近10000条
        if len(self._latency_history) > 10000:
            self._latency_history = self._latency_history[-10000:]
        if len(self._request_history) > 10000:
            self._request_history = self._request_history[-10000:]

    def check_health(
        self,
        llm_configured: bool = False,
        llm_reachable: bool = False,
        db_healthy: bool = True,
    ) -> list[HealthCheck]:
        """执行健康检查。"""
        checks = []

        # LLM配置检查
        if llm_configured:
            if llm_reachable:
                checks.append(HealthCheck('llm', HealthStatus.HEALTHY, 'LLM已配置且可达'))
            else:
                checks.append(HealthCheck('llm', HealthStatus.DEGRADED, 'LLM已配置但不可达'))
        else:
            checks.append(HealthCheck('llm', HealthStatus.DEGRADED, 'LLM未配置（使用本地规则）'))

        # 数据库检查
        if db_healthy:
            checks.append(HealthCheck('database', HealthStatus.HEALTHY, '数据库正常'))
        else:
            checks.append(HealthCheck('database', HealthStatus.UNHEALTHY, '数据库异常'))

        return checks

    def get_metrics(self, hours: int = 24) -> AIMetrics:
        """获取运行指标。"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [r for r in self._request_history if r['timestamp'] >= cutoff]

        if not recent:
            return AIMetrics(
                period_start=cutoff,
                period_end=datetime.now(),
            )

        total = len(recent)
        success = sum(1 for r in recent if r['success'])
        failure = total - success
        fallback = sum(1 for r in recent if r['fallback'])

        latencies = sorted(r['latency_ms'] for r in recent)
        avg_latency = sum(latencies) / len(latencies)
        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)

        # 错误分布
        error_dist: dict[str, int] = {}
        for r in recent:
            if r['error_type']:
                error_dist[r['error_type']] = error_dist.get(r['error_type'], 0) + 1

        # 工具使用分布
        tool_usage: dict[str, int] = {}
        for r in recent:
            if r['tool_name']:
                tool_usage[r['tool_name']] = tool_usage.get(r['tool_name'], 0) + 1

        return AIMetrics(
            total_requests=total,
            success_count=success,
            failure_count=failure,
            fallback_count=fallback,
            avg_latency_ms=avg_latency,
            p95_latency_ms=latencies[p95_idx] if p95_idx < len(latencies) else avg_latency,
            p99_latency_ms=latencies[p99_idx] if p99_idx < len(latencies) else avg_latency,
            error_distribution=error_dist,
            tool_usage=tool_usage,
            period_start=cutoff,
            period_end=datetime.now(),
        )

    def evaluate_alerts(self, metrics: AIMetrics) -> list[dict[str, Any]]:
        """评估告警规则。"""
        triggered = []
        metric_values = {
            'success_rate': metrics.success_rate,
            'fallback_rate': metrics.fallback_rate,
            'avg_latency_ms': metrics.avg_latency_ms,
        }

        for rule in self._alert_rules:
            if rule.metric in metric_values:
                if rule.evaluate(metric_values[rule.metric]):
                    triggered.append(rule.to_dict())

        return triggered

    def get_trend_data(self, hours: int = 24, granularity: str = 'hour') -> list[dict[str, Any]]:
        """获取趋势数据。"""
        if granularity == 'hour':
            buckets = hours
            bucket_seconds = 3600
        else:
            buckets = hours // 24
            bucket_seconds = 86400

        now = datetime.now()
        trend = []

        for i in range(buckets - 1, -1, -1):
            bucket_start = now - timedelta(seconds=bucket_seconds * (i + 1))
            bucket_end = now - timedelta(seconds=bucket_seconds * i)

            bucket_requests = [
                r for r in self._request_history
                if bucket_start <= r['timestamp'] < bucket_end
            ]

            if bucket_requests:
                success = sum(1 for r in bucket_requests if r['success'])
                avg_lat = sum(r['latency_ms'] for r in bucket_requests) / len(bucket_requests)
            else:
                success = 0
                avg_lat = 0

            trend.append({
                'time': bucket_start.strftime('%H:%M') if granularity == 'hour' else bucket_start.strftime('%m-%d'),
                'requests': len(bucket_requests),
                'success': success,
                'failure': len(bucket_requests) - success,
                'avg_latency_ms': round(avg_lat, 1),
            })

        return trend


# 全局监控实例
_ops_monitor = OpsMonitor()

# 注册默认告警规则
_ops_monitor.add_alert_rule(AlertRule(
    name='success_rate_low',
    metric='success_rate',
    operator='lt',
    threshold=90.0,
    severity='critical',
))
_ops_monitor.add_alert_rule(AlertRule(
    name='fallback_rate_high',
    metric='fallback_rate',
    operator='gt',
    threshold=30.0,
    severity='warning',
))
_ops_monitor.add_alert_rule(AlertRule(
    name='latency_high',
    metric='avg_latency_ms',
    operator='gt',
    threshold=5000.0,
    severity='warning',
))


def get_ops_monitor() -> OpsMonitor:
    """获取全局监控实例。"""
    return _ops_monitor
