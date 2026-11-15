package com.factory.wms.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.*
import androidx.compose.ui.unit.dp
import com.factory.wms.BuildConfig
import com.factory.wms.ui.components.StatusBarIconEffect
import com.factory.wms.ui.components.WmsPrimaryButton
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.auth.AuthViewModel

@Composable
fun LoginScreen(viewModel: AuthViewModel, onLoginSuccess: () -> Unit) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    StatusBarIconEffect(darkIcons = MaterialTheme.colorScheme.background.luminance() > 0.5f)
    LaunchedEffect(uiState.isLoggedIn) {
        if (uiState.isLoggedIn) onLoginSuccess()
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }
    Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }, containerColor = Background) { padding ->
        LoginForm(uiState.baseUrl.ifEmpty { BuildConfig.DEFAULT_SERVER_URL }, uiState.isLoading,
            Modifier.padding(padding), onLogin = viewModel::login)
    }
}

/** 测试直接操作真实登录表单；不会构造仓库、账号或请求。 */
@Composable
internal fun LoginForm(initialBaseUrl: String, isLoading: Boolean, modifier: Modifier = Modifier,
    onLogin: (String, String, String) -> Unit) {
    var username by rememberSaveable { mutableStateOf("") }
    // 密码只驻留当前组合，不写入可保存状态。
    var password by remember { mutableStateOf("") }
    var baseUrl by rememberSaveable { mutableStateOf(initialBaseUrl) }
    var showPassword by remember { mutableStateOf(false) }
    var showConnection by rememberSaveable { mutableStateOf(false) }
    val focusManager = LocalFocusManager.current
    LaunchedEffect(initialBaseUrl) { if (initialBaseUrl.isNotBlank()) baseUrl = initialBaseUrl }
    val loginEnabled = !isLoading && username.isNotBlank() && password.isNotBlank()
    val login = {
        focusManager.clearFocus()
        if (loginEnabled) onLogin(username, password, baseUrl)
    }
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).imePadding()
        .padding(horizontal = 24.dp, vertical = 32.dp), verticalArrangement = Arrangement.spacedBy(24.dp)) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(Icons.Outlined.Warehouse, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(40.dp))
            Text("WMS", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            Text("仓库工作台", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            Text("登录后开始仓库作业", style = MaterialTheme.typography.bodyLarge, color = OnSurfaceVariant)
            Text("入库 · 出库 · 盘点 · 识物", style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
        }
        Surface(color = CardBackground, shape = MaterialTheme.shapes.large) {
            Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("登录工作台", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(username, { username = it }, label = { Text("用户名") },
                    leadingIcon = { Icon(Icons.Outlined.Person, null) }, singleLine = true,
                    modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                    keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(FocusDirection.Down) }))
                OutlinedTextField(password, { password = it }, label = { Text("密码") },
                    leadingIcon = { Icon(Icons.Outlined.Lock, null) }, singleLine = true,
                    modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium,
                    visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = { IconButton(onClick = { showPassword = !showPassword }, modifier = Modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp)) {
                        Icon(if (showPassword) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                            if (showPassword) "隐藏密码" else "显示密码")
                    } }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { login() }))
                WmsPrimaryButton("登录", login, Modifier.fillMaxWidth(), loading = isLoading, enabled = loginEnabled)
                HorizontalDivider(color = DividerSoft)
                TextButton(onClick = { showConnection = !showConnection }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Icon(Icons.Outlined.Dns, null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (showConnection) "收起连接设置" else "连接设置")
                    Icon(if (showConnection) Icons.Outlined.ExpandLess else Icons.Outlined.ExpandMore, null)
                }
                // 保留服务器可配置能力，收起不清空地址，也不保存或更改真实账号凭据。
                if (showConnection) {
                    OutlinedTextField(baseUrl, { baseUrl = it }, label = { Text("服务器地址") },
                        modifier = Modifier.fillMaxWidth(), singleLine = true, shape = MaterialTheme.shapes.medium,
                        supportingText = { if (baseUrl.isNotBlank()) Text(baseUrl, softWrap = true) },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() }))
                }
            }
        }
        Text("版本 ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodyMedium,
            color = OnSurfaceVariant, modifier = Modifier.align(Alignment.CenterHorizontally))
    }
}
