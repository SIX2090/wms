package com.factory.wms

/**
 * BUG-2026-10-001（M2' 发现）：`by preferencesDataStore` 委托是 **JVM 级单例**，
 * 跨 Robolectric 沙箱（每个 @Test 方法一个环境）复用时 DataStore actor 链会被毒化，
 * 第 4 个方法的 `saveLoginInfo`（dataStore.edit）永久挂起（CI #762 探针实证：
 * 同一时刻独立工厂实例的 edit 正常返回，仅委托单例挂死）。
 *
 * 修复口径：每个测试方法开始前反射清空委托缓存的实例，使下一个访问
 * 用**当前沙箱 filesDir** 新建 DataStore（fresh actor，与探针行为一致）。
 *
 * 反射面（androidx.datastore:datastore-preferences:1.1.1）：
 * - 委托对象：`WmsRepositoryKt.dataStore$delegate`（顶层扩展属性的静态委托字段）
 * - 委托内部缓存字段：`INSTANCE`（旧版本为 `dataStore`，双名兜底）
 * androidx 内部结构升级可能改名——失败时打印告警并跳过（测试会再次挂起从而暴露），
 * 绝不静默吞掉。
 */
object DataStoreTestReset {

    fun resetWmsSettingsDataStore() {
        runCatching {
            val facade = Class.forName("com.factory.wms.data.repository.WmsRepositoryKt")
            val delegateField = facade.getDeclaredField("dataStore\$delegate").apply { isAccessible = true }
            val delegate = delegateField.get(null)
            val cls = delegate.javaClass
            val instanceField = sequenceOf("INSTANCE", "dataStore")
                .mapNotNull { name ->
                    runCatching {
                        cls.getDeclaredField(name).apply { isAccessible = true }
                    }.getOrNull()
                }
                .firstOrNull()
                ?: error("PreferenceDataStoreSingletonDelegate 缓存字段未找到（androidx 结构变化？）")
            val old = instanceField.get(delegate)
            instanceField.set(delegate, null)
            println("[DataStoreTestReset] 已复位委托单例（旧实例: $old）")
        }.onFailure {
            println("[DataStoreTestReset] 反射复位失败: ${it.javaClass.simpleName}: ${it.message}")
        }
    }
}
