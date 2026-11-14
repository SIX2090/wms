"""Pending numeric/ULP correction: real source/models, guarded new memory only."""
import ast
import os
from pathlib import Path
import subprocess
import sys

CASE=r'''
def test_pending_{name}(self):
    mode={mode!r}
    location_on={location_on}
    quantity=math.nextafter(1.01,float('inf') if {direction!r}=='up' else float('-inf')) if {direction!r}!='exact' else 1.01
    order,row,source=self.pending(quantity,{counter!r},location_on)
    row.price=3.5 if mode in ('price_zero','quantity_change','invalid') else 0
    if mode=='price_ulp':
        row.price=math.nextafter(3.5,float('inf') if {price_direction!r}=='up' else float('-inf'))
    row.amount=7.77
    order.total_amount={head!r}
    db.session.commit()
    before=(row.quantity,row.price,row.amount,order.total_amount,source.received_quantity)
    all_before=self.pending_state()
    form={{'id':row.id,'quantity':1.01,'price':3.5 if mode=='price_ulp' else 0,'remark':'only remark'}}
    if mode=='quantity_change':
        form['quantity']=2
    elif mode=='rounded_equal':
        form['quantity']=1.005
    elif mode=='invalid':
        form['quantity']=2
        form[{field!r}]={invalid_value!r}
    try:
        status,result=self.pending_call('update',order,row,source,form_override=form)
    except Exception as exc:
        self.fail('Actual handler raised '+type(exc).__name__+' instead of returning a business response: '+str(exc))
    if mode=='invalid':
        self.assertEqual(status,400,result)
        self.assertEqual(result['status'],'error',result)
        self.assertEqual(self.pending_state(),all_before)
        self.assertEqual((row.quantity,row.price,row.amount,order.total_amount,source.received_quantity),before)
    else:
        self.assertEqual(status,200,result)
        self.assertEqual(result['status'],'success',result)
        if mode=='price_zero':
            expected=(quantity,0,0,0,{counter!r})
        elif mode=='quantity_change':
            expected=(2,0,0,0,2)
        else:
            expected=before
        self.assertEqual((row.quantity,row.price,row.amount,order.total_amount,source.received_quantity),expected)
        self.assertEqual(row.remark,'only remark')
        self.assertEqual(self.material.stock,20)
        self.assertEqual(ns['StockTransaction'].query.count(),2)
'''


def scenarios():
    result=[]
    def add(name,location_on,mode='metadata',direction='exact',counter=1.01,head=9.99,
            price_direction='exact',field='quantity',invalid_value='not-a-number'):
        result.append((name,CASE.format(name=name,mode=mode,location_on=location_on,direction=direction,
            counter=counter,head=head,price_direction=price_direction,field=field,invalid_value=invalid_value)))
    for location_on in (False,True):
        suffix='_on' if location_on else '_off'
        for direction in ('up','down','exact'):
            for counter in (1.01,1.005):
                for head in (0,9.99):
                    add('q_'+direction+'_'+str(counter).replace('.','p')+'_'+str(head).replace('.','p')+suffix,
                        location_on,direction=direction,counter=counter,head=head)
            add('price_zero_'+direction+suffix,location_on,mode='price_zero',direction=direction,counter=1.005)
        for direction in ('up','down'):
            add('price_ulp_'+direction+suffix,location_on,mode='price_ulp',price_direction=direction,counter=1.005)
        add('rounded_equal'+suffix,location_on,mode='rounded_equal',counter=1.005)
        add('real_quantity_change'+suffix,location_on,mode='quantity_change')
        invalid=[('quantity','not-a-number'),('price','not-a-number'),('quantity','nan'),('price','nan'),
                 ('quantity','inf'),('price','inf'),('quantity','0.004'),('quantity','0'),('quantity','-1'),
                 ('quantity','1e308'),('price','1e308')]
        for index,(field,value) in enumerate(invalid):
            add('invalid_'+str(index)+suffix,location_on,mode='invalid',field=field,invalid_value=value)
    assert len(result)==60 and len({name for name,_ in result})==60
    return result


SCENARIOS=scenarios()


def main():
    path=Path(__file__).with_name('test_purchase_reservation_source_20261114.py')
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    constants={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)}
    template=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    first=next(index for index,node in enumerate(template.body) if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='cases' for target in node.targets))
    last=next(index for index,node in enumerate(template.body[first:],first)
        if isinstance(node,ast.Expr) and ast.unparse(node)=='suite.body.extend(cases)')
    template.body[first:last+1]=ast.parse('cases=ast.parse(ALL_CASES).body\nassert len(cases)==60\nsuite.body.extend(cases)').body
    for node in ast.walk(template):
        if isinstance(node,ast.Assign) and ast.unparse(node.targets[0])=='counts[0].comparators[0]':
            node.value=ast.parse('ast.Constant(value=60)',mode='eval').body
    imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__,**constants,'ALL_CASES':'\n'.join(case for _,case in SCENARIOS)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,template],type_ignores=[])),
        '<guarded-pending-input-ulp-correction>','exec'),namespace)
    namespace['main']()


def test_update_in_order_item_input_ulp_in_guarded_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=150)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
