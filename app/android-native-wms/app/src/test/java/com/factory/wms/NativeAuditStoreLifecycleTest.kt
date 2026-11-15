package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** The retained real DataStore must stop before Robolectric can delete its sandbox. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class NativeAuditStoreLifecycleTest {
    private lateinit var application: Application
    private val stores = mutableListOf<NativeAuditLocalStores>()
    @Before fun before() {
        DataStoreTestReset.resetWmsSettingsDataStore()
        application = ApplicationProvider.getApplicationContext()
    }
    @After fun after() { stores.asReversed().forEach { it.close() } }

    @Suppress("UNCHECKED_CAST")
    private fun settings(): DataStore<Preferences> = Class.forName("com.factory.wms.data.repository.WmsRepositoryKt")
        .getDeclaredMethod("getDataStore", Context::class.java).apply { isAccessible = true }
        .invoke(null, application) as DataStore<Preferences>
    private fun fixture() = NativeAuditLocalStores(application).also { stores += it }

    @Test fun closingFixtureRejectsFurtherWritesOnItsRetainedDataStore() = runBlocking {
        val fixture = fixture()
        val store = settings()
        val key = stringPreferencesKey("lifecycle-proof")
        store.edit { it[key] = "before close" }
        fixture.close()
        var rejected = false
        try { store.edit { it[key] = "late write" } }
        catch (_: CancellationException) { rejected = true }
        assertTrue("A fixture must cancel and join its actual DataStore actor before returning", rejected)
    }

    @Test fun closingAndReopeningSameFilePreservesTheCommittedPreferences() = runBlocking {
        val first = fixture()
        val key = stringPreferencesKey("lifecycle-proof")
        settings().edit { it[key] = "committed value" }
        first.close()
        fixture()
        assertEquals("committed value", settings().data.first()[key])
    }
}
