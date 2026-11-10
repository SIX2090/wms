"""BUG-2026-11-11-001 offline regression lock.

批量微信分享 run_wechat_share_for_today() 逐单循环原本没有异常隔离：任意一张
入库单在图片生成 / 发送阶段抛异常，整个循环立即中断，排在它后面的所有单据
都不会再被处理，且已处理单据的结果也不会返回给调用方。修复为「逐单 try /
except」：坏单记日志 + 计入 failed，其余单据继续处理。

本锁只读取源码，用 AST 提取真实函数在纯合成命名空间执行；不导入 WMS 应用、
不连生产库、不访问现役服务、不发 HTTP、不写产品文件。R8 回退验证：把
app/app.py 还原为 HEAD 后本验证器必须出现失败项，逐字节恢复后必须全绿。

边界（有意保持不变，不属本缺陷）：
  * execute_share 自身对「可能已送达」的 uncertain 语义、force 语义不变；
  * created / skipped 计数与无失败时的 msg 文案逐字不变；
  * 定时任务每日 marker 去重语义不变（失败单不会被自动重复推送）；
  * 企业微信节流 sleep 不变。
"""
import ast
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / 'app' / 'app.py'
FUNC_NAME = 'run_wechat_share_for_today'


def _tree():
    return ast.parse(APP_PY.read_text(encoding='utf-8-sig'))


def _func(tree, name):
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(nodes) == 1, f'{name}: expected exactly 1 function, got {len(nodes)}'
    return nodes[0]


def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == name]


def _order(oid, status='sent', action='created'):
    def _impl(order):
        return types.SimpleNamespace(id=100 + order.id, status=status), action
    return _impl


def _run(orders, order_impl, *, master=True, wecom='', trigger='manual',
         config=None):
    """Execute the REAL function over a synthetic namespace (no app import)."""
    calls, commits, logs = [], [], []

    def _order_stub(config_arg, order, trigger_type='manual', force=False):
        calls.append(order)
        return order_impl(order)

    logger = types.SimpleNamespace(
        exception=lambda *a, **kw: logs.append((a, kw)),
        info=lambda *a, **kw: None,
    )
    scope = {
        '_wechat_share_master_enabled': lambda: master,
        '_wechat_share_default_config': lambda: types.SimpleNamespace(enabled=True, share_in_order=True),
        '_wechat_share_today_in_orders': lambda: orders,
        '_wechat_share_wecom_webhook': lambda: wecom,
        '_wechat_share_order': _order_stub,
        'db': types.SimpleNamespace(session=types.SimpleNamespace(
            commit=lambda: commits.append(1))),
        'app': types.SimpleNamespace(logger=logger),
    }
    module = ast.fix_missing_locations(
        ast.Module(body=[_func(_tree(), FUNC_NAME)], type_ignores=[]))
    exec(compile(module, '<copied-wechat-batch>', 'exec'), scope)
    result = scope[FUNC_NAME](
        trigger_type=trigger, force=False,
        config=config or types.SimpleNamespace(enabled=True, share_in_order=True))
    return result, calls, commits, logs


def _safe_run(*args, **kwargs):
    """Old (unfixed) code lets the per-order exception escape the batch loop.

    Keep the regression lock runnable on the reverted source so R8 evidence is a
    list of failed checks instead of an uncaught traceback.
    """
    try:
        return _run(*args, **kwargs)
    except Exception:
        return None, [], [], []


def _orders(count):
    return [types.SimpleNamespace(id=i, order_no=f'RK{i}') for i in range(1, count + 1)]


