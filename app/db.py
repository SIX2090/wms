# 数据库实例 - 独立文件避免循环导入
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session


class _NativeRequestSession(Session):
    """Defer inner commits only while this session owns a native replay request."""

    def flush(self, objects=None):
        state = self.info.get('native_request')
        if state and not state['atomic'] and (self.new or self.dirty or self.deleted):
            from services.native_request_idempotency import activate_native_business_transaction
            activate_native_business_transaction()
        return super().flush(objects)

    def commit(self):
        state = self.info.get('native_request')
        if state and not state['finalizing']:
            from services.native_request_idempotency import activate_native_business_transaction
            activate_native_business_transaction()
            self.flush()
            return
        return super().commit()

    def rollback(self):
        state = self.info.get('native_request')
        if state and state['atomic']:
            state['invalid'] = True
        return super().rollback()


db = SQLAlchemy(session_options={'class_': _NativeRequestSession})
