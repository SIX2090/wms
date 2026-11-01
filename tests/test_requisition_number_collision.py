"""BUG-2026-11-01-024: also cover the req_no table-save consumer."""
from tests.test_document_create_number_conflicts import case  # noqa: F401
from tests import test_document_create_number_conflicts as common


ENTRY = ('work-requisition', '/requisition/save_table', 'ProductionRequisition', 'req_no')


def test_new_work_requisition_does_not_take_over_same_number(case):
    common.test_new_same_number_preserves_original_and_inventory(case, ENTRY, 'json')


def test_work_requisition_explicit_id_and_separate_new_number_still_work(case):
    common.test_explicit_id_still_edits_its_draft_and_new_number_creates_separate_document(case, ENTRY)
