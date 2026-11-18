package com.factory.wms.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.theme.PalettePrimary
import com.factory.wms.ui.theme.PrimaryDark

/** 工作台、登录及账号页共用固定深色背景，保证白字在亮暗主题下可读。 */
@Composable
internal fun WmsIdentityPanel(modifier: Modifier = Modifier, shape: Shape = MaterialTheme.shapes.extraLarge,
    content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth().clip(shape)
        .background(Brush.horizontalGradient(listOf(PrimaryDark, PalettePrimary))).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp), content = content)
}
