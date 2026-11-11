"""BUG-2026-11-11-001 offline regression lock.

批量微信分享 run_wechat_share_for_today() 逐单循环原本没有异常隔离：任意一张
入库单在图片生成 / 发送阶段抛异常，整个循环立即中断，排在它后面的所有单据
都不会再被处理。修复为「逐单 try/except」：坏单记日志、保留异常、继续处理
其余单据；**整批处理完后再把首个异常原样交回调用方**。

后半点是本批 CI #2114 的回归纠正（10 个既有用例失败）：/wechat_share/run_now
依赖 DispatchUnavailable 冒泡返回 503 与具体错误信息；如果在循环里把异常吞掉
并返回 200，既有「传输结果不明 / 缺表 / 落库失败」等 fail-closed 契约全部失效。
因此逐单隔离只解决「后续单据漏发」，不改变请求级失败语义与返回结构。

本锁只读取源码，用 AST 提取真实函数在纯合成命名空间执行；不导入 WMS 应用、
不连生产库、不访问现役服务、不发 HTTP、不写产品文件。R8 回退验证：把
app/app.py 还原为 HEAD 后本验证器必须出现失败项，逐字节恢复后必须全绿。

边界（有意保持不变，不属本缺陷）：
  * execute_share 自身对「可能已送达」的 uncertain 语义、force 语义不变；
  * created / skipped 计数、msg 文案、返回字段集合逐字逐项不变；
  * 定时任务每日 marker 去重语义不变（异常仍冒泡到定时任务 except）；
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


def _order(_oid, status='sent', action='created'):
    def _impl(order):
        return types.SimpleNamespace(id=100 + order.id, status=status), action
    return _impl


def _run(orders, order_impl, *, master=True, wecom='', trigger='manual',
         config=None):
    """Execute the REAL function over a synthetic namespace (no app import).

    Returns (result, calls, commits, logs, raised). An exception raised by the
    batch is returned rather than propagated, so every scenario stays inspectable.
    """
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
    try:
        result = scope[FUNC_NAME](
            trigger_type=trigger, force=False,
            config=config or types.SimpleNamespace(enabled=True, share_in_order=True))
    except Exception as exc:
        return None, calls, commits, logs, exc
    return result, calls, commits, logs, None


def _safe_run(*args, **kwargs):
    """Keep the lock runnable on reverted source (R8 evidence = failed checks)."""
    try:
        return _run(*args, **kwargs)
    except Exception as exc:
        return None, [], [], [], exc


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
    check('static_except_records_exception',
          lambda: handler is not None and any(
              isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == 'append' for n in ast.walk(handler)))
    check('static_except_logs_exception',
          lambda: handler is not None and any(
              isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == 'exception' for n in ast.walk(handler)))
    check('static_except_does_not_reraise',
          lambda: handler is not None
          and not [n for n in ast.walk(handler) if isinstance(n, ast.Raise)])
    check('static_errors_initialised',
          lambda: any(isinstance(n, ast.Assign) and any(
              isinstance(t, ast.Name) and t.id == 'errors' for t in n.targets)
              for n in ast.walk(node)))

    top = node.body
    loop_index = next((i for i, stmt in enumerate(top) if stmt is loops[0]), -1) if loops else -1
    tail = top[loop_index + 1:] if loop_index >= 0 else []
    reraises = [n for n in ast.walk(node) if isinstance(n, ast.Raise)]
    check('static_first_error_reraised_after_loop', lambda: len(reraises) == 1)
    check('static_reraise_is_guarded',
          lambda: any(isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                     and n.test.id == 'errors'
                     and any(isinstance(x, ast.Raise) for x in n.body) for n in tail))
    commit_idx = next((i for i, n in enumerate(tail)
                       if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                       and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'commit'), 99)
    guard_idx = next((i for i, n in enumerate(tail)
                      if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                      and n.test.id == 'errors'), 99)
    check('static_reraise_precedes_batch_commit', lambda: guard_idx < commit_idx)
    check('static_reraise_uses_stored_error',
          lambda: reraises and isinstance(reraises[0].exc, ast.Subscript))
    check('static_throttle_preserved',
          lambda: any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr == 'sleep' for n in ast.walk(node)))
    returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)
               and isinstance(n.value, ast.Dict)]
    check('static_return_shape_unchanged',
          lambda: len(returns) >= 2 and not any(
              any(isinstance(k, ast.Constant) and k.value == 'failed' for k in r.value.keys)
              for r in returns))
    check('static_msg_still_inline_fstring',
          lambda: any(any(isinstance(k, ast.Constant) and k.value == 'msg'
                          and isinstance(v, ast.JoinedStr)
                          for k, v in zip(r.value.keys, r.value.values)) for r in returns))
    check('static_no_failure_counter_in_source',
          lambda: not any(isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name)
                         and n.target.id == 'failed' for n in ast.walk(node)))

    # 同类排查：定时任务侧的 config 批量循环已有 try/except 隔离，无需一并修改。
    jobs = _func(_tree(), 'run_due_wechat_share_jobs')
    job_loops = [n for n in ast.walk(jobs) if isinstance(n, ast.For)]
    check('same_class_scheduled_loop_already_isolated',
          lambda: len(job_loops) == 1
          and any(isinstance(stmt, ast.Try) for stmt in job_loops[0].body))

    # --- 行为：主场景（第 2 张抛异常，第 3 张必须继续，异常仍交回调用方）---
    orders = _orders(3)

    def _boom_on_second(order):
        if order.id == 2:
            raise RuntimeError('image generation failed')
        return _order(order.id)(order)

    result, calls, commits, logs, raised = _safe_run(orders, _boom_on_second)
    check('behaviour_all_orders_attempted', lambda: [o.id for o in calls] == [1, 2, 3])
    check('behaviour_later_order_still_attempted', lambda: calls[-1].id == 3)
    check('behaviour_no_silent_success', lambda: result is None and raised is not None)
    check('behaviour_original_exception_reraised',
          lambda: isinstance(raised, RuntimeError) and 'image generation failed' in str(raised))
    check('behaviour_exception_logged', lambda: len(logs) == 1 and '2' in str(logs[0]))
    check('behaviour_logger_receives_order_id', lambda: logs and logs[0][0][-1] == 2)
    check('behaviour_no_commit_before_reraise', lambda: commits == [])

    # --- 行为：无失败时输出与修复前逐字一致，返回结构不变 ---
    clean, clean_calls, clean_commits, clean_logs, clean_raised = _safe_run(
        orders, lambda o: _order(o.id)(o))
    check('behaviour_no_failure_msg_unchanged',
          lambda: clean['msg'] == '已处理 3 张今日入库单，生成 3 张分享图片，跳过 0 张')
    check('behaviour_no_failure_return_shape',
          lambda: set(clean) == {'status', 'msg', 'created', 'skipped', 'uncertain', 'log_ids'})
    check('behaviour_no_failure_counts', lambda: clean['created'] == 3 and clean['skipped'] == 0)
    check('behaviour_no_failure_all_attempted', lambda: len(clean_calls) == 3)
    check('behaviour_no_failure_no_logs', lambda: clean_logs == [])
    check('behaviour_no_failure_no_exception', lambda: clean_raised is None)
    check('behaviour_no_failure_commit_called', lambda: len(clean_commits) == 1)
    check('behaviour_no_failure_log_ids', lambda: clean['log_ids'] == [101, 102, 103])

    # --- 行为：混合 skipped / 异常 / created ---
    def _mixed(order):
        if order.id == 2:
            raise RuntimeError('delivery exploded')
        return _order(order.id, action='skipped' if order.id == 1 else 'created')(order)

    mixed, mixed_calls, _, mixed_logs, mixed_raised = _safe_run(orders, _mixed)
    check('behaviour_mixed_all_attempted', lambda: len(mixed_calls) == 3)
    check('behaviour_mixed_reraised',
          lambda: mixed is None and 'delivery exploded' in str(mixed_raised))
    check('behaviour_mixed_logged', lambda: len(mixed_logs) == 1)

    # --- 行为：全部失败仍逐单尝试，只把首个异常交回 ---
    def _always_boom(order):
        raise RuntimeError(f'boom-{order.id}')

    all_bad, bad_calls, _, bad_logs, bad_raised = _safe_run(orders, _always_boom)
    check('behaviour_all_failed_still_attempted_all', lambda: len(bad_calls) == 3)
    check('behaviour_all_failed_each_logged', lambda: len(bad_logs) == 3)
    check('behaviour_all_failed_reraises_first', lambda: str(bad_raised) == 'boom-1')

    # --- 行为：单张单据失败仍冒泡（既有 10 个 fail-closed 用例的 503 语义）---
    single, single_calls, _, _, single_raised = _safe_run(_orders(1), _always_boom)
    check('behaviour_single_failure_still_reraises',
          lambda: single is None and single_raised is not None and len(single_calls) == 1)

    # --- 行为：空单 / 总开关 / 配置短路 ---
    empty, empty_calls, _, _, empty_raised = _safe_run([], lambda o: _order(o.id)(o))
    check('behaviour_empty_orders', lambda: empty['msg'] == '今天没有已完成入库单'
          and empty['created'] == 0 and empty['skipped'] == 0 and empty['logs'] == [])
    check('behaviour_empty_return_shape', lambda: 'failed' not in empty)
    check('behaviour_empty_no_attempts', lambda: empty_calls == [])
    check('behaviour_empty_no_exception', lambda: empty_raised is None)

    off, off_calls, _, _, _ = _safe_run(orders, lambda o: _order(o.id)(o), master=False)
    check('behaviour_master_switch_short_circuits',
          lambda: off['status'] == 'skipped' and off_calls == [])

    no_in_order, _, _, _, _ = _safe_run(
        orders, lambda o: _order(o.id)(o),
        config=types.SimpleNamespace(enabled=True, share_in_order=False))
    check('behaviour_share_in_order_short_circuits', lambda: no_in_order['status'] == 'skipped')

    scheduled_off, _, _, _, _ = _safe_run(
        orders, lambda o: _order(o.id)(o), trigger='scheduled',
        config=types.SimpleNamespace(enabled=False, share_in_order=True))
    check('behaviour_scheduled_disabled_short_circuits',
          lambda: scheduled_off['status'] == 'skipped')

    # --- 行为：uncertain 统计（无异常场景）---
    def _uncertain(order):
        return _order(order.id, status='uncertain' if order.id == 1 else
                      'delivery_started' if order.id == 2 else 'sent')(order)

    unc, _, _, _, unc_raised = _safe_run(orders, _uncertain)
    check('behaviour_uncertain_counts_delivery_states',
          lambda: unc['uncertain'] == 2 and unc_raised is None)

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
