"""A07/A11 route behavior. Extracted functions run locally without application import;
real application cases run only under the repository's owned synthetic runtime.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from flask import Flask, request, jsonify
import pytest

ROOT = Path(__file__).resolve().parents[1]


class MaterialWarehouseContractTest(unittest.TestCase):
    def invoke(self, function, warehouse):
        source = ROOT / 'app/app.py'
        node = next(n for n in ast.parse(source.read_text(encoding='utf-8-sig')).body
                    if isinstance(n, ast.FunctionDef) and n.name == function)
        node.decorator_list = []
        material = SimpleNamespace(id=1, code='M001', stock=999)
        class Column:
            def like(self, _): return self
            def asc(self): return self
        class Query:
            def filter(self, *_): return self
            def filter_by(self, **_): return self
            def order_by(self, *_): return self
            def count(self): return 1
            def limit(self, _): return self
            def all(self): return [material]
            def first(self): return material
        def validate(value):
            return (SimpleNamespace(id={'A':1,'B':2}[value],name=value,code=value),None) if value in ('A','B') else (None,'invalid warehouse')
        def payload(item, warehouse=None, **_):
            return {'code':item.code,'stock':{'A':7,'B':13}[warehouse.code] if warehouse else item.stock}
        namespace = dict(request=request,jsonify=jsonify,Material=SimpleNamespace(query=Query(),
            code=Column(),name=Column(),spec=Column(),brand=Column()),db=SimpleNamespace(or_=lambda *_:None),
            material_selectable_filter=lambda _:None,MATERIAL_SEARCH_API_LIMIT=100,
            validate_inventory_warehouse=validate,get_warehouse_stock_quantities=lambda _: {},
            location_management_enabled=lambda:False,api_material_payload=payload,material_scan_code=lambda v:v,
            api_json_error=lambda message,status:(jsonify(status='error',msg=message),status))
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
        app=Flask(__name__)
        query={'code':'M001','kw':'M001'}
        if warehouse is not None: query['warehouse']=warehouse
        with app.test_request_context(query_string=query):
            response=app.make_response(namespace[function]())
            return response.status_code,response.get_json()

    def test_invalid_search_cannot_return_global_stock(self):
        status,body=self.invoke('material_search_api','missing');self.assertEqual(400,status);self.assertNotIn('data',body)
    def test_invalid_info_cannot_return_global_stock(self):
        status,body=self.invoke('material_info_api','missing');self.assertEqual(400,status);self.assertNotIn('data',body)
    def test_valid_search_keeps_warehouse_stock(self):
        self.assertEqual(7,self.invoke('material_search_api','A')[1]['data'][0]['stock'])
        self.assertEqual(13,self.invoke('material_search_api','B')[1]['data'][0]['stock'])
    def test_valid_info_keeps_warehouse_stock(self):
        self.assertEqual(7,self.invoke('material_info_api','A')[1]['data']['stock'])
        self.assertEqual(13,self.invoke('material_info_api','B')[1]['data']['stock'])
    def test_metadata_without_warehouse_remains_compatible(self):
        self.assertEqual(999,self.invoke('material_info_api',None)[1]['data']['stock'])
        self.assertEqual(999,self.invoke('material_search_api',None)[1]['data'][0]['stock'])

    def test_default_protocol_is_explicit_and_retains_active_list_order(self):
        source = ROOT / 'app/routes/native_api.py'
        node = next(n for n in ast.walk(ast.parse(source.read_text(encoding='utf-8-sig')))
                    if isinstance(n, ast.FunctionDef) and n.name == 'native_api_warehouses')
        node.decorator_list = []
        # Bind only the route's imported collaborators; never import the full application.
        node.body = [n for n in node.body if not isinstance(n, ast.ImportFrom)]
        class Column:
            def asc(self): return self
        class Query:
            def filter_by(inner, **filters):
                self.assertEqual({'status':'active'}, filters)
                return inner
            def order_by(self, *_): return self
            def all(self):
                return [SimpleNamespace(id=1,code='A',name='First active',is_default=False),
                        SimpleNamespace(id=2,code='B',name='Configured default',is_default=True)]
        namespace = dict(Warehouse=SimpleNamespace(query=Query(),code=Column(),id=Column()),
                         api_json_success=lambda data:jsonify(status='success',data=data))
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
        with Flask(__name__).test_request_context():
            items = namespace['native_api_warehouses']().get_json()['data']['items']
        self.assertEqual([1,2],[row['id'] for row in items])
        self.assertTrue(all('is_default' in row for row in items))
        self.assertEqual([False,True],[row['is_default'] for row in items])


# Fixture is resolved by pytest only after conftest has verified the isolated runtime.
from tests.test_money_route_synthetic_20261109 import money_case


@pytest.mark.parametrize('endpoint',['/api/material/info','/api/material/search'])
@pytest.mark.parametrize('kind',['missing','disabled','ambiguous'])
def test_real_material_route_rejects_explicit_invalid_warehouse(money_case,endpoint,kind):
    c=money_case;w=c.w
    if kind=='disabled':
        warehouse=w.db.session.get(w.Warehouse,c.wh2);warehouse.status='inactive';raw=warehouse.code
    elif kind=='ambiguous':
        first=w.db.session.get(w.Warehouse,c.wh1);raw=first.code
        # Seed a historical invalid alias in this owned memory DB. Normal ORM writes correctly reject it.
        w.Warehouse.query.filter_by(id=c.wh2).update({'name':raw},synchronize_session=False)
    else:raw='S-NO-SUCH-WAREHOUSE'
    w.db.session.commit()
    result=c.client.get(endpoint,query_string={'code':'B-M','kw':'B-M','warehouse':raw})
    assert result.status_code==400,result.json
    assert 'data' not in result.json or result.json['data'] is None
    assert w.db.session.get(w.Material,c.ids['material']).stock==10


@pytest.mark.parametrize('endpoint',['/api/material/info','/api/material/search'])
def test_real_material_routes_preserve_scoped_and_metadata_protocols(money_case,endpoint):
    c=money_case
    for warehouse in ('S-MONEY-W1','S-MONEY-W2'):
        result=c.client.get(endpoint,query_string={'code':'B-M','kw':'B-M','warehouse':warehouse})
        assert result.status_code==200,result.json
        data=result.json['data'];item=data[0] if isinstance(data,list) else data
        assert item['code']=='B-M' and item['stock']==5
    metadata=c.client.get(endpoint,query_string={'code':'B-M','kw':'B-M'})
    assert metadata.status_code==200,metadata.json
    data=metadata.json['data'];item=data[0] if isinstance(data,list) else data
    assert item['stock']==10


def test_real_warehouse_protocol_names_default_and_excludes_disabled(money_case):
    c=money_case;w=c.w
    w.Warehouse.query.update({'is_default':False})
    second=w.db.session.get(w.Warehouse,c.wh2);second.is_default=True
    w.db.session.commit()
    result=c.client.get('/api/warehouses');assert result.status_code==200,result.json
    items=result.json['data']['items']
    assert all(isinstance(row['is_default'],bool) for row in items)
    assert [row['id'] for row in items if row['is_default']]==[c.wh2]
    second.status='inactive';w.db.session.commit()
    result=c.client.get('/api/warehouses')
    assert c.wh2 not in [row['id'] for row in result.json['data']['items']]
    assert not any(row['is_default'] for row in result.json['data']['items'])
