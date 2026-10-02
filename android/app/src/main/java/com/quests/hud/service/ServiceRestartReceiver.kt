package com.quests.hud.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import com.quests.hud.data.PrefsStore

/**
 * Bring the foreground service back after a reinstall or reboot. Without it
 * the heads-up events silently stop until someone opens Settings and taps
 * "start service" again — an update kills the process and nothing restarts it.
 */
class ServiceRestartReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED &&
            intent.action != Intent.ACTION_BOOT_COMPLETED
        ) return
        if (!PrefsStore(context).isConfigured()) return
        try {
            ContextCompat.startForegroundService(context, Intent(context, QuestsService::class.java))
            Log.i(TAG, "service restarted on ${intent.action}")
        } catch (e: Exception) {
            // Background FGS starts can be refused (e.g. dataSync after boot on
            // newer Android); opening the app starts it instead.
            Log.w(TAG, "restart on ${intent.action} refused: ${e.message}")
        }
    }

    private companion object {
        const val TAG = "QuestsRestart"
    }
}
