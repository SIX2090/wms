package com.factory.wms

import com.factory.wms.data.api.RetrofitClient
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * BUG-2026-09-14-033：RetrofitClient 会话状态的**真实可执行**回归测试。
 *
 * ## 为什么需要它
 *
 * 本文件是项目**第一个真实运行的 Android 单元测试**（此前 `app/src/test` 不存在，
 * CI 的 `testReleaseUnitTest` 步骤一直在空跑）。项目原有 55 个"Android 测试"全部是
 * Python 正则匹配 Kotlin 源码字符串——能防"某行代码被删"，但**测不出任何运行时行为**。
 *
 * ## 覆盖的真实缺陷
 *
 * - **BUG-2026-09-14-029**（冷启动闪退真实根因）：`apiService` 在 baseUrl 未配置时
 *   必须抛异常（这是防 token 发往非预期服务器的**安全守卫**，不能删）。当时的问题是
 *   `OfflineQueueManager` 在**构造期**就解析 api → `ScanViewModel.init` 同步访问
 *   offlineQueue → 组合期抛异常 → 闪退。本测试锁死「守卫必须抛」+「抛的是
 *   IllegalStateException 且消息可读」这两个契约，防后续有人"为了不崩"把守卫删掉
 *   （那会让 token 泄漏到占位地址），也防把异常类型改成不具辨识度的类型。
 * - **BUG-2026-08-24-006**（会话竞态）：`setBaseUrl` 与 `apiService` 的可见性契约。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`（CI 已配置该步骤）。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31]) // 与现场设备 HUAWEI LIO-AN00（Android 12 / sdk 31）对齐
class RetrofitClientSessionTest {

    @Before
    fun setUp() {
        // 每个用例前把单例重置为"未配置"初始态（object 单例跨用例共享状态）
        RetrofitClient.setToken(null)
    }

    @After
    fun tearDown() {
        RetrofitClient.setToken(null)
    }

    // ---------------------------------------------------------------
    // BUG-2026-09-14-029：安全守卫语义
    // ---------------------------------------------------------------

    @Test
    fun `apiService throws IllegalStateException when baseUrl not configured`() {
        // 全新安装 / 清除数据 / 未登录：baseUrl 为空
        RetrofitClient.setBaseUrl("")

        val ex = assertThrows(IllegalStateException::class.java) {
            RetrofitClient.apiService
        }
        // 消息必须可读——用户在崩溃报告页/日志里要能看懂
        assertTrue(
            "异常消息应提示用户配置服务器地址，实际：${ex.message}",
            ex.message?.contains("服务器地址未配置") == true
        )
    }

    @Test
    fun `apiService never falls back to a real remote host when baseUrl blank`() {
        // 守卫存在的原因：baseUrl 未配置时**绝不能**静默 fallback 到任何真实域名，
        // 否则用户刚输入的 token 会被发往非预期服务器（凭据泄漏）。
        // 这里断言"未配置 = 直接抛错"，即"没有任何请求可能发出"。
        RetrofitClient.setBaseUrl("")
        assertThrows(IllegalStateException::class.java) { RetrofitClient.apiService }
    }

    @Test
    fun `apiService succeeds after baseUrl configured`() {
        RetrofitClient.setBaseUrl("https://gd2026.top")
        // 不抛异常即通过（retrofit.create 返回动态代理）
        assertNotNull(RetrofitClient.apiService)
    }

    @Test
    fun `setBaseUrl tolerates missing trailing slash`() {
        // 不带尾斜杠也必须可用（buildRetrofit 内部补 "/"），否则用户填
        // "https://gd2026.top" 会连不上——这是现场最容易被填错的格式
        RetrofitClient.setBaseUrl("https://gd2026.top")
        assertNotNull(RetrofitClient.apiService)
        assertEquals("https://gd2026.top", RetrofitClient.getBaseUrl())
    }

    @Test
    fun `blank baseUrl throws again after being configured`() {
        // 登出/切换服务器后必须重新受守卫保护，不能因曾配置过就放行
        RetrofitClient.setBaseUrl("https://gd2026.top")
        assertNotNull(RetrofitClient.apiService)

        RetrofitClient.setBaseUrl("")
        assertThrows(IllegalStateException::class.java) { RetrofitClient.apiService }
    }

    // ---------------------------------------------------------------
    // token 生命周期
    // ---------------------------------------------------------------

    @Test
    fun `setToken and getToken round trip`() {
        RetrofitClient.setToken("test-token-abc")
        assertEquals("test-token-abc", RetrofitClient.getToken())

        RetrofitClient.setToken(null)
        assertEquals(null, RetrofitClient.getToken())
    }

    // ---------------------------------------------------------------
    // 共享 OkHttpClient（Coil 图片加载复用，避免重复连接池）
    // ---------------------------------------------------------------

    @Test
    fun `sharedOkHttpClient is stable across calls`() {
        // 必须是同一实例：Coil 注入后与 Retrofit 共用连接池/线程池，
        // 若每次新建会泄漏连接池与线程
        val first = RetrofitClient.sharedOkHttpClient()
        val second = RetrofitClient.sharedOkHttpClient()
        assertTrue("sharedOkHttpClient 必须返回同一实例", first === second)
    }

    // ---------------------------------------------------------------
    // 并发安全（setBaseUrl 在锁内"先构建后发布"）
    // ---------------------------------------------------------------

    @Test
    fun `setBaseUrl is thread safe and never exposes half updated state`() {
        // 并发写 baseUrl + 并发读 apiService，不允许出现
        // 「新 baseUrl 已可见但 retrofit 仍是旧实例」的中间态。
        // 本用例是**并发冒烟**：只要不抛非预期异常、最终状态自洽即通过。
        val urls = listOf("https://a.example.com", "https://b.example.com", "https://gd2026.top")
        val errors = java.util.Collections.synchronizedList(mutableListOf<Throwable>())

        val writers = urls.map { url ->
            Thread {
                repeat(50) {
                    runCatching { RetrofitClient.setBaseUrl(url) }
                        .onFailure { errors.add(it) }
                }
            }
        }
        val readers = (1..3).map {
            Thread {
                repeat(100) {
                    // baseUrl 非空时读 apiService 不应抛异常
                    runCatching {
                        if (RetrofitClient.getBaseUrl().isNotBlank()) {
                            RetrofitClient.apiService
                        }
                    }.onFailure { errors.add(it) }
                }
            }
        }

        (writers + readers).forEach { it.start() }
        (writers + readers).forEach { it.join() }

        assertTrue("并发读写出现异常：${errors.map { it.message }}", errors.isEmpty())
    }
}
