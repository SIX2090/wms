package com.factory.wms

import android.app.Application
import androidx.room.Room
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.local.AppDatabase
import com.factory.wms.data.repository.OfflineQueueManager
import java.io.Closeable
import java.util.concurrent.Executor
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.emptyFlow

/** Private real stores and workers. close waits for all owned I/O before the sandbox can disappear. */
internal class NativeAuditLocalStores(application: Application) : Closeable {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val settings = OwnedWmsSettingsDataStore(application)
    @Volatile var online = false
    val database = Room.inMemoryDatabaseBuilder(application, AppDatabase::class.java)
        .allowMainThreadQueries().setQueryExecutor(Executor { it.run() })
        .setTransactionExecutor(Executor { it.run() }).build()
    val queue = OfflineQueueManager(database.pendingOperationDao(), { RetrofitClient.apiServiceFor(it) },
        { online }, emptyFlow(), scope)
    private var closed = false
    init {
        AppDatabase::class.java.getDeclaredField("INSTANCE").apply { isAccessible = true }.set(null, database)
        OfflineQueueManager::class.java.getDeclaredField("instance").apply { isAccessible = true }.set(null, queue)
    }
    override fun close() {
        if (closed) return
        closed = true
        scope.cancel()
        runBlocking { scope.coroutineContext[Job]!!.join() }
        settings.close()
        OfflineQueueManager::class.java.getDeclaredField("instance").apply { isAccessible = true }.set(null, null)
        database.close()
        AppDatabase::class.java.getDeclaredField("INSTANCE").apply { isAccessible = true }.set(null, null)
    }
}
