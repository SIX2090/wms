# -*- coding: utf-8 -*-
"""审查 app.py 拆分后遗症：扫描 app/routes/ 各模块函数体内引用的名字，
是否已在模块级 import 或函数级 from app import (...) 延迟导入中引入。
输出疑似漏导入清单（名字在 app.py 中确实存在但未在本模块可见）。"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
ROUTES = APP_DIR / "routes"

# 常见内置 + 模块内常用别名，避免误报
BUILTINS = set(dir(__builtins__)) if hasattr(__builtins__, "__dict__") else set(dir(__builtins__))
BUILTINS |= {
    "app", "request", "session", "g", "redirect", "url_for", "render_template",
    "jsonify", "flash", "abort", "Response", "make_response", "send_file",
    "send_from_directory", "current_app", "request", "Blueprint", "flask",
    "db", "os", "sys", "io", "re", "json", "time", "datetime", "date",
    "timedelta", "hashlib", "secrets", "uuid", "base64", "csv", "openpyxl",
    "logging", "traceback", "sqlalchemy", "text", "desc", "asc", "func", "or_",
    "and_", "not_", "in_", "select", "update", "delete", "Alias", "hybrid",
    "wtforms", "StringField", "FloatField", "IntegerField", "SubmitField",
    "SelectField", "BooleanField", "DecimalField", "TextAreaField", "PasswordField",
    "login_required", "csrf_exempt", "require_role", "api_required", "login_manager",
    "itext", "wraps", "partial", "namedtuple", "defaultdict", "OrderedDict",
    "Any", "Optional", "Dict", "List", "Tuple", "Set", "Union", "Path", "Literal",
    "BaseModel", "Field", "validator", "ValidationError", "constants",
}

MODULE_LEVEL_IMPORTS = {}  # module_path -> set(names)


def module_visible_names(module_path):
    """解析模块的顶层 import 名（含 from x import y 的 y，含 import x.y as z 的 z）。"""
    if module_path in MODULE_LEVEL_IMPORTS:
        return MODULE_LEVEL_IMPORTS[module_path]
    names = set()
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except Exception:
        MODULE_LEVEL_IMPORTS[module_path] = names
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
    MODULE_LEVEL_IMPORTS[module_path] = names
    return names


def app_defined_names():
    """app.py 顶层定义的名字（函数/类/常量/变量），用于判断是否为 app 级名字。"""
    names = set()
    try:
        tree = ast.parse((APP_DIR / "app.py").read_text(encoding="utf-8"))
    except Exception:
        return names
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def func_imported_names(func_node):
    """函数体内出现的 from app import (...) / import... 语句引入的名字。"""
    names = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
    return names


def suspicious_names(func_node, module_visible, app_names):
    """函数体内直接引用、但不可见也未在 app.py 顶层的名字。"""
    used = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            pass  # obj.attr —— obj 已被 Name 节点覆盖
    func_imported = func_imported_names(func_node)
    func_locals = ({a.arg for a in func_node.args.args}
                   | {a.arg for a in func_node.args.kwonlyargs}
                   | {a.arg for a in func_node.args.posonlyargs}
                   | ({"..."}
                      if func_node.args.vararg else set())
                   | ({"..."} if func_node.args.kwarg else set()))
    # 函数内局部赋值名
    for node in ast.walk(func_node):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for t in node.targets:
                if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
                    func_locals.add(t.id)
        elif isinstance(node, (ast.For, )):
            if isinstance(node.target, ast.Name):
                func_locals.add(node.target.id)
        elif isinstance(node, ast.FunctionDef):
            func_locals.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            func_locals.add(node.name)
        elif isinstance(node, ast.withitem):
            pass
        elif isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name):
                    func_locals.add(item.optional_vars.id)
    # comprehension 变量
    for node in ast.walk(func_node):
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for gen in node.generators:
                if isinstance(gen.target, ast.Name):
                    func_locals.add(gen.target.id)
                for g in gen.targets if hasattr(gen, "targets") else []:
                    if isinstance(g, ast.Name):
                        func_locals.add(g.id)
    visible = module_visible | func_imported | func_locals | BUILTINS
    # 只保留"app.py 顶层确实定义过"的名字，作为高置信漏导候选
    maybe_missing = used - visible
    return {n for n in maybe_missing if n in app_names}


def main():
    app_names = app_defined_names()
    print(f"[INFO] app.py 顶层定义名数量: {len(app_names)}")
    findings = []
    for mf in sorted(ROUTES.glob("*.py")):
        if mf.name == "__init__.py":
            continue
        try:
            tree = ast.parse(mf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[PARSE-ERR] {mf.name}: {e}")
            continue
        module_visible = module_visible_names(mf)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # 只分析路由注册函数内部（register_xxx_routes 里的函数）
            suspicious = suspicious_names(node, module_visible, app_names)
            for n in sorted(suspicious):
                findings.append((mf.name, node.name, n))

    if not findings:
        print("\n[RESULT] 未发现漏导入（引用 app.py 顶层名字但本函数/模块未导入）")
        return
    print(f"\n[RESULT] 发现 {len(findings)} 处疑似漏导入：")
    for fname, func, name in findings:
        print(f"  {fname:<28} {func:<40} -> 缺 {name}")


if __name__ == "__main__":
    sys.exit(main())