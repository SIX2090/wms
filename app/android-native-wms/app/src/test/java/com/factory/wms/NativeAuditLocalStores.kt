package com.factory.wms

import android.app.Application
import androidx.room.Room
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.local.AppDatabase
import com.factory.wms.data.repository.OfflineQueueManager
import java.util.concurrent.Executor
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.emptyFlow

/** A private Room database and offline queue whose workers never outlive a test. */
internal class NativeAuditLocalStores(application:Application) {
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    val database=Room.inMemoryDatabaseBuilder(application,AppDatabase::class.java)
        .allowMainThreadQueries().setQueryExecutor(Executor{it.run()})
        .setTransactionExecutor(Executor{it.run()}).build()
    init {
        AppDatabase::class.java.getDeclaredField("INSTANCE").apply{isAccessible=true}.set(null,database)
        val queue=OfflineQueueManager(database.pendingOperationDao(),{RetrofitClient.apiServiceFor(it)},
            {false},emptyFlow(),scope)
        OfflineQueueManager::class.java.getDeclaredField("instance").apply{isAccessible=true}.set(null,queue)
    }
    fun close(){
        scope.cancel();runBlocking{scope.coroutineContext[Job]!!.join()}
        OfflineQueueManager::class.java.getDeclaredField("instance").apply{isAccessible=true}.set(null,null)
        database.close()
        AppDatabase::class.java.getDeclaredField("INSTANCE").apply{isAccessible=true}.set(null,null)
    }
}
