#!/usr/bin/env python3
"""阶段2验证脚本：文档智能与送货单入库强化。

验证内容：
1. 统一提取Schema（DocumentExtraction/DocumentHeader/DocumentLine）
2. 文档任务状态机（状态转换合法性）
3. 匹配优先级引擎（精确编码→别名→名称规格→模糊→未匹配）
4. 文档提取流水线（文本/视觉/Excel）
5. 确认模块（修正/别名撤销/超量阻断）
6. 向后兼容（旧 documents/evaluation.py 仍可用）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage2-secret'
sys.path.insert(0, str(APP_DIR))


def test_schemas():
    print("测试统一提取Schema...")
    try:
        from ai.documents.schemas import (
            DocumentType, MatchMethod, DocumentStatus,
            DocumentHeader, DocumentLine, DocumentExtraction,
            CONFIDENCE_THRESHOLDS, CONFIRMATION_REASONS,
        )

        # 枚举值
        assert DocumentType.IN_ORDER.value == 'in_order'
        assert DocumentType.OUT_ORDER.value == 'out_order'
        assert MatchMethod.EXACT_CODE.value == 'exact_code'
        assert DocumentStatus.UPLOADING.value == 'uploading'

        # 置信度阈值
        assert CONFIDENCE_THRESHOLDS['high'] == 0.95
        assert CONFIDENCE_THRESHOLDS['medium'] == 0.80
        assert CONFIDENCE_THRESHOLDS['low'] == 0.60

        # 确认原因
        assert 'multiple_candidates' in CONFIRMATION_REASONS
        assert 'low_confidence' in CONFIRMATION_REASONS
        assert 'no_match' in CONFIRMATION_REASONS

        # 构建实例
        header = DocumentHeader(document_type=DocumentType.IN_ORDER, supplier='测试供应商')
        assert header.document_type == DocumentType.IN_ORDER
        assert header.supplier == '测试供应商'

        line = DocumentLine(line_no=1, code='A001', name='测试物料', quantity=10.0)
        assert line.line_no == 1
        assert line.needs_confirmation is True

        extraction = DocumentExtraction(header=header, lines=[line], total_lines=1)
        d = extraction.to_dict()
        assert d['header']['document_type'] == 'in_order'
        assert len(d['lines']) == 1

        # 反向序列化
        e2 = DocumentExtraction.from_dict(d)
        assert e2.header.document_type == DocumentType.IN_ORDER
        assert len(e2.lines) == 1

        print("  PASS: Schema定义完整")
        print("  PASS: 序列化/反序列化正确")
        return True
    except Exception as e:
        print(f"  FAIL: Schema测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_state_machine():
    print("测试文档任务状态机...")
    try:
        from ai.documents.state_machine import (
            DocumentTaskStateMachine, DocumentStatus,
            create_task, start_recognition, complete_recognition,
            create_draft, fail_task, cancel_task,
            StateMachineError,
        )

        # 正常流程
        task = create_task(user_id=1)
        assert task.current_status == DocumentStatus.UPLOADING
        assert not task.is_terminal()

        start_recognition(task, user_id=1)
        assert task.current_status == DocumentStatus.RECOGNIZING

        complete_recognition(task, user_id=1)
        assert task.current_status == DocumentStatus.PENDING_CONFIRM

        create_draft(task, user_id=1)
        assert task.current_status == DocumentStatus.DRAFT_CREATED
        assert task.is_terminal()

        print("  PASS: 正常流程 (uploading→recognizing→pending_confirm→draft_created)")

        # 失败流程
        task2 = create_task(user_id=1)
        start_recognition(task2)
        fail_task(task2)
        assert task2.current_status == DocumentStatus.FAILED
        assert task2.is_terminal()

        print("  PASS: 失败流程 (recognizing→failed)")

        # 取消流程
        task3 = create_task(user_id=1)
        start_recognition(task3)
        complete_recognition(task3)
        cancel_task(task3)
        assert task3.current_status == DocumentStatus.CANCELLED
        assert task3.is_terminal()

        print("  PASS: 取消流程 (pending_confirm→cancelled)")

        # 非法转换
        task4 = create_task(user_id=1)
        try:
            task4.transition(DocumentStatus.DRAFT_CREATED)
            print("  FAIL: 应抛出非法转换异常")
            return False
        except StateMachineError:
            pass

        print("  PASS: 非法转换被阻止")

        # 状态历史
        task5 = create_task(user_id=1)
        start_recognition(task5, user_id=1)
        complete_recognition(task5, user_id=1)
        history = task5.get_history()
        assert len(history) == 3
        assert history[0]['status'] == 'uploading'
        assert history[1]['status'] == 'recognizing'
        assert history[2]['status'] == 'pending_confirm'

        print("  PASS: 状态历史记录正确")
        return True
    except Exception as e:
        print(f"  FAIL: 状态机测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_extractor():
    print("测试文档提取流水线...")
    try:
        from ai.documents.extractor import (
            extract_from_text, extract_from_vision, extract_from_excel_table,
            _guess_doc_type, _is_wechat_delivery, _parse_material_segments,
        )
        from ai.documents.schemas import DocumentType

        # 微信发货通知
        ext1 = extract_from_text('明天发鑫达 6204轴承 100套，M8螺母 500个')
        assert ext1.header.document_type == DocumentType.IN_ORDER
        assert ext1.header.supplier == '鑫达'
        assert len(ext1.lines) >= 2
        assert ext1.source_type == 'text'

        print("  PASS: 微信发货通知识别正确")

        # 送货单文本
        ext2 = extract_from_text('送货单 A001 50个 B002 30件')
        assert ext2.header.document_type == DocumentType.IN_ORDER
        assert len(ext2.lines) >= 1

        print("  PASS: 送货单文本识别正确")

        # 领料单文本
        ext3 = extract_from_text('领料 M001 20套 M002 15个')
        assert ext3.header.document_type == DocumentType.OUT_ORDER
        assert len(ext3.lines) >= 1

        print("  PASS: 领料单文本识别正确")

        # 视觉模型JSON回复
        vision_json = {
            'document_type': 'in_order',
            'supplier': '测试供应商',
            'items': [
                {'code': 'A001', 'name': '轴承', 'quantity': 100},
                {'code': 'B002', 'name': '螺母', 'quantity': 500},
            ]
        }
        ext4 = extract_from_vision('', extracted_json=vision_json)
        assert ext4.header.document_type == DocumentType.IN_ORDER
        assert ext4.header.supplier == '测试供应商'
        assert len(ext4.lines) == 2
        assert ext4.lines[0].code == 'A001'
        assert ext4.lines[0].quantity == 100.0

        print("  PASS: 视觉模型JSON提取正确")

        # Excel表格
        ext5 = extract_from_excel_table('A001\t轴承\t6204\t100\t套\nB002\t螺母\tM8\t500\t个')
        assert len(ext5.lines) == 2
        assert ext5.lines[0].code == 'A001'
        assert ext5.lines[0].quantity == 100.0

        print("  PASS: Excel表格提取正确")

        # 空文本
        ext6 = extract_from_text('')
        assert ext6.header.document_type == DocumentType.OTHER
        assert len(ext6.lines) == 0

        print("  PASS: 空文本处理正确")

        # 文档类型猜测
        assert _guess_doc_type('送货单') == DocumentType.IN_ORDER
        assert _guess_doc_type('领料') == DocumentType.OUT_ORDER
        assert _guess_doc_type('调拨') == DocumentType.TRANSFER
        assert _guess_doc_type('盘点') == DocumentType.CHECK
        assert _guess_doc_type('报废') == DocumentType.ADJUSTMENT

        print("  PASS: 文档类型猜测正确")

        # 微信发货检测
        assert _is_wechat_delivery('明天发鑫达 6204轴承 100套') is True
        assert _is_wechat_delivery('发给客户 A001 10个') is False

        print("  PASS: 微信发货检测正确")

        return True
    except Exception as e:
        print(f"  FAIL: 提取流水线测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_confirmation():
    # 已移除：依赖 legacy confirmation.py（已被 document_confirmation.py AI-R08 取代）
    # 新 API 验证见 verify_ai_document_confirmation.py
    print("测试确认模块... [SKIP: legacy confirmation.py 已移除]")
    return True


def _test_confirmation_legacy():
    print("测试确认模块...")
    try:
        from ai.documents.confirmation import (
            build_confirmation_context, apply_confirmation_corrections,
            ConfirmationItem, ConfirmationContext,
        )
        from ai.documents.schemas import (
            DocumentExtraction, DocumentHeader, DocumentLine,
            DocumentType, MatchMethod,
        )

        # 构建确认上下文
        header = DocumentHeader(document_type=DocumentType.IN_ORDER, supplier='测试')
        lines = [
            DocumentLine(line_no=1, code='A001', name='轴承', quantity=100,
                         match_method=MatchMethod.EXACT_CODE, confidence=1.0,
                         matched_material_id=1, needs_confirmation=False),
            DocumentLine(line_no=2, code='B002', name='螺母', quantity=500,
                         match_method=MatchMethod.MULTIPLE_CANDIDATES, confidence=0.5,
                         matched_material_id=None, needs_confirmation=True,
                         confirmation_reason='多个候选物料，请选择正确的一个'),
            DocumentLine(line_no=3, code='', name='未知物料', quantity=10,
                         match_method=MatchMethod.NONE, confidence=0.0,
                         matched_material_id=None, needs_confirmation=True,
                         confirmation_reason='未找到匹配物料，请手动选择或创建'),
        ]
        extraction = DocumentExtraction(header=header, lines=lines, total_lines=3)

        ctx = build_confirmation_context(task_id=1, extraction=extraction)
        assert ctx.needs_confirmation is True
        assert len(ctx.items) == 3
        assert ctx.auto_confirmable_lines == [1]  # 只有第1行可自动确认

        d = ctx.to_dict()
        assert d['summary']['total'] == 3
        assert d['summary']['needs_confirmation'] == 2
        assert d['summary']['auto_confirmable'] == 1

        print("  PASS: 确认上下文构建正确")

        # 超采购数量阻断
        po_qty = {1: 50}  # 物料1的未到货量为50
        ctx2 = build_confirmation_context(
            task_id=2, extraction=extraction,
            purchase_order_quantities=po_qty,
        )
        assert 1 in ctx2.blocked_lines  # 第1行数量100 > 50被阻断

        print("  PASS: 超采购数量阻断正确")

        # 应用修正
        corrections = [
            {'line_no': 2, 'matched_material_id': 2, 'code': 'B002'},
            {'line_no': 3, 'delete': True},
        ]
        ext_corrected = apply_confirmation_corrections(extraction, corrections)
        assert ext_corrected.lines[1].matched_material_id == 2
        assert ext_corrected.lines[1].confidence == 1.0
        assert ext_corrected.lines[1].needs_confirmation is False
        assert ext_corrected.lines[2].quantity == 0  # 已删除

        print("  PASS: 修正应用正确")

        return True
    except Exception as e:
        print(f"  FAIL: 确认模块测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_backward_compat():
    print("测试向后兼容...")
    try:
        from ai.documents.evaluation import (
            evaluate_document_samples, DocumentEvaluationResult,
        )

        samples = [
            {
                'expected': {
                    'document_type': 'in_order',
                    'supplier': 'test',
                    'items': [{'code': 'a001', 'name': '轴承', 'quantity': 100}],
                },
                'actual': {
                    'document_type': 'in_order',
                    'supplier': 'test',
                    'items': [{'code': 'a001', 'name': '轴承', 'quantity': 100}],
                },
            }
        ]
        result = evaluate_document_samples(samples)
        assert result.sample_count == 1
        assert result.header_accuracy == 1.0
        assert result.line_recall == 1.0
        assert result.quantity_accuracy == 1.0

        print("  PASS: 旧 evaluation.py 仍可用")
        return True
    except Exception as e:
        print(f"  FAIL: 向后兼容测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("阶段2验证：文档智能与送货单入库强化")
    print("=" * 60)

    results = []
    results.append(("统一Schema", test_schemas()))
    results.append(("状态机", test_state_machine()))
    results.append(("提取流水线", test_extractor()))
    results.append(("确认模块", test_confirmation()))
    results.append(("向后兼容", test_backward_compat()))

    print("\n" + "=" * 60)
    print("验证结果汇总:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("PASS: 阶段2验证全部通过")
        return 0
    else:
        print("FAIL: 阶段2验证存在失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())
