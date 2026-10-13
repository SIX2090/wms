# -*- coding: utf-8 -*-
"""守护：测试里的 importlib.reload 不得让 app/db 单例对其它模块永久分叉。

## 事故背景

CI unit-tests-shard-1 长期随机红，且**每次红的文件都不一样**：

    第 1 次：test_ai_schema_meta_p1_001 / test_inv_batch_001b_check_freeze_upsert
    第 2 次：test_ai_schema_meta_p1_001 / test_inventory_alert_two_band_unified
             / test_auto_migrate_db_path

症状跨了两类完全不同的断言——「登录返回 401」「改config 不生效」——但根因是同一个。

tests/test_f3_3_schema_diff.py 的 app_module fixture 里有::

    mod = importlib.reload(app_mod)

reload 会重新执行 app/app.py，末尾的 ``app = Flask(__name__)`` 于是产出一个
**全新的 Flask 实例**。其它测试模块在导入期就``from app import app`` 把旧实例
绑成了模块级常量（test_auto_migrate_db_path.py 的 ``flask_app`` 即是）。reload
之后：

    测试改的是旧实例的 config
    被测代码（_resolve_sqlite_db_path）读的是新实例的 config
    → 改配置不生效，断言恒假

更隐蔽的是 401 那类失败：内存库挂在 db 对象上，单例一换，测试 seed 的数据
写进了 A 库，请求却打到 B 库，于是「用户不存在」。

红哪个文件取决于 xdist --dist loadfile 把哪些文件分到同一 worker，因此表现为
**间歇性、且失败集合漂移**——这是它长期没被定位的直接原因。

## 本测试锁定的约束

凡在测试里reload app 模块，fixture 退出时必须把 ``app_mod.app`` 与
``app_mod.db`` 还原成 reload 之前的对象。单例只允许在fixture 存续期间被替换。
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def _reload_targets() -> list[Path]:
    """找出所有对 **app 模块**（持有 app/db 单例）做 importlib.reload 的测试文件。

    只 reload ``startup_check`` 这类每次现取依赖的模块不在此列——它不持有单例。
    """
    hits = []
    for path in sorted(TESTS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "reload"):
                continue
            tgt = node.args[0] if node.args else None
            name = getattr(tgt, "id", None) or getattr(tgt, "attr", None)
            if name in {"app", "app_mod", "app_module"}:
                hits.append(path)
                break
    return hits


class TestNoAppSingletonFork:
    def test_reload_sites_exist(self):
        """反向断言：确实存在 reload 站点。

        若将来没人再 reload app，本测试的其它断言会**空跑通过**——那是假绿。
        这里先把站点钉住，使「约束失效」必然表现为可读的失败而非静默。
        """
        sites = _reload_targets()
        assert sites, (
            "未找到任何 importlib.reload(app) 的测试站点。若确实已全部移除，"
            "请连同本测试类一并删除，不要留着空转。"
        )

    @pytest.mark.parametrize(
        "path",
        _reload_targets(),
        ids=lambda p: p.name,
    )
    def test_reload_restores_app_singleton(self, path: Path):
        """reload app 模块的 fixture 必须在 finally 里还原 app / db 单例。

        只约束 reload 目标是 **app** 的函数。``startup_check`` 之类的 reload
        不持有 app 单例（它每次现取），不属本约束范围。
        """
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)

        offenders: list[str] = []
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # 本函数是否 reload 了 app 模块（只认 app / app_mod / app_module）
            reloads_app = False
            for n in ast.walk(fn):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "reload"
                ):
                    tgt = n.args[0] if n.args else None
                    name = getattr(tgt, "id", None) or getattr(tgt, "attr", None)
                    if name in {"app", "app_mod", "app_module"}:
                        reloads_app = True
                        break
            if not reloads_app:
                continue

            # 收集 ``<recv>.app = ...`` / ``<recv>.db = ...`` 形式的还原动作
            restores: set[str] = set()
            has_finally = False
            for node in ast.walk(fn):
                if isinstance(node, ast.Try) and node.finalbody:
                    has_finally = True
                if not isinstance(node, ast.Assign):
                    continue
                for tgt in node.targets:
                    if isinstance(tgt, ast.Attribute) and tgt.attr in {"app", "db"}:
                        restores.add(tgt.attr)

            if not restores:
                offenders.append(f"{path.name}:{fn.name} reload 了 app 但未还原单例")
                continue
            if not has_finally:
                offenders.append(
                    f"{path.name}:{fn.name} 还原单例但不在 finally 中，异常路径会漏还原"
                )
                continue
            # 只硬性要求还原 app。db 目前来自 `from db import db`（另一个模块的
            # 单例），reload app 不会重建它——还原 db 是防御性写法，不强制，
            # 以免判据逼出无意义的样板代码。
            if "app" not in restores:
                offenders.append(
                    f"{path.name}:{fn.name} 未还原 app 单例"
                )

        assert not offenders, (
            "reload 会换掉 app/db 单例，测试模块导入期绑定的旧引用将永久失效，"
            "表现为 xdist 下随机失败且失败集合漂移（401 / 改配置不生效）。"
            f"请在 finally 中还原：{offenders}"
        )

    def test_singleton_restoration_actually_holds(self):
        """行为级验证：跑完 reload fixture 后，单例必须还是原来那个。

        前面的断言是静态检查（读 AST），本条是真正的行为验证——静态检查可能被
        等价写法绕过，行为不会。

        这里**不允许 skip**：fixture 结构一旦变了，本条就该报错提醒同步更新，
        而不是静默跳过——静默跳过等于把唯一的动态防线变成空转。
        """
        import app as app_mod

        before_app, before_db = app_mod.app, app_mod.db

        # 手工驱动 fixture 的生成器：
        #   第一次 send 拿到 yield 出的 mod（此时 reload 已发生，app 已换新）
        #   第二次 send(None) 让它跑完 finally 并 StopIteration
        gen = _drive_app_module_fixture()
        reload_mod = next(gen)
        # 此刻 finally 尚未执行，reload_mod.app 必须已经是**新**实例——
        # 这证明 reload 确实换掉了单例，也就是本次事故的成因本身。
        assert reload_mod.app is not before_app, (
            "反向校验失效：reload 未产生新的 Flask 实例，说明本测试的前提不成立"
        )
        # 注意：db 不参与本断言。app/app.py 里是 `from db import db`，db 是
        # **另一个模块**的单例，reload app 不会重建它（实测 reload 后
        # reload_mod.db is before_db）。fixture 里仍还原 db 属防御性写法——
        # 若将来 app.py 改成自建 SQLAlchemy()，那才会真的换掉。
        assert app_mod.db is before_db, "reload 不应重建 db 单例（它来自 db 模块）"

        with pytest.raises(StopIteration):
            gen.send(None)

        import app as app_after

        assert app_after.app is before_app, (
            "app 单例在 fixture 退出后被换掉了——其它测试模块导入期绑定的 "
            "flask_app 会与 app_mod.app 分叉"
        )
        assert app_after.db is before_db, "db 单例在 fixture 退出后被换掉了"


def _drive_app_module_fixture():
    """手工驱动 test_f3_3_schema_diff 的**真实** app_module fixture，直到 yield。

    直接 import 被测模块（而非复制其 fixture 体）：复制会随被测文件演进而
    悄悄漂移，行为验证就变成了验证一份副本，失去意义。

    被测模块是普通可导入模块（pytest 以 tests.test_f3_3_schema_diff 加载），
    这里用同一模块名导入即可拿到同一个 fixture 对象。
    """
    import importlib
    import sys

    for key, val in (
        ("WMS_BOOTSTRAP_PASSWORD", "admin"),
        ("WMS_DEBUG", "0"),
        ("WMS_SKIP_AUTO_UPDATE", "1"),
        ("WMS_ALLOW_INSECURE_COOKIE", "1"),
    ):
        os.environ.setdefault(key, val)

    if str(TESTS) not in sys.path:
        sys.path.insert(0, str(TESTS))
    import test_f3_3_schema_diff as target

    fn = getattr(target.app_module, "__wrapped__", target.app_module)
    return fn()