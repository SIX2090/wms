package com.factory.wms.update

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.factory.wms.WmsApplication

class UpdateInstallReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        (context.applicationContext as? WmsApplication)?.appUpdates?.receive(intent)
    }
}
