#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统配置文件
统一管理所有系统配置参数
"""

import os


def _static_version():
    env_version = os.environ.get('WMS_STATIC_VERSION')
    if env_version:
        return env_version

    base_dir = os.path.dirname(os.path.abspath(__file__))
    version_files = (
        os.path.join(base_dir, 'static', 'css', 'custom.css'),
        os.path.join(base_dir, 'static', 'js', 'app.js'),
    )
    mtimes = []
    for path in version_files:
        try:
            mtimes.append(int(os.path.getmtime(path)))
        except OSError:
            pass
    return str(max(mtimes)) if mtimes else '1.0.55'

# ==================== 基础配置 ====================
class Config:
    """系统基础配置类"""
    
    # 应用密钥（生产环境必须使用环境变量）
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # 数据库配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "instance", "inventory.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 数据库性能优化
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'check_same_thread': False,
            'timeout': 30,
        },
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大上传 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'xlsx', 'xls', 'pdf'}
    
    # 静态文件缓存（开发模式禁用缓存）
    SEND_FILE_MAX_AGE_DEFAULT = 0  # 开发模式：禁用缓存，修改立即生效

    # 静态资源版本号（用于强制刷新浏览器缓存）
    STATIC_VERSION = _static_version()  # 每次更新JS/CSS时修改此版本号

    # 库存预警/安全库存尚未启用。启用前不在页面展示预警入口和低库存提示。
    INVENTORY_ALERT_ENABLED = os.environ.get('INVENTORY_ALERT_ENABLED', 'false').lower() in ('true', '1', 'yes')

    # AI仓库助手大模型配置。兼容 OpenAI 风格的 /chat/completions 接口；
    # 未配置 API Key 时，系统会自动使用本地规则助手兜底。
    WMS_LLM_ENABLED = os.environ.get('WMS_LLM_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    WMS_LLM_BASE_URL = os.environ.get('WMS_LLM_BASE_URL', 'https://api.openai.com/v1/chat/completions')
    WMS_LLM_API_KEY = os.environ.get('WMS_LLM_API_KEY', '')
    WMS_LLM_MODEL = os.environ.get('WMS_LLM_MODEL', 'gpt-4.1-mini')
    WMS_LLM_TIMEOUT_SECONDS = float(os.environ.get('WMS_LLM_TIMEOUT_SECONDS', '8'))
    WMS_LLM_MAX_TOKENS = int(os.environ.get('WMS_LLM_MAX_TOKENS', '300'))

    # SSL/HTTPS配置
    USE_SSL = False
    SSL_CERT_FILE = os.environ.get('SSL_CERT_FILE', os.path.join(BASE_DIR, 'instance', 'certs', 'server.crt'))
    SSL_KEY_FILE = os.environ.get('SSL_KEY_FILE', os.path.join(BASE_DIR, 'instance', 'certs', 'server.key'))
    
    # 服务器配置
    HOST = '0.0.0.0'
    PORT = 8080
    DEBUG = False  # 生产模式：禁用调试
    
    # 日志配置
    LOG_FOLDER = os.path.join(BASE_DIR, 'logs')
    LOG_FILE = os.path.join(LOG_FOLDER, 'app.log')
    LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # 备份配置
    BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
    AUTO_BACKUP_ENABLED = True
    AUTO_BACKUP_TIME = '02:00'  # 每天凌晨2点自动备份
    BACKUP_RETENTION_DAYS = 30  # 保留30天备份

    # 本机微信助手拉取云端待发送任务的访问令牌
    # 未显式配置时不使用默认弱令牌，由 app.py 启动期生成并持久化到 instance/wechat_helper_token
    WECHAT_HELPER_TOKEN = os.environ.get('WECHAT_HELPER_TOKEN')
    
    # 会话配置
    PERMANENT_SESSION_LIFETIME = 28800  # 会话有效期8小时
    SESSION_COOKIE_SECURE = False  # Production环境应设为True（使用HTTPS时）
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
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes')
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 静态文件缓存1年
    PERMANENT_SESSION_LIFETIME = 28800  # 会话8小时过期
    
    # 安全头配置
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
    }
    if os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes'):
        SECURITY_HEADERS['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'


# ==================== 测试环境配置 ====================
class TestingConfig(Config):
    """测试环境配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('TEST_SECRET_KEY') or 'wms-testing-only-secret-key'
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # 使用内存数据库


# 配置字典
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}
