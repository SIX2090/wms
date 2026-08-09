package com.factory.wms.data.api

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 401 未授权事件总线。
 *
 * 关键点：用 [AtomicBoolean] 保证"未授权"只触发一次，直到用户重新登录成功后才复位。
 * 否则一旦多个并发请求同时返回 401，拦截器会对每个响应都回调一次，导致
 * NavGraph 重复跳转登录页、AuthViewModel 重复登出，产生 UI 抖动 / 状态混乱。
 */
object AuthEventBus {
    private val _unauthorizedEvents = MutableSharedFlow<Unit>(extraBufferCapacity = 1)

    private val unauthorizedSignaled = AtomicBoolean(false)

    val unauthorizedEvents = _unauthorizedEvents.asSharedFlow()

    fun notifyUnauthorized() {
        // 已经通知过的 401 直接忽略，避免同一令牌失效期间重复消费
        if (unauthorizedSignaled.compareAndSet(false, true)) {
            _unauthorizedEvents.tryEmit(Unit)
        }
    }

    /** 登录成功后复位，允许下一次令牌失效再次触发 401 事件。 */
    fun reset() {
        unauthorizedSignaled.set(false)
    }
}