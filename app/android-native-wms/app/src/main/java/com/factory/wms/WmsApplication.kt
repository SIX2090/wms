package com.factory.wms

import android.app.Application
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.data.api.RetrofitClient

class WmsApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        RetrofitClient.onUnauthorized = {
            AuthEventBus.notifyUnauthorized()
        }
    }
}