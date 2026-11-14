"""Same 60 boundaries through actual WMS update HTTP, verified isolation only."""
import ast
import math
import types
import unittest

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from sqlalchemy import event  # noqa: E402
import app as w  # noqa: E402
from tests.test_purchase_reservation_source_20261114 import HELPERS  # noqa: E402
from tests.test_purchase_reservation_runtime_20261114 import (  # noqa: E402,F401
    source_scene, _RealModelNamespace, _txn, _http_call)
from tests.test_pending_input_ulp_source_20261114 import SCENARIOS  # noqa: E402


@pytest.mark.parametrize('case_name,specification',SCENARIOS,ids=[name for name,_ in SCENARIOS])
def test_real_pending_input_and_ulp(source_scene,case_name,specification):
    client,a,b=source_scene
    w.set_system_setting('purchase_receipt_strict_order','1')
    w.db.session.commit()
    specimen=unittest.TestCase()
    specimen.client=client
    specimen.a=a
    specimen.b=b
    specimen.user=w.User.query.filter_by(username='synthetic-sources').one()
    specimen.material=w.Material(code='SYN-INPUT-ULP',name='合成输入尾差物料',stock=0)
    w.db.session.add(specimen.material)
    w.db.session.commit()
    specimen.http_paths=[]
    specimen.txn=types.MethodType(_txn,specimen)
    specimen.pending_call=types.MethodType(_http_call,specimen)
    namespace={'ns':_RealModelNamespace(),'db':w.db,'math':math,'event':event}
    helpers=[node for node in ast.parse(HELPERS).body
             if isinstance(node,ast.FunctionDef) and node.name!='pending_call']
    assert {node.name for node in helpers}=={'pending','pending_state'}
    cases=ast.parse(specification).body
    assert len(cases)==1 and isinstance(cases[0],ast.FunctionDef)
    exec(compile(ast.Module(body=[*helpers,*cases],type_ignores=[]),
        '<real-pending-input-ulp-http:'+case_name+'>','exec'),namespace)
    for node in helpers:
        setattr(specimen,node.name,types.MethodType(namespace[node.name],specimen))
    assert specimen.pending_call.__func__ is _http_call
    namespace[cases[0].name](specimen)
    assert specimen.http_paths==['/in_order/item/update']
