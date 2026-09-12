package com.factory.wms.util

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.distinctUntilChanged

/**
 * AI-MOB-OFFLINE-01：网络可达性监听。
 *
 * ## 为什么需要它
 *
 * 此前 App 全模块没有任何网络状态感知（无 ConnectivityManager / NetworkCallback）——
 * 提交失败只能靠 `catch (Exception)` 兜底，无法区分"断网"与"服务端出错"，
 * 也无法在**恢复联网的瞬间**自动补传离线队列。本类提供这个信号源。
 *
 * ## 判定标准（关键，避免误判）
 *
 * 只有 `NET_CAPABILITY_INTERNET` + `NET_CAPABILITY_VALIDATED` **同时满足**才算在线：
 * - 只连上 WiFi 但连不到外网（仓库常见：连了内网 AP 但出口断了）时
 *   `VALIDATED` 为 false，此时**必须判为离线**，否则会把请求发出去、卡到超时才发现，
 *   既慢又可能写坏本地状态。
 * - `VALIDATED` 是系统实际探测过连通性的结论，比单纯看连接状态可靠。
 *
 * ## 保守策略
 *
 * 拿不到任何网络时按**离线**处理：宁可暂存（可补传），不可当作在线把数据丢掉。
 * 这是单向安全的选择——离线误判只多存一条、联网即补；在线误判则直接丢数据。
 */
class NetworkMonitor(context: Context) {

    private val connectivityManager =
        context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    private val _isOnline = MutableStateFlow(currentlyOnline())

    /** 当前是否在线（热流，供 ViewModel 直接 collect 驱动 UI 与补传）。 */
    val isOnline: StateFlow<Boolean> = _isOnline.asStateFlow()

    /**
     * 网络可达性变化流：**仅在状态真正翻转时**发射（distinctUntilChanged），
     * 避免系统频繁回调导致补传被重复触发。
     */
    val onlineChanges: Flow<Boolean> = callbackFlow {
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                val online = currentlyOnline()
                _isOnline.value = online
                trySend(online)
            }

            override fun onLost(network: Network) {
                val online = currentlyOnline()
                _isOnline.value = online
                trySend(online)
            }

            override fun onCapabilitiesChanged(
                network: Network,
                networkCapabilities: NetworkCapabilities
            ) {
                val online = networkCapabilities.hasCapability(
                    NetworkCapabilities.NET_CAPABILITY_INTERNET
                ) && networkCapabilities.hasCapability(
                    NetworkCapabilities.NET_CAPABILITY_VALIDATED
                )
                _isOnline.value = online
                trySend(online)
            }
        }

        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()

        // 注册可能抛 SecurityException（缺 ACCESS_NETWORK_STATE 权限）：
        // 此时退化为"按当前状态发射一次"，不阻断流程——监听失败不该让 App 崩溃。
        try {
            connectivityManager.registerNetworkCallback(request, callback)
        } catch (e: Exception) {
            trySend(currentlyOnline())
        }

        awaitClose {
            try {
                connectivityManager.unregisterNetworkCallback(callback)
            } catch (e: Exception) {
                // 未注册成功时 unregister 会抛，忽略即可
            }
        }
    }.distinctUntilChanged()

    /**
     * 主动查询当前是否在线（同步，用于补传前的最终确认）。
     *
     * 与 `onlineChanges` 的关系：这个方法是**即时快照**，网络回调有系统延迟，
     * 补传前用它再确认一次可以避免"系统还没回调、但实际已断"的空发。
     */
    fun currentlyOnline(): Boolean {
        return try {
            val network = connectivityManager.activeNetwork ?: return false
            val caps = connectivityManager.getNetworkCapabilities(network) ?: return false
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        } catch (e: Exception) {
            // 查询失败按离线处理（保守：宁可暂存可补传，不当作在线丢数据）
            false
        }
    }

    companion object {
        @Volatile
        private var instance: NetworkMonitor? = null

        /**
         * 单例：网络监听器全局一份即可，多处各建一份会重复注册 NetworkCallback
         * （系统对同进程重复注册虽容忍，但每次注册都占资源且回调倍数触发补传）。
         */
        fun getInstance(context: Context): NetworkMonitor {
            return instance ?: synchronized(this) {
                instance ?: NetworkMonitor(context.applicationContext).also { instance = it }
            }
        }
    }
}
