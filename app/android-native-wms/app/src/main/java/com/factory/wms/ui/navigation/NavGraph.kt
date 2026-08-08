package com.factory.wms.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.ui.components.VoiceAssistantOverlay
import com.factory.wms.ui.screens.*
import com.factory.wms.ui.viewmodel.ai.AiViewModel
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.voice.VoiceCommandViewModel

@Composable
fun AppNavGraph() {
    val navController = rememberNavController()
    val authViewModel: AuthViewModel = viewModel()
    val scanViewModel: ScanViewModel = viewModel()
    val aiViewModel: AiViewModel = viewModel()
    val openingStockViewModel: OpeningStockViewModel = viewModel()
    val voiceViewModel: VoiceCommandViewModel = viewModel()

    val authState by authViewModel.uiState.collectAsState()

    val startDestination = if (authState.isLoggedIn) Screen.Home.route else Screen.Login.route

    // Listen for 401 unauthorized events and navigate to login
    LaunchedEffect(Unit) {
        AuthEventBus.unauthorizedEvents.collect {
            navController.navigate(Screen.Login.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        NavHost(navController = navController, startDestination = startDestination) {
            composable(Screen.Login.route) {
                LoginScreen(
                    viewModel = authViewModel,
                    onLoginSuccess = {
                        navController.navigate(Screen.Home.route) {
                            popUpTo(Screen.Login.route) { inclusive = true }
                        }
                    }
                )
            }

            composable(Screen.Home.route) {
                HomeScreen(
                    authViewModel = authViewModel,
                    onNavigate = { screen ->
                        navController.navigate(screen.route)
                    },
                    onLogout = {
                        navController.navigate(Screen.Login.route) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                )
            }

            composable(Screen.Inbound.route) {
                InboundScreen(
                    viewModel = scanViewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.Outbound.route) {
                OutboundScreen(
                    viewModel = scanViewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.StockQuery.route) {
                StockQueryScreen(
                    viewModel = scanViewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.Stocktake.route) {
                StocktakeScreen(
                    viewModel = scanViewModel,
                    onBack = { navController.popBackStack() },
                    onRecognize = { navController.navigate(Screen.StocktakeRecognize.route) }
                )
            }

            composable(Screen.OpeningStock.route) {
                OpeningStockScreen(
                    viewModel = openingStockViewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.DocumentOcr.route) {
                DocumentOcrScreen(
                    viewModel = aiViewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.ObjectRecognize.route) {
                ObjectRecognizeScreen(
                    viewModel = aiViewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.StocktakeRecognize.route) {
                StocktakeRecognizeScreen(
                    aiViewModel = aiViewModel,
                    scanViewModel = scanViewModel,
                    onBack = { navController.popBackStack() }
                )
            }
        }

        // 语音助手悬浮层，仅登录态显示
        if (authState.isLoggedIn) {
            VoiceAssistantOverlay(
                voiceViewModel = voiceViewModel,
                authViewModel = authViewModel,
                navController = navController
            )
        }
    }
}