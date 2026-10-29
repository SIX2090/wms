package com.factory.wms

import com.factory.wms.ui.components.materialScanCode
import org.junit.Assert.assertEquals
import org.junit.Test

class MaterialScanCodeTest {
    @Test fun plainCodesStillWork() {
        assertEquals("000123", materialScanCode(" 000123 "))
        assertEquals("物料 / A&B+01", materialScanCode("物料 / A&B+01"))
    }
    @Test fun labelUrlYieldsExactCodeForAllScanners() {
        assertEquals("物料 / A&B+01", materialScanCode("https://wms.example/mobile/material?code=%E7%89%A9%E6%96%99+%2F+A%26B%2B01"))
        assertEquals("M1", materialScanCode("http://192.168.1.2:8080/mobile/material?code=M1"))
    }
    @Test fun unrelatedAndAmbiguousUrlsDoNotSelectAMaterial() {
        val unrelated = "https://example.com/other?code=M1"
        assertEquals(unrelated, materialScanCode(unrelated))
        assertEquals("", materialScanCode("https://example.com/mobile/material?code=A&code=B"))
    }
}
