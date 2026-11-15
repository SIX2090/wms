package com.factory.wms

import com.factory.wms.ui.theme.Typography
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeTypographyMinimumTest {
    @Test fun commonBodyAndAuxiliaryStylesMeetRequestedBaseSizes() {
        assertTrue(Typography.bodyLarge.fontSize.value >= 16f)
        assertTrue(Typography.bodyMedium.fontSize.value >= 14f)
        assertTrue(Typography.bodySmall.fontSize.value >= 14f)
        assertTrue(Typography.labelSmall.fontSize.value >= 14f)
        assertTrue(Typography.labelMedium.fontSize.value >= 14f)
    }
}
