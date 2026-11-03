"""Locate actual module-level controlled startup dispatches, never strings."""
import ast

def startup_dispatch_positions(source):
    positions={}
    for node in ast.parse(source).body:
        if not (isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)):
            continue
        call=node.value
        if not (isinstance(call.func,ast.Name) and call.func.id=='_run_startup_db_maintenance'):
            continue
        if len(call.args)!=1 or call.keywords or not isinstance(call.args[0],ast.Name):
            raise ValueError('Unexpected startup maintenance dispatch shape')
        name=call.args[0].id
        if name in positions:
            raise ValueError('Duplicate startup maintenance dispatch: '+name)
        positions[name]=node.lineno
    return positions
