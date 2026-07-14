"""AI 草稿统一幂等与审计闭环验证脚本 (AI-R01)。

验证内容（对应台账验收标准）：
1. 首次创建草稿：acquire 返回 acquired=True，complete 后 status=completed
2. 重复请求：相同业务键 acquire 返回 is_replay=True，不创建重复草稿
3. 并发竞争：两个 acquire 同时提交相同键，仅一个成功（IntegrityError 处理）
4. 失败重试：fail 标记 status=failed 后，再次 acquire 可获得新槽位
5. 反查链路：find_by_draft / find_by_run / find_by_confirmation 可从草稿反查审计记录
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-draft-idempotency-secret'
os.environ['PYTHONUTF8'] = '1'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.draft_idempotency import (
    DRAFT_STATUS_COMPLETED,
    DRAFT_STATUS_FAILED,
    DRAFT_STATUS_PROCESSING,
    DRAFT_STATUS_REPLAYED,
)


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SQLALCHEMY_DATABASE_URI=os.environ.get('WMS_DATABASE_URI'))

    with app.app_context():
        wms_app.db.create_all()

        # ---- 准备测试数据 ----
        unit = wms_app.Unit(name='个', code='PCS')
        wms_app.db.session.add(unit)
        wms_app.db.session.flush()

        materials = []
        for idx, code in enumerate(('M0001', 'M0002', 'M0003')):
            mat = wms_app.Material(
                code=code,
                name=f'测试物料{idx + 1}',
                unit_id=unit.id,
                price=10.0,
                stock=100,
            )
            wms_app.db.session.add(mat)
            materials.append(mat)
        wms_app.db.session.flush()

        user = wms_app.User(
            username='draft-idempotency-verifier',
            password_hash='not-used',
            role='admin',
            status='normal',
        )
        wms_app.db.session.add(user)
        wms_app.db.session.commit()
        user_id = user.id

        service = wms_app._ai_draft_idempotency()

        # ---- 测试 1: 首次创建草稿 ----
        business_fields = {
            'items': sorted([(m.id, 20.0) for m in materials[:2]]),
            'message': '出库 M0001 20 M0002 20',
        }
        slot1 = service.acquire(
            capability='out_order_draft',
            source='text',
            business_fields=business_fields,
            draft_type='out_order',
            request_snapshot={'message': '出库 M0001 20 M0002 20'},
            user_id=user_id,
        )
        assert slot1.acquired, f'首次 acquire 应成功，但得到: {slot1.conflict_reason}'
        assert slot1.record is not None
        assert slot1.record.status == DRAFT_STATUS_PROCESSING
        assert slot1.record.user_id == user_id
        assert slot1.record.capability == 'out_order_draft'
        assert slot1.record.source == 'text'

        response1 = {'order_no': 'OU-TEST-0001', 'items': [{'code': 'M0001', 'quantity': 20}]}
        service.complete(
            slot1.record,
            draft_type='out_order',
            draft_id=1001,
            draft_no='OU-TEST-0001',
            response=response1,
        )
        assert slot1.record.status == DRAFT_STATUS_COMPLETED
        assert slot1.record.draft_id == 1001
        assert slot1.record.draft_no == 'OU-TEST-0001'
        assert slot1.record.completed_at is not None
        print('PASS 测试1: 首次创建草稿成功，状态 completed，记录 draft_id/draft_no')

        # ---- 测试 2: 重复请求返回 replay，不创建重复 ----
        slot2 = service.acquire(
            capability='out_order_draft',
            source='text',
            business_fields=business_fields,
            draft_type='out_order',
            request_snapshot={'message': '出库 M0001 20 M0002 20'},
            user_id=user_id,
        )
        assert not slot2.acquired, '重复 acquire 不应获得新槽位'
        assert slot2.is_replay, '重复 acquire 应返回 is_replay=True'
        assert slot2.replay == response1, f'replay 响应应等于首次响应，得到: {slot2.replay}'
        assert slot2.record.id == slot1.record.id, 'replay 应指向同一条记录'
        print('PASS 测试2: 重复请求返回 replay，无重复草稿')

        # ---- 统计：当前只有 1 条 completed 记录 ----
        all_records = wms_app.AIDraftIdempotency.query.filter_by(
            user_id=user_id, capability='out_order_draft',
        ).all()
        assert len(all_records) == 1, f'应只有 1 条记录，实际 {len(all_records)}'
        assert all_records[0].status in (DRAFT_STATUS_COMPLETED, DRAFT_STATUS_REPLAYED)

        # ---- 测试 3: 并发竞争（唯一约束 + IntegrityError 处理） ----
        # 直接向数据库插入一条 processing 记录，模拟并发请求已抢先写入
        from ai.draft_idempotency import compute_draft_idempotency_key
        concurrent_fields = {
            'items': [(materials[0].id, 50.0)],
            'message': '并发测试入库 M0001 50',
        }
        concurrent_key = compute_draft_idempotency_key(user_id, 'in_order_draft', 'text', concurrent_fields)
        racing_record = wms_app.AIDraftIdempotency(
            user_id=user_id,
            capability='in_order_draft',
            idempotency_key=concurrent_key,
            source='text',
            source_hash='racing',
            business_key='{}',
            draft_type='in_order',
            status=DRAFT_STATUS_PROCESSING,
        )
        wms_app.db.session.add(racing_record)
        wms_app.db.session.commit()

        # 此时 acquire 应发现已存在的 processing 记录并拒绝（模拟并发冲突）
        slot_race = service.acquire(
            capability='in_order_draft',
            source='text',
            business_fields=concurrent_fields,
            draft_type='in_order',
            request_snapshot={'message': '并发测试'},
            user_id=user_id,
        )
        assert not slot_race.acquired, '并发冲突时 acquire 不应获得槽位'
        assert not slot_race.is_replay, 'processing 状态不应返回 replay'
        assert slot_race.record is not None, '应返回已存在的 processing 记录'
        assert slot_race.record.id == racing_record.id
        assert '处理中' in slot_race.conflict_reason or '并发' in slot_race.conflict_reason, \
            f'冲突原因应提示处理中/并发，得到: {slot_race.conflict_reason}'
        print('PASS 测试3a: 并发竞争——processing 记录阻止重复获取')

        # 测试唯一约束：直接插入相同键应抛出 IntegrityError
        from sqlalchemy.exc import IntegrityError as SAIntegrityError
        duplicate_record = wms_app.AIDraftIdempotency(
            user_id=user_id,
            capability='in_order_draft',
            idempotency_key=concurrent_key,
            source='text',
            draft_type='in_order',
            status=DRAFT_STATUS_PROCESSING,
        )
        wms_app.db.session.add(duplicate_record)
        try:
            wms_app.db.session.commit()
            raise AssertionError('唯一约束未生效：相同 (user_id, capability, idempotency_key) 应抛出 IntegrityError')
        except SAIntegrityError:
            wms_app.db.session.rollback()
            print('PASS 测试3b: 唯一约束 (user_id, capability, idempotency_key) 正确阻止重复插入')

        # 将 racing 记录标记为完成，使后续 acquire 返回 replay
        service.complete(
            racing_record,
            draft_type='in_order',
            draft_id=2001,
            draft_no='PI-CONCURRENT-0001',
            response={'order_no': 'PI-CONCURRENT-0001'},
        )
        slot_after_complete = service.acquire(
            capability='in_order_draft',
            source='text',
            business_fields=concurrent_fields,
            draft_type='in_order',
            request_snapshot={'message': '并发测试'},
            user_id=user_id,
        )
        assert slot_after_complete.is_replay, 'completed 后再 acquire 应返回 replay'
        assert slot_after_complete.replay == {'order_no': 'PI-CONCURRENT-0001'}
        print('PASS 测试3c: 并发完成后重试返回 replay（无重复草稿）')

        # ---- 测试 4: 失败重试 ----
        fail_fields = {
            'items': [(materials[2].id, 5.0)],
            'message': '报废 M0003 5',
        }
        slot_fail = service.acquire(
            capability='adjustment_draft',
            source='text',
            business_fields=fail_fields,
            draft_type='adjustment',
            request_snapshot={'message': '报废 M0003 5', 'adjustment_type': 'loss'},
            user_id=user_id,
        )
        assert slot_fail.acquired, '失败测试首次 acquire 应成功'
        service.fail(slot_fail.record, '模拟业务异常：库存不足')
        assert slot_fail.record.status == DRAFT_STATUS_FAILED
        assert slot_fail.record.error_message == '模拟业务异常：库存不足'
        assert slot_fail.record.completed_at is None
        print('PASS 测试4a: 失败标记 status=failed，保留错误信息')

        # 失败后重试：相同业务键应获得新槽位
        slot_retry = service.acquire(
            capability='adjustment_draft',
            source='text',
            business_fields=fail_fields,
            draft_type='adjustment',
            request_snapshot={'message': '报废 M0003 5', 'adjustment_type': 'loss'},
            user_id=user_id,
        )
        assert slot_retry.acquired, '失败后重试应获得新槽位'
        assert slot_retry.record.id == slot_fail.record.id, '重试应复用原记录保留历史'
        assert slot_retry.record.status == DRAFT_STATUS_PROCESSING, '重试后状态应回到 processing'
        assert slot_retry.record.error_message is None, '重试应清除错误信息'
        service.complete(
            slot_retry.record,
            draft_type='adjustment',
            draft_id=3001,
            draft_no='AD-RETRY-0001',
            response={'order_no': 'AD-RETRY-0001'},
        )
        assert slot_retry.record.status == DRAFT_STATUS_COMPLETED
        print('PASS 测试4b: 失败后重试成功，复用原记录，状态 completed')

        # ---- 测试 5: 反查链路 ----
        # 5a: find_by_draft
        found_by_draft = service.find_by_draft('out_order', 1001)
        assert found_by_draft is not None, 'find_by_draft 应找到记录'
        assert found_by_draft.id == slot1.record.id
        assert found_by_draft.draft_no == 'OU-TEST-0001'
        assert found_by_draft.user_id == user_id

        # 5b: find_by_draft 返回 None 对不存在的情况
        assert service.find_by_draft('out_order', 999999) is None

        # 5c: find_by_confirmation
        token = 'confirm-token-test-0001'
        confirm_fields = {
            'items': [(materials[1].id, 30.0)],
            'confirmation_token': token,
        }
        slot_confirm = service.acquire(
            capability='purchase_request_draft',
            source='confirmation',
            business_fields=confirm_fields,
            draft_type='purchase_request',
            request_snapshot={'source_text': '采购申请确认'},
            confirmation_token=token,
            document_job_id=5001,
            user_id=user_id,
        )
        assert slot_confirm.acquired
        assert slot_confirm.record.confirmation_token == token
        assert slot_confirm.record.document_job_id == 5001
        assert slot_confirm.record.source == 'confirmation'
        service.complete(
            slot_confirm.record,
            draft_type='purchase_request',
            draft_id=4001,
            draft_no='PR-CONFIRM-0001',
            response={'order_no': 'PR-CONFIRM-0001'},
        )

        found_by_token = service.find_by_confirmation(token)
        assert found_by_token is not None, 'find_by_confirmation 应找到记录'
        assert found_by_token.id == slot_confirm.record.id
        assert found_by_token.draft_type == 'purchase_request'
        assert found_by_token.draft_id == 4001

        # 5d: find_by_confirmation 返回 None 对空 token
        assert service.find_by_confirmation('') is None
        assert service.find_by_confirmation('nonexistent') is None

        # 5e: find_by_run
        run_id = 99999
        slot_with_run = service.acquire(
            capability='transfer_draft',
            source='text',
            business_fields={'items': [(materials[0].id, 10.0)], 'from': 'WH01', 'to': 'WH02'},
            draft_type='transfer',
            request_snapshot={'message': '调拨测试'},
            user_id=user_id,
            ai_run_id=run_id,
        )
        assert slot_with_run.acquired
        service.complete(
            slot_with_run.record,
            draft_type='transfer',
            draft_id=6001,
            draft_no='TF-RUN-0001',
            response={'order_no': 'TF-RUN-0001'},
        )
        found_by_run = service.find_by_run(run_id)
        assert len(found_by_run) >= 1, 'find_by_run 应返回至少 1 条记录'
        assert any(r.id == slot_with_run.record.id for r in found_by_run)
        assert service.find_by_run(0) == []

        print('PASS 测试5: 反查链路完整（find_by_draft / find_by_confirmation / find_by_run）')

        # ---- 测试 6: 不同业务键不冲突 ----
        different_fields = {
            'items': [(materials[0].id, 99.0)],  # 不同数量
            'message': '出库 M0001 99',
        }
        slot_diff = service.acquire(
            capability='out_order_draft',
            source='text',
            business_fields=different_fields,
            draft_type='out_order',
            request_snapshot={'message': '出库 M0001 99'},
            user_id=user_id,
        )
        assert slot_diff.acquired, '不同业务键应获得新槽位（非 replay）'
        assert slot_diff.record.id != slot1.record.id, '不同业务键应创建新记录'
        service.complete(
            slot_diff.record,
            draft_type='out_order',
            draft_id=1002,
            draft_no='OU-TEST-0002',
            response={'order_no': 'OU-TEST-0002'},
        )
        print('PASS 测试6: 不同业务键创建新记录，不误判为重复')

        # ---- 测试 7: attach_tool_call 延迟关联 ----
        slot_no_tc = service.acquire(
            capability='check_draft',
            source='text',
            business_fields={'items': [(materials[0].id, 10.0)], 'message': '盘点 M0001'},
            draft_type='check',
            request_snapshot={'message': '盘点 M0001'},
            user_id=user_id,
        )
        assert slot_no_tc.acquired
        assert slot_no_tc.record.ai_tool_call_id is None
        service.attach_tool_call(slot_no_tc.record, 77777)
        assert slot_no_tc.record.ai_tool_call_id == 77777
        # 幂等：重复 attach 相同值不报错
        service.attach_tool_call(slot_no_tc.record, 77777)
        assert slot_no_tc.record.ai_tool_call_id == 77777
        service.complete(
            slot_no_tc.record,
            draft_type='check',
            draft_id=7001,
            draft_no='CK-TC-0001',
            response={'order_no': 'CK-TC-0001'},
        )
        print('PASS 测试7: attach_tool_call 延迟关联工具调用记录')

        # ---- 最终统计 ----
        total = wms_app.AIDraftIdempotency.query.count()
        completed = wms_app.AIDraftIdempotency.query.filter_by(status=DRAFT_STATUS_COMPLETED).count()
        failed = wms_app.AIDraftIdempotency.query.filter_by(status=DRAFT_STATUS_FAILED).count()
        assert failed == 0, f'不应有残留 failed 记录（已重试完成），实际 {failed}'
        assert completed >= 5, f'应有至少 5 条 completed 记录，实际 {completed}'
        print(f'\n统计: 总记录 {total} 条, completed {completed} 条, failed {failed} 条')

    print('\nPASS AI-DRAFT-IDEMPOTENCY: 首次/重复/并发/失败重试/反查全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
