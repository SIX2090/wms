package com.factory.wms

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStoreFile
import androidx.test.core.app.ApplicationProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.io.Closeable
import java.lang.reflect.Field
import kotlinx.coroutines.*
import org.junit.rules.ExternalResource

/** Reset only the delegate cache; every test that uses it must separately own and close its store. */
object DataStoreTestReset {
    private fun slot(): Pair<Any, Field> {
        val facade = Class.forName("com.factory.wms.data.repository.WmsRepositoryKt")
        val delegate = facade.getDeclaredField("dataStore\$delegate").apply { isAccessible = true }.get(null)
        val field = sequenceOf("INSTANCE", "dataStore").mapNotNull { name ->
            runCatching { delegate.javaClass.getDeclaredField(name).apply { isAccessible = true } }.getOrNull()
        }.firstOrNull() ?: error("PreferenceDataStoreSingletonDelegate 缓存字段未找到（androidx 结构变化？）")
        return delegate to field
    }

    fun resetWmsSettingsDataStore() {
        runCatching {
            val (delegate, field) = slot()
            val old = field.get(delegate)
            field.set(delegate, null)
            println("[DataStoreTestReset] 已复位委托单例（旧实例: $old）")
        }.onFailure {
            println("[DataStoreTestReset] 反射复位失败: ${it.javaClass.simpleName}: ${it.message}")
        }
    }

    internal fun bindOwned(store: DataStore<Preferences>): () -> Unit {
        val (delegate, field) = slot()
        check(field.get(delegate) == null) { "DataStore fixture must reset before binding its own store" }
        field.set(delegate, store)
        return { if (field.get(delegate) === store) field.set(delegate, null) }
    }
}

/** Real PreferenceDataStore, fixed sandbox file and an actor whose lifetime ends before sandbox cleanup. */
internal class OwnedWmsSettingsDataStore(context: Context) : Closeable {
    private val job = SupervisorJob()
    private val scope = CoroutineScope(job + Dispatchers.IO)
    private val file = context.applicationContext.preferencesDataStoreFile("wms_settings").canonicalFile
    val store: DataStore<Preferences> = PreferenceDataStoreFactory.create(scope = scope, produceFile = { file })
    private val unbind = DataStoreTestReset.bindOwned(store)
    private var closed = false
    override fun close() {
        if (closed) return
        closed = true
        job.cancel()
        runBlocking { job.join() }
        unbind()
    }
}

/** Outermost JUnit resource: close after activity/Compose/ViewModel teardown, before Robolectric deletes files. */
class WmsSettingsDataStoreRule : ExternalResource() {
    private var owner: OwnedWmsSettingsDataStore? = null
    override fun before() {
        DataStoreTestReset.resetWmsSettingsDataStore()
        owner = OwnedWmsSettingsDataStore(ApplicationProvider.getApplicationContext())
    }
    override fun after() { owner?.close(); owner = null }
}

/** App-scoped pending writes outlive individual ViewModels; drain before closing the test store. */
internal fun drainPendingQuantityDraftWrites(drainMain: () -> Unit) {
    val deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(10)
    while (com.factory.wms.ui.viewmodel.scan.hasPendingQuantityDraftWrites() && System.nanoTime() < deadline) {
        drainMain()
        Thread.sleep(1)
    }
    check(!com.factory.wms.ui.viewmodel.scan.hasPendingQuantityDraftWrites()) {
        "Quantity draft writes did not finish before isolated DataStore closed"
    }
}

/** Raw ViewModels have no owner to clear them. Finish their Main callbacks before closing the store. */
internal fun closeWmsTestViewModels(
    models: Iterable<ViewModel>,
    drainMain: () -> Unit = { org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle() }
) {
    val jobs = models.mapNotNull { it.viewModelScope.coroutineContext[Job] }
    jobs.forEach { it.cancel() }
    val deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(10)
    while (jobs.any { !it.isCompleted } && System.nanoTime() < deadline) {
        drainMain()
        Thread.sleep(1)
    }
    check(jobs.all { it.isCompleted }) { "ViewModel scopes did not finish before their DataStore fixture closed" }
    drainPendingQuantityDraftWrites(drainMain)
}
