package com.factory.wms

import com.factory.wms.ui.util.quantityInputError
import com.factory.wms.ui.util.toPositiveQtyOrNull
import com.factory.wms.ui.util.toQtyOrNull
import com.factory.wms.ui.util.quantityDisplayText
import org.junit.Assert.*
import org.junit.Test

class NativeQuantityInputTest {
    @Test fun displayBreaksPreserveAllDigitsAndKeepFractionWithLastGroup() {
        val original = "+1,234,567,890,123.50 套"
        val displayed = quantityDisplayText(original)
        assertEquals(original, displayed.replace("\u200B", ""))
        assertTrue(displayed.endsWith("123.50 套"))
        assertEquals(4, displayed.count { it == '\u200B' })
    }
    @Test fun nonFiniteAndMalformedQuantitiesNeverBecomeValidInput() {
        for (text in listOf("", " ", "abc", "-1", "NaN", "Infinity", "1e309")) {
            assertNull(text.toPositiveQtyOrNull())
            assertNull(text.toQtyOrNull(allowZero = true))
            assertNotNull(quantityInputError(text, allowZero = false))
        }
    }

    @Test fun onlyStocktakeZeroPolicyAcceptsZero() {
        assertNull("0".toPositiveQtyOrNull())
        assertEquals(0.0, "0".toQtyOrNull(allowZero = true)!!, 0.0)
        assertEquals("请输入大于或等于 0 的有效数量", quantityInputError("-1", allowZero = true))
        assertEquals("请输入大于 0 的有效数量", quantityInputError("0", allowZero = false))
    }

    @Test fun correctedDecimalClearsErrorWithoutChangingTheInputValue() {
        val text = " 12.250 "
        assertNull(quantityInputError(text, allowZero = false))
        assertEquals(12.25, text.toPositiveQtyOrNull()!!, 0.0)
        assertEquals(" 12.250 ", text)
    }
}
