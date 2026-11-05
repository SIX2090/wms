package com.factory.wms

import com.factory.wms.data.model.OpeningStockDto
import com.factory.wms.data.model.OpeningStockUpdateRequest
import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class OpeningStockRevisionTest {
    private val gson = Gson()

    @Test
    fun listSnapshotIsCarriedIntoEditBody() {
        val item = gson.fromJson("""{"id":7,"quantity":5,"revision":"snapshot-A"}""", OpeningStockDto::class.java)
        val request = OpeningStockUpdateRequest(quantity = 8.0, revision = item.revision)
        val body = gson.toJsonTree(request).asJsonObject
        assertEquals("snapshot-A", body.get("revision").asString)
        assertEquals(8.0, body.get("quantity").asDouble, 0.0)
        assertFalse(body.has("price"))
    }

    @Test
    fun missingServerSnapshotDoesNotInventOne() {
        val item = gson.fromJson("""{"id":7,"quantity":5}""", OpeningStockDto::class.java)
        val body = gson.toJsonTree(OpeningStockUpdateRequest(quantity = 8.0, revision = item.revision)).asJsonObject
        assertFalse(body.has("revision"))
    }
}