def run_checks():
    results = {}

    def check(name, fn):
        try:
            results[name] = bool(fn())
        except Exception:
            results[name] = False

    node = _func(_tree(), FUNC_NAME)
    loops = [n for n in ast.walk(node) if isinstance(n, ast.For)]
    check('static_single_batch_loop', lambda: len(loops) == 1)
    body = loops[0].body if loops else []
    tries = [n for n in body if isinstance(n, ast.Try)]
    check('static_loop_has_try', lambda: len(tries) == 1)
    try_node = tries[0] if tries else None

    check('static_order_call_inside_try',
          lambda: try_node is not None and len(_calls(try_node, '_wechat_share_order')) == 1)
    check('static_no_bare_order_call_outside_try',
          lambda: try_node is not None and not [
              n for stmt in body if stmt is not try_node for n in _calls(stmt, '_wechat_share_order')])
    handlers = try_node.handlers if try_node else []
    check('static_single_except_handler', lambda: len(handlers) == 1)
    handler = handlers[0] if handlers else None
    check('static_except_is_named_exception',
          lambda: handler is not None and isinstance(handler.type, ast.Name)
          and handler.type.id == 'Exception')
    check('static_except_continues_batch',
          lambda: handler is not None
          and any(isinstance(n, ast.Continue) for n in ast.walk(handler)))
    check('static_except_counts_failure',
          lambda: handler is not None and any(
              isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name)
              and n.target.id == 'failed' for n in ast.walk(handler)))
    check('static_except_logs_exception',
          lambda: handler is not None and any(
              isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == 'exception' for n in ast.walk(handler)))
    check('static_except_does_not_reraise',
          lambda: handler is not None
          and not [n for n in ast.walk(handler) if isinstance(n, ast.Raise)])
    check('static_failed_initialised',
          lambda: any(isinstance(n, ast.Assign) and any(
              isinstance(t, ast.Name) and t.id == 'failed' for t in n.targets)
              for n in ast.walk(node)))
    check('static_conditional_failure_suffix',
          lambda: any(isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                     and n.test.id == 'failed' for n in ast.walk(node)))
    check('static_throttle_preserved',
          lambda: any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr == 'sleep' for n in ast.walk(node)))
    returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)
               and isinstance(n.value, ast.Dict)]
    with_failed = [r for r in returns if any(
        isinstance(k, ast.Constant) and k.value == 'failed' for k in r.value.keys)]
    # 只有「空单」与「正常汇总」两条返回需要暴露 failed；三个短路返回保持原状。
    check('static_summary_returns_expose_failed', lambda: len(with_failed) == 2)
    check('static_final_return_exposes_failed',
          lambda: any(any(isinstance(k, ast.Constant) and k.value == 'msg'
                          and isinstance(v, ast.Name) and v.id == 'msg'
                          for k, v in zip(r.value.keys, r.value.values))
                      for r in with_failed))

    # 同类排查：定时任务侧的 config 批量循环已有 try/except 隔离，无需一并修改。
    jobs = _func(_tree(), 'run_due_wechat_share_jobs')
    job_loops = [n for n in ast.walk(jobs) if isinstance(n, ast.For)]
    check('same_class_scheduled_loop_already_isolated',
          lambda: len(job_loops) == 1
          and any(isinstance(stmt, ast.Try) for stmt in job_loops[0].body))

    # --- 行为：主场景（第 2 张抛异常，第 3 张必须继续）---
    orders = _orders(3)

    def _boom_on_second(order):
        if order.id == 2:
            raise RuntimeError('image generation failed')
        return _order(order.id)(order)

    result, calls, commits, logs = _safe_run(orders, _boom_on_second)
    check('behaviour_all_orders_attempted', lambda: [o.id for o in calls] == [1, 2, 3])
    check('behaviour_later_order_still_created', lambda: result['created'] == 2)
    check('behaviour_skipped_unchanged', lambda: result['skipped'] == 0)
    check('behaviour_failed_count', lambda: result.get('failed') == 1)
    check('behaviour_msg_reports_failure',
          lambda: '失败 1 张需人工核对' in result['msg'])
    check('behaviour_msg_keeps_original_prefix',
          lambda: result['msg'].startswith('已处理 3 张今日入库单，生成 2 张分享图片，跳过 0 张'))
    check('behaviour_exception_logged', lambda: len(logs) == 1 and '2' in str(logs[0]))
    check('behaviour_log_ids_exclude_failed', lambda: result['log_ids'] == [101, 103])
    check('behaviour_commit_still_called', lambda: len(commits) == 1)
    check('behaviour_uncertain_zero_on_clean_logs', lambda: result['uncertain'] == 0)
    check('behaviour_legacy_return_keys',
          lambda: {'status', 'msg', 'created', 'skipped', 'uncertain', 'log_ids'} <= set(result))

    # --- 行为：无失败时输出与修复前逐字一致 ---
    clean, clean_calls, _, clean_logs = _safe_run(orders, lambda o: _order(o.id)(o))
    check('behaviour_no_failure_msg_unchanged',
          lambda: clean['msg'] == '已处理 3 张今日入库单，生成 3 张分享图片，跳过 0 张')
    check('behaviour_no_failure_zero', lambda: clean['failed'] == 0)
    check('behaviour_no_failure_all_attempted', lambda: len(clean_calls) == 3)
    check('behaviour_no_failure_no_logs', lambda: clean_logs == [])

    # --- 行为：混合 skipped / 异常 / created ---
    def _mixed(order):
        if order.id == 2:
            raise RuntimeError('delivery exploded')
        return _order(order.id, action='skipped' if order.id == 1 else 'created')(order)

    mixed, mixed_calls, _, _ = _safe_run(orders, _mixed)
    check('behaviour_mixed_created', lambda: mixed['created'] == 1)
    check('behaviour_mixed_skipped', lambda: mixed['skipped'] == 1)
    check('behaviour_mixed_failed', lambda: mixed['failed'] == 1)
    check('behaviour_mixed_all_attempted', lambda: len(mixed_calls) == 3)
    check('behaviour_mixed_msg', lambda: '失败 1 张需人工核对' in mixed['msg'])

    # --- 行为：全部失败 ---
    all_bad, bad_calls, _, bad_logs = _safe_run(
        orders, lambda o: (_ for _ in ()).throw(RuntimeError('boom')))
    check('behaviour_all_failed_created_zero', lambda: all_bad['created'] == 0)
    check('behaviour_all_failed_skipped_zero', lambda: all_bad['skipped'] == 0)
    check('behaviour_all_failed_count', lambda: all_bad['failed'] == 3)
    check('behaviour_all_failed_msg', lambda: '失败 3 张需人工核对' in all_bad['msg'])
    check('behaviour_all_failed_still_attempted_all', lambda: len(bad_calls) == 3)
    check('behaviour_all_failed_each_logged', lambda: len(bad_logs) == 3)

    # --- 行为：空单 / 总开关 / 配置短路 ---
    empty, empty_calls, _, _ = _safe_run([], lambda o: _order(o.id)(o))
    check('behaviour_empty_orders', lambda: empty['msg'] == '今天没有已完成入库单'
          and empty['created'] == 0 and empty['skipped'] == 0 and empty['failed'] == 0)
    check('behaviour_empty_no_attempts', lambda: empty_calls == [])

    off, off_calls, _, _ = _safe_run(orders, lambda o: _order(o.id)(o), master=False)
    check('behaviour_master_switch_short_circuits',
          lambda: off['status'] == 'skipped' and off_calls == [])

    no_in_order, _, _, _ = _safe_run(
        orders, lambda o: _order(o.id)(o),
        config=types.SimpleNamespace(enabled=True, share_in_order=False))
    check('behaviour_share_in_order_short_circuits', lambda: no_in_order['status'] == 'skipped')

    scheduled_off, _, _, _ = _safe_run(
        orders, lambda o: _order(o.id)(o), trigger='scheduled',
        config=types.SimpleNamespace(enabled=False, share_in_order=True))
    check('behaviour_scheduled_disabled_short_circuits',
          lambda: scheduled_off['status'] == 'skipped')

    # --- 行为：uncertain 只统计成功返回的单 ---
    def _uncertain(order):
        if order.id == 2:
            raise RuntimeError('boom')
        return _order(order.id, status='uncertain' if order.id == 1 else 'delivery_started')(order)

    unc, _, _, _ = _safe_run(orders, _uncertain)
    check('behaviour_uncertain_counts_successful_logs_only', lambda: unc['uncertain'] == 2)

    return results


def main():
    results = run_checks()
    for name, ok in results.items():
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
    passed = sum(results.values())
    print(f'\n  {passed}/{len(results)} checks passed')
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
