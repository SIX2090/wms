import os
from datetime import timedelta

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
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'xlsx', 'xls', 'csv', 'doc', 'docx'}
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE') or 'logs/app.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    
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
    
    # 自动备份
    AUTO_BACKUP_ENABLED = os.environ.get('AUTO_BACKUP_ENABLED', 'true').lower() in ('true', '1', 'yes')
    AUTO_BACKUP_TIME = '02:00'  # 每天凌晨2点自动备份
    BACKUP_RETENTION_DAYS = 30  # 保留30天备份

    # 本机微信助手拉取云端待发送任务的访问令牌
    # 未显式配置时不使用默认弱令牌，由 app.py 启动期生成并持久化到 instance/wechat_helper_token
    WECHAT_HELPER_TOKEN = os.environ.get('WECHAT_HELPER_TOKEN')
    
    # 会话配置
    PERMANENT_SESSION_LIFETIME = 28800  # 会话有效期8小时
    WTF_CSRF_TIME_LIMIT = 28800  # CSRF令牌有效期与会话一致，避免页面停留过久导致操作失败
    SESSION_COOKIE_SECURE = True  # HTTPS环境下Cookie仅通过加密连接传输（AI-SEC-F01）
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


# ==================== 开发环境配置 ====================
class DevelopmentConfig(Config):
    """开发环境配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('DEV_SECRET_KEY')
    DEBUG = True
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'false').lower() in ('true', '1', 'yes')  # 按需打印 SQL


# ==================== 生产环境配置 ====================
class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() in ('true', '1', 'yes')
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 静态文件缓存1年
    PERMANENT_SESSION_LIFETIME = 28800  # 会话8小时过期
    
    # 安全头配置
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
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
