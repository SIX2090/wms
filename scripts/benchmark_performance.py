#!/usr/bin/env python3
"""WMS AI助手性能基准测试脚本"""

import os
import sys
from pathlib import Path

# 设置正确的导入路径
ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
sys.path.insert(0, str(APP_DIR))

import time
import statistics
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def benchmark_tool_registry():
    """测试工具注册表性能"""
    print("\n=== 工具注册表性能测试 ===")
    
    from ai.tools.registry import list_ai_tool_specs, get_ai_tool_spec
    
    times = []
    for _ in range(100):
        start = time.time()
        tools = list_ai_tool_specs()
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
    
    avg_time = statistics.mean(times)
    p95_time = statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
    print(f"  工具列表查询: 平均 {avg_time:.4f}ms, P95 {p95_time:.4f}ms")
    print(f"  注册工具数量: {len(tools)}")
    
    # Test individual tool lookup
    times2 = []
    for _ in range(100):
        start = time.time()
        spec = get_ai_tool_spec('in_order_draft')
        elapsed = (time.time() - start) * 1000
        times2.append(elapsed)
    
    avg_time2 = statistics.mean(times2)
    p95_time2 = statistics.quantiles(times2, n=20)[18] if len(times2) >= 20 else max(times2)
    print(f"  单工具查询: 平均 {avg_time2:.4f}ms, P95 {p95_time2:.4f}ms")
    
    return {"avg_ms": avg_time, "p95_ms": p95_time, "tool_count": len(tools)}

def benchmark_policy_engine():
    """测试策略引擎性能"""
    print("\n=== 策略引擎性能测试 ===")

    from ai.tools.registry import list_ai_tools_for_role

    times = []
    for _ in range(100):
        start = time.time()
        tools = list_ai_tools_for_role('warehouse')
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)

    avg_time = statistics.mean(times)
    p95_time = statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
    print(f"  角色工具过滤: 平均 {avg_time:.4f}ms, P95 {p95_time:.4f}ms")

    return {"avg_ms": avg_time, "p95_ms": p95_time}

def benchmark_document_schemas():
    """测试文档模式性能"""
    print("\n=== 文档模式性能测试 ===")

    from ai.documents.schemas import (
        DocumentExtraction, DocumentHeader, DocumentLine,
        DocumentType, MatchMethod,
    )

    times = []
    for _ in range(100):
        start = time.time()
        # 创建文档提取对象
        extraction = DocumentExtraction(
            header=DocumentHeader(
                document_type=DocumentType.IN_ORDER,
                supplier='测试供应商',
            ),
            lines=[
                DocumentLine(
                    line_no=1,
                    code='A001',
                    name='轴承',
                    quantity=100,
                    match_method=MatchMethod.EXACT_CODE,
                    matched_material_id=1,
                    confidence=1.0,
                ),
            ],
            total_lines=1,
            matched_lines=1,
        )
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)

    avg_time = statistics.mean(times)
    p95_time = statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
    print(f"  文档创建: 平均 {avg_time:.4f}ms, P95 {p95_time:.4f}ms")

    return {"avg_ms": avg_time, "p95_ms": p95_time}

def benchmark_concurrent_requests():
    """测试并发请求处理能力"""
    print("\n=== 并发请求性能测试 ===")

    from ai.tools.registry import list_ai_tool_specs

    def worker(worker_id):
        start = time.time()
        try:
            tools = list_ai_tool_specs()
            elapsed = (time.time() - start) * 1000
            return elapsed
        except Exception as e:
            return None

    # 测试不同并发级别
    concurrency_levels = [5, 10, 20]
    results = {}

    for level in concurrency_levels:
        times = []
        with ThreadPoolExecutor(max_workers=level) as executor:
            futures = [executor.submit(worker, i) for i in range(level)]
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    times.append(result)

        if times:
            avg_time = statistics.mean(times)
            success_rate = len(times) / level * 100
            results[level] = {"avg_ms": avg_time, "success_rate": success_rate}
            print(f"  并发 {level}: 平均 {avg_time:.2f}ms, 成功率 {success_rate:.1f}%")

    return results

def benchmark_circuit_breaker():
    """测试熔断器性能"""
    print("\n=== 熔断器性能测试 ===")

    from ai.providers import get_breaker

    breaker = get_breaker('chat')

    times = []
    for _ in range(100):
        start = time.time()
        breaker.allow_request()
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)

    avg_time = statistics.mean(times)
    p95_time = statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
    print(f"  熔断器检查: 平均 {avg_time:.4f}ms, P95 {p95_time:.4f}ms")

    return {"avg_ms": avg_time, "p95_ms": p95_time}

def main():
    """主测试函数"""
    print("=" * 60)
    print("WMS AI助手性能基准测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_results = {}

    # 运行各项测试
    all_results["tool_registry"] = benchmark_tool_registry()
    all_results["policy_engine"] = benchmark_policy_engine()
    all_results["document_schemas"] = benchmark_document_schemas()
    all_results["concurrent_requests"] = benchmark_concurrent_requests()
    all_results["circuit_breaker"] = benchmark_circuit_breaker()

    # 生成性能报告
    print("\n" + "=" * 60)
    print("性能基准测试报告")
    print("=" * 60)

    report = {
        "test_time": datetime.now().isoformat(),
        "results": all_results,
        "summary": {
            "tool_registry_p95": all_results["tool_registry"]["p95_ms"],
            "policy_engine_p95": all_results["policy_engine"]["p95_ms"],
            "document_schemas_p95": all_results["document_schemas"]["p95_ms"],
            "circuit_breaker_p95": all_results["circuit_breaker"]["p95_ms"],
        }
    }

    # 保存报告
    report_file = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n性能报告已保存到: {report_file}")

    # 性能评估
    print("\n=== 性能评估 ===")

    tool_p95 = report["summary"]["tool_registry_p95"]
    if tool_p95 <= 10:
        print(f"✓ 工具注册表 P95 {tool_p95:.4f}ms (目标: ≤10ms)")
    else:
        print(f"✗ 工具注册表 P95 {tool_p95:.4f}ms 超过目标 (目标: ≤10ms)")

    policy_p95 = report["summary"]["policy_engine_p95"]
    if policy_p95 <= 5:
        print(f"✓ 策略引擎 P95 {policy_p95:.4f}ms (目标: ≤5ms)")
    else:
        print(f"✗ 策略引擎 P95 {policy_p95:.4f}ms 超过目标 (目标: ≤5ms)")

    doc_p95 = report["summary"]["document_schemas_p95"]
    if doc_p95 <= 10:
        print(f"✓ 文档模式 P95 {doc_p95:.4f}ms (目标: ≤10ms)")
    else:
        print(f"✗ 文档模式 P95 {doc_p95:.4f}ms 超过目标 (目标: ≤10ms)")

    breaker_p95 = report["summary"]["circuit_breaker_p95"]
    if breaker_p95 <= 1:
        print(f"✓ 熔断器 P95 {breaker_p95:.4f}ms (目标: ≤1ms)")
    else:
        print(f"✗ 熔断器 P95 {breaker_p95:.4f}ms 超过目标 (目标: ≤1ms)")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
