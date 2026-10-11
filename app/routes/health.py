# 进程级健康检查端点（F1.4 / P0-4 / 审计 §7.4）：register-on-app 模式。
#
# 设计约束（不可削弱）：
# - **免认证**：nginx/外部探活专用，挂登录墙会让探活永远 302，监控形同虚设；
# - **不查库**：数据库抖动时探活不该被拖挂——本端点只回答
#   "Flask 进程还活着吗"，数据库健康是另一层监控的事；
# - 只做进程存活（能响应即证明）+ 廉价的 os.path 级存在性检查。
import os
from datetime import datetime

from flask import jsonify


# no-test:reason=路由注册辅助函数，能力由 tests/test_healthz_endpoint.py 覆盖
def register_health_routes(app):
    @app.route('/healthz')
    def healthz():
        checks = {
            'app': True,
            'instance_dir': os.path.isdir(
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance')),
        }
        healthy = all(checks.values())
        return jsonify({
            'status': 'ok' if healthy else 'degraded',
            'checks': checks,
            'time': datetime.now().isoformat(),
        }), (200 if healthy else 503)
