import os
from datetime import timedelta


def _env_int(name, default, minimum=None, maximum=None):
    """读取整数环境变量，非法/越界时回退默认值而不是在 import 期抛异常。

    AUDIT-FULL-20261016-001-F09-F06（原 A16）：旧实现直接 int(os.environ.get(...))，
    空串/非数字会让 import config 抛 ValueError，调度器里的"回退 30 天"永远执行不到；
    而 config 是 app.py 启动期第一批 import，等于服务直接起不来（或测试收集失败）。
    """
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == '':
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and value < minimum:
        return default
    if maximum is not None and value > maximum:
        return default
    return value


# ==================== 基础配置 ====================
class Config:
    """基础配置"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DEBUG = False
    TESTING = False
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///inventory.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
    }
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'xlsx', 'xls', 'csv', 'doc', 'docx'}
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    # F3.13：默认日志路径锚定应用目录（绝对路径），避免 nssm 服务等
    # 非仓库根 CWD 启动时把日志写到工作目录下的相对 logs/ 里。
    LOG_FILE = os.environ.get('LOG_FILE') or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'logs', 'app.log')
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    WMS_SLOW_REQUEST_MS = os.environ.get('WMS_SLOW_REQUEST_MS', '500')
    
    # 分页配置
    DEFAULT_PER_PAGE = 20
    MAX_PER_PAGE = 200
    
    # 库存告警阈值
    DEFAULT_STOCK_LOW_THRESHOLD = 10
    DEFAULT_STOCK_HIGH_THRESHOLD = 10000
    
    # 币别配置
    DEFAULT_CURRENCY = 'CNY'
    SUPPORTED_CURRENCIES = ['CNY', 'USD', 'EUR', 'JPY', 'HKD']
    
    # 税率配置
    DEFAULT_TAX_RATE = 0.13  # 默认13%税率
    
    # 缓存配置
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # 自动备份（F1.2：已接入 app/backup_scheduler.py 每日调度，不再是死配置）
    AUTO_BACKUP_ENABLED = os.environ.get('AUTO_BACKUP_ENABLED', 'true').lower() in ('true', '1', 'yes')
    AUTO_BACKUP_TIME = os.environ.get('AUTO_BACKUP_TIME', '02:00')  # 每天凌晨2点自动备份
    BACKUP_RETENTION_DAYS = _env_int('BACKUP_RETENTION_DAYS', 30, minimum=1, maximum=3650)  # 保留30天备份；非法值回退 30
    # 备份目标目录：WMS_BACKUP_DIR 环境变量（默认 C:\wms_backups，见 backup_scheduler.get_backup_dir）

    # 本机微信助手拉取云端待发送任务的访问令牌
    # 未显式配置时不使用默认弱令牌，由 app.py 启动期生成并持久化到 instance/wechat_helper_token
    WECHAT_HELPER_TOKEN = os.environ.get('WECHAT_HELPER_TOKEN')
    
    # 会话配置
    PERMANENT_SESSION_LIFETIME = 28800  # 会话有效期8小时
    # AI-LOGIN-F02：登录"记住我"持久 Cookie 有效期（手机浏览器关掉后仍免登录）。
    # 默认 365 天，每次重新登录自动顺延；环境变量 WMS_REMEMBER_LOGIN_DAYS 可调，设 0 关闭长登录。
    REMEMBER_COOKIE_DURATION = timedelta(days=_env_int('WMS_REMEMBER_LOGIN_DAYS', 365, minimum=0, maximum=3650))
    WTF_CSRF_TIME_LIMIT = 28800  # CSRF 令牌有效期 8 小时（与会话有效期一致，避免用户操作中途令牌过期）
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # 可信代理列表，仅这些 IP 的 X-Forwarded-For 头会被信任
    TRUSTED_PROXIES = [ip.strip() for ip in os.environ.get('TRUSTED_PROXIES', '127.0.0.1,::1').split(',') if ip.strip()]


# ==================== 开发环境配置 ====================
class DevelopmentConfig(Config):
    """开发环境配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('DEV_SECRET_KEY')
    DEBUG = True
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'false').lower() in ('true', '1', 'yes')  # 按需打印 SQL


def _env_flag(name):
    return os.environ.get(name, 'false').lower() in ('true', '1', 'yes')


def validate_production_security_config(environment=None):
    env_name = environment or os.environ.get('FLASK_ENV', 'production')
    if env_name != 'production':
        return
    if _env_flag('WMS_DISABLE_CSRF'):
        raise RuntimeError('CSRF protection cannot be disabled in production')
    # AUDIT-2026-09-13-003 / BUG-2026-09-19-003：生产默认拒绝明文会话 Cookie。
    # 未开启 SESSION_COOKIE_SECURE 时必须显式设置 WMS_ALLOW_INSECURE_COOKIE=1
    # （仅限受信内网 HTTP 部署），否则阻止启动；显式放行后启动期记录高危告警。
    if not _env_flag('SESSION_COOKIE_SECURE') and not _env_flag('WMS_ALLOW_INSECURE_COOKIE'):
        raise RuntimeError(
            'SESSION_COOKIE_SECURE is disabled in production: session cookies would be '
            'transmitted over HTTP in plaintext. Deploy behind HTTPS and set '
            'SESSION_COOKIE_SECURE=true, or explicitly opt in to insecure cookies for a '
            'trusted intranet by setting WMS_ALLOW_INSECURE_COOKIE=1 (high risk). '
            'See AUDIT-2026-09-13-003 / BUG-2026-09-19-003.'
        )


# ==================== 生产环境配置 ====================
class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes')
    WTF_CSRF_ENABLED = True
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 静态文件缓存1年
    PERMANENT_SESSION_LIFETIME = 28800  # 会话8小时过期
    
    # 安全头配置
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        # F2.7 / S9：CSP 从宽松白名单起步（全站大量内联脚本/样式 + 本地托管 CDN 资源，
        # 模板无外部 http(s) 外链）。object-src/base-uri/frame-ancestors 先行收紧，
        # script/style 暂保留 unsafe-inline 以不破坏既有页面；后续可逐步收敛。
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'"
        ),
        # F2.7 / S9：HSTS 仅在 HTTPS 生效（HTTP 响应忽略该头），includeSubDomains
        # 覆盖 www 等子域；生产 nginx 层亦加同名头（见 nginx_wms_server_block.conf）。
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    }


# ==================== 测试环境配置 ====================
class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False  # 测试环境走 HTTP，关闭 Secure 标志避免会话丢失（AI-SEC-F01）
    

# ==================== 配置映射 ====================
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig,
}

def get_config():
    """获取当前环境配置"""
    env = os.environ.get('FLASK_ENV', 'production')
    return config_dict.get(env, config_dict['default'])
