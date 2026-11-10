"""Offline regression for uncertain print-alert deliveries.

不导入 WMS 应用：`sys.modules['app']` 被替换成最小替身，网络与子进程一律拒绝。
但保留**真实 SQLite 临时文件库**——发送结果必须由 `services.print_alert_reserve`
的短事务落库（`reserve_alert` / `attach_alert_image` / `finish_alert`），纯内存
替身无法证明状态机语义。sqlite 连接被限制在本次临时目录内，不可能碰到真实库。
"""
import ast
import socket
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import Column, Date, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
SOURCE = APP_DIR / 'routes' / 'print_alerts.py'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def refuse(*_args, **_kwargs):
    raise AssertionError('network, database and subprocess are forbidden')


Base = declarative_base()


class Log(Base):
    """与 `models.wechat.WechatShareLog` 同表同列的独立映射（不导入应用）。"""
    __tablename__ = 'wechat_share_log'

    id = Column(Integer, primary_key=True)
    config_id = Column(Integer)
    module_key = Column(String(50), nullable=False)
    order_id = Column(Integer, nullable=False)
    order_no = Column(String(80))
    share_date = Column(Date, default=date.today)
    trigger_type = Column(String(30), default='manual')
    status = Column(String(30), default='pending')
    message = Column(String(500))
    image_path = Column(String(500))
    image_size = Column(Integer, default=0)
    receiver_name = Column(String(100))
    receiver_wechat_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    sent_at = Column(DateTime)


class PrintAlertUncertainSend(unittest.TestCase):
    def setUp(self):
        self.stack = []
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmpdir = Path(tmp.name)

        self.engine = create_engine('sqlite:///' + (tmpdir / 'alerts.db').as_posix())
        Base.metadata.create_all(self.engine)
        self.image = tmpdir / 'alert.png'
        self.image.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')

        # 离线红线保持：只允许连接本用例临时目录内的 sqlite 文件。
        real_connect = sqlite3.connect

        def guarded_connect(database=':memory:', *args, **kwargs):
            target = str(database)
            if target != ':memory:' and not target.startswith(str(tmpdir)):
                raise AssertionError(f'禁止连接临时目录之外的数据库: {target}')
            return real_connect(database, *args, **kwargs)

        for target, name, replacement in (
                (socket.socket, 'connect', refuse),
                (socket.socket, 'connect_ex', refuse),
                (socket, 'getaddrinfo', refuse),
                (subprocess, 'Popen', refuse),
                (sqlite3, 'connect', guarded_connect)):
            guard = patch.object(target, name, replacement)
            guard.start()
            self.addCleanup(guard.stop)

        self.config = types.SimpleNamespace(id=1, receiver_name='synthetic', receiver_wechat_id='')
        self.fake_app = types.ModuleType('app')
        self.fake_app.WechatShareLog = Log
        self.fake_app.get_system_setting_bool = lambda *_args: True
        self.fake_app.get_system_setting_int = lambda *_args: 10
        self.fake_app._wechat_share_default_config = lambda: self.config
        self.tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        func = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'push_print_alert_wechat')
        namespace = {
            'db': types.SimpleNamespace(engine=self.engine),
            'datetime': datetime, 'date': date, 'timedelta': timedelta,
            '_render_alert_image': lambda _notification: str(self.image),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[])),
                     '<synthetic-alert>', 'exec'), namespace)
        self.push = namespace['push_print_alert_wechat']

    def run_case(self, status, code, message):
        self.fake_app._wechat_share_send_image = lambda *_args: (status, code, message)
        notification = types.SimpleNamespace(id=101, title='synthetic alert')
        with patch.dict(sys.modules, {'app': self.fake_app}):
            self.assertTrue(self.push(notification))
        with Session(self.engine) as session:
            logs = session.query(Log).all()
        self.assertEqual(len(logs), 1)
        return logs[0]

    def test_connection_lost_after_possible_delivery_is_not_requeued(self):
        log = self.run_case('failed', 'helper_offline', '发送结果待核对；不自动重试')
        self.assertEqual(log.status, 'uncertain')
        self.assertIn('核对', log.message)
        self.assertIn('helper_offline', log.message)

    def test_confirmed_preflight_error_still_queues(self):
        # 确定请求尚未发出的配置错误 → 交助手轮询（queued_v2 即待拉取队列）。
        log = self.run_case('failed', 'invalid_helper_url', 'invalid')
        self.assertEqual(log.status, 'queued_v2')

    def test_missing_helper_already_returns_pending(self):
        # 助手未配置属于「确定未发出」，同样进轮询队列而不是留在 pending。
        log = self.run_case('pending', 'helper_not_configured', '待发送')
        self.assertEqual(log.status, 'queued_v2')

    def test_timeout_needs_manual_confirmation(self):
        log = self.run_case('failed', 'helper_timeout', '请核对')
        self.assertEqual(log.status, 'uncertain')
        self.assertIn('核对', log.message)

    def test_helper_reported_error_needs_manual_confirmation(self):
        log = self.run_case('failed', 'send_key_failed', '按键失败')
        self.assertEqual(log.status, 'uncertain')
        self.assertIn('核对', log.message)
        self.assertIn('send_key_failed', log.message)

    def test_preflight_auth_failure_remains_failed(self):
        log = self.run_case('failed', 'token_not_configured', '未配置')
        self.assertEqual(log.status, 'failed')

    def test_sent_stays_sent(self):
        log = self.run_case('sent', 'ok', '已发送')
        self.assertEqual(log.status, 'sent')
        self.assertIsNotNone(log.sent_at)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PrintAlertUncertainSend)
    if suite.countTestCases() != 7:
        raise SystemExit('synthetic test list is incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
