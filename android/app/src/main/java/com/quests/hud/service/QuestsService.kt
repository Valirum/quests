package com.quests.hud.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.quests.hud.MainActivity
import com.quests.hud.R
import com.quests.hud.data.PrefsStore
import com.quests.hud.net.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * Foreground service holding the ongoing notification. Polls the same REST
 * API the desktop overlay talks to (note=3) and renders a summary of active
 * quests/steps (quest=192, steps 716/717).
 */
class QuestsService : Service() {

    private val job = SupervisorJob()
    private val scope = CoroutineScope(job)
    private lateinit var prefs: PrefsStore

    override fun onCreate() {
        super.onCreate()
        prefs = PrefsStore(this)
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification(getString(R.string.notification_placeholder_text)))
        startPollingLoop()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        job.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startPollingLoop() {
        scope.launch {
            while (isActive) {
                pollOnce()
                delay(POLL_INTERVAL_MS)
            }
        }
    }

    private suspend fun pollOnce() {
        val base = prefs.apiBase
        if (base.isNullOrBlank()) {
            updateNotification(getString(R.string.notification_not_configured))
            return
        }
        try {
            val client = ApiClient(base, prefs.apiToken)
            val quests = client.activeQuests()
            updateNotification(summarize(quests))
        } catch (e: Exception) {
            updateNotification(getString(R.string.notification_error, e.message))
        }
    }

    private fun summarize(quests: List<JSONObject>): String {
        if (quests.isEmpty()) return getString(R.string.notification_no_active_quests)

        val lines = mutableListOf<String>()
        lines += getString(R.string.notification_active_count, quests.size)

        nearestDeadline(quests)?.let { lines += getString(R.string.notification_nearest_deadline, it) }

        currentStepLine(quests)?.let { lines += it }

        return lines.joinToString("\n")
    }

    private fun nearestDeadline(quests: List<JSONObject>): String? {
        return quests
            .mapNotNull { if (it.isNull("deadline_at")) null else it.optString("deadline_at") }
            .minOrNull()
    }

    private fun currentStepLine(quests: List<JSONObject>): String? {
        for (quest in quests) {
            val steps = quest.optJSONArray("steps") ?: continue
            for (i in 0 until steps.length()) {
                val step = steps.getJSONObject(i)
                if (!step.optBoolean("done", false)) {
                    return getString(
                        R.string.notification_current_step,
                        quest.optString("title"),
                        step.optString("title"),
                        step.optInt("progress_current"),
                        step.optInt("progress_total"),
                    )
                }
            }
        }
        return null
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_LOW,
        )
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val openApp = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val firstLine = text.lineSequence().first()
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(firstLine)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setOngoing(true)
            .setContentIntent(openApp)
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "quests_hud"
        private const val NOTIFICATION_ID = 1
        private const val POLL_INTERVAL_MS = 60_000L
    }
}
