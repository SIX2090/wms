package com.factory.wms.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Remove
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.QuantityDraft
import com.factory.wms.ui.util.toQtyOrNull
import com.factory.wms.util.formatQuantity
import java.math.BigDecimal

@OptIn(ExperimentalFoundationApi::class)
@Composable
internal fun ScanQuantityStepper(
    line: ScanLine,
    enabled: Boolean,
    allowZero: Boolean,
    draft: QuantityDraft?,
    onDraft: (QuantityDraft?) -> Unit,
    onUpdate: (ScanLine, Double) -> Boolean,
    accent: Color,
    failureMessage: () -> String = { "清单已变化，请取消修改后重新核对" },
    modifier: Modifier = Modifier,
    identityOverride: String? = null,
) {
    val displayId = "${line.material_code}|${line.location_code.orEmpty()}"
    val id = identityOverride ?: displayId
    var value by rememberSaveable(id, stateSaver = TextFieldValue.Saver) {
        mutableStateOf(TextFieldValue(draft?.raw ?: formatQuantity(line.quantity)))
    }
    var expected by rememberSaveable(id) { mutableDoubleStateOf(draft?.expected ?: line.quantity) }
    var focused by remember { mutableStateOf(false) }
    val focusManager = LocalFocusManager.current
    val confirmationLocation = remember { BringIntoViewRequester() }
    LaunchedEffect(draft != null) {
        if (draft != null) confirmationLocation.bringIntoView()
    }
    LaunchedEffect(line.quantity, focused, draft) {
        if (!focused && draft == null) {
            value = TextFieldValue(formatQuantity(line.quantity))
            expected = line.quantity
        }
    }

    fun apply(raw: TextFieldValue) {
        value = raw
        val previous = draft?.expected ?: expected
        val number = raw.text.toQtyOrNull(allowZero)
        onDraft(QuantityDraft(raw.text, previous, if (number != null) "" else
            if (allowZero) "请输入大于或等于 0 的有效数量" else "请输入大于 0 的有效数量"))
    }

    fun commit(number: Double, raw: String) {
        val previous = draft?.expected ?: expected
        if (onUpdate(line.copy(quantity = previous), number)) {
            expected = number
            value = TextFieldValue(formatQuantity(number))
            onDraft(null)
        } else {
            onDraft(QuantityDraft(raw, previous, failureMessage()))
        }
    }

    fun target(delta: Long): Double? {
        val current = draft?.raw?.toQtyOrNull(allowZero) ?: if (draft == null) expected else return null
        if (!current.isFinite()) return null
        val target = BigDecimal.valueOf(current).add(BigDecimal.valueOf(delta)).toDouble()
        return target.takeIf { it.isFinite() && it != current && it >= 0 && (allowZero || it > 0) }
    }

    Column(modifier = modifier) {
        Text(line.material_unit?.takeIf { it.isNotBlank() }?.let { "数量（$it）" } ?: "数量（单位未获取）", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            OutlinedIconButton(onClick = { target(-1)?.let { commit(it, formatQuantity(it)) } }, enabled = enabled && target(-1) != null,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.size(48.dp).semantics { contentDescription = "减少数量：$displayId" }) {
                Icon(Icons.Outlined.Remove, null, tint = if (enabled && target(-1) != null) accent else MaterialTheme.colorScheme.onSurface.copy(alpha = .38f))
            }
            Surface(modifier = Modifier.weight(1f).heightIn(min = 48.dp),
                shape = MaterialTheme.shapes.small, color = MaterialTheme.colorScheme.surfaceVariant,
                border = BorderStroke(1.dp, if (draft?.error?.isNotEmpty() == true) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.outline)) {
                Box(contentAlignment = Alignment.Center, modifier = Modifier.heightIn(min = 48.dp)) {
                    BasicTextField(value = value, onValueChange = ::apply, enabled = enabled,
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)
                            .onFocusChanged { focused = it.isFocused }
                            .semantics { contentDescription = "修改数量：${line.material_code} ${line.location_code.orEmpty()}" },
                        textStyle = MaterialTheme.typography.titleLarge.copy(fontSize = 20.sp,
                            color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold,
                            textAlign = TextAlign.Center, fontFeatureSettings = "tnum"),
                        decorationBox = { field -> Box(Modifier.fillMaxWidth().heightIn(min = 48.dp),
                            contentAlignment = Alignment.Center) { field() } },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal, imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = {
                            draft?.raw?.toQtyOrNull(allowZero)?.let { commit(it, draft.raw) }
                            focusManager.clearFocus()
                        }))
                }
            }
            OutlinedIconButton(onClick = { target(1)?.let { commit(it, formatQuantity(it)) } }, enabled = enabled && target(1) != null,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.size(48.dp).semantics { contentDescription = "增加数量：$displayId" }) {
                Icon(Icons.Outlined.Add, null, tint = if (enabled && target(1) != null) accent else MaterialTheme.colorScheme.onSurface.copy(alpha = .38f))
            }
        }
        if (value.text.length > 8) {
            Text("完整数量：${value.text}", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.fillMaxWidth(), softWrap = true)
        }
        draft?.let {
            if (it.error.isNotEmpty()) Text(it.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            Row(modifier = Modifier.bringIntoViewRequester(confirmationLocation),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = {
                    expected = line.quantity; value = TextFieldValue(formatQuantity(line.quantity)); onDraft(null)
                }, modifier = Modifier.heightIn(min = 48.dp)) { Text("取消") }
                TextButton(onClick = { it.raw.toQtyOrNull(allowZero)?.let { number -> commit(number, it.raw) } },
                    enabled = enabled && it.raw.toQtyOrNull(allowZero) != null && it.error.isEmpty(),
                    modifier = Modifier.heightIn(min = 48.dp)) { Text("确定数量") }
            }
        }
    }
}
