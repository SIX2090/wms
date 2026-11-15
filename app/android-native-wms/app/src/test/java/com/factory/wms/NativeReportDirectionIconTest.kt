package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import com.factory.wms.data.model.InOutDetailItem
import com.factory.wms.data.model.StockLedgerItem
import com.factory.wms.ui.screens.InOutDetailItemRow
import com.factory.wms.ui.screens.StockLedgerItemRow
import com.factory.wms.ui.theme.WmsTheme
import org.junit.After
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeReportDirectionIconTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    @After fun after() { disposeComposeActivity(activity) }

    @Test fun reportsKeepDirectionIconsSignsAndBusinessLabels() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent {
            WmsTheme(darkTheme = false) {
                Column {
                    InOutDetailItemRow(InOutDetailItem(1, quantity = 24.0, unit = "件", direction = "in", transactionTypeLabel = "采购入库"))
                    InOutDetailItemRow(InOutDetailItem(2, quantity = -8.0, unit = "包", direction = "out", transactionTypeLabel = "领料出库"))
                    StockLedgerItemRow(StockLedgerItem(referenceType = "采购入库", inQuantity = 24.0, outQuantity = 0.0, balanceQuantity = 124.0))
                    StockLedgerItemRow(StockLedgerItem(referenceType = "销售出库", inQuantity = 0.0, outQuantity = 44.0, balanceQuantity = 128.0))
                    StockLedgerItemRow(StockLedgerItem(referenceType = "库存流水", inQuantity = 0.0, outQuantity = 0.0, balanceQuantity = 128.0))
                }
            }
        }
        compose.onAllNodesWithContentDescription("入库方向").assertCountEquals(2)
        compose.onAllNodesWithContentDescription("出库方向").assertCountEquals(2)
        compose.onNodeWithText("+24 件").assertExists()
        compose.onNodeWithText("-8 包").assertExists()
        compose.onNodeWithText("结存 124").assertExists()
        compose.onAllNodesWithText("结存 128").assertCountEquals(2)
    }
}
