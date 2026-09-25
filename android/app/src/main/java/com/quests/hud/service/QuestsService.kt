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
import com.quests.hud.QuestsWebActivity
import com.quests.hud.R
import com.quests.hud.data.PrefsStore
import com.quests.hud.net.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * Foreground service holding the ongoing notification. Polls the same REST
 * API the desktop overlay talks to (note=3) and renders active quests as an
 * InboxStyle list — a single BigTextStyle line can't fit more than one quest
 * (quest=192, steps 716/717). The full list with all details lives in
 * QuestsWebActivity (the existing SPA), reachable by tapping the notification.
 */
class QuestsService : Service() {

    private val job = SupervisorJob()
    private val scope = CoroutineScope(job)
    private lateinit var prefs: PrefsStore

    override fun onCreate() {
        super.onCreate()
        prefs = PrefsStore(this)
        createChannel()
        startForeground(NOTIFICATION_ID, buildMessageNotification(getString(R.string.notification_placeholder_text)))
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
            notify(buildMessageNotification(getString(R.string.notification_not_configured)))
            return
        }
        try {
            val client = ApiClient(base, prefs.apiToken)
            val quests = client.activeQuests()
            notify(buildQuestListNotification(quests))
        } catch (e: Exception) {
            notify(buildMessageNotification(getString(R.string.notification_error, e.message)))
        }
    }

    private fun notify(notification: Notification) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification)
    }

    private fun questLine(quest: JSONObject): String {
        val title = quest.optString("title")
        val progress = quest.optString("progress_label").ifBlank { null }
        return if (progress != null) "$title — $progress" else title
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

    private fun openWebIntent(): PendingIntent = PendingIntent.getActivity(
        this,
        0,
        Intent(this, QuestsWebActivity::class.java),
        PendingIntent.FLAG_IMMUTABLE,
    )

    private fun baseNotification(contentText: String): NotificationCompat.Builder =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(contentText)
            .setOngoing(true)
            .setContentIntent(openWebIntent())

    private fun buildMessageNotification(text: String): Notification =
        baseNotification(text).build()

    private fun buildQuestListNotification(quests: List<JSONObject>): Notification {
        if (quests.isEmpty()) {
            return buildMessageNotification(getString(R.string.notification_no_active_quests))
        }

        val summary = getString(R.string.notification_active_count, quests.size)
        val style = NotificationCompat.InboxStyle().setSummaryText(summary)
        quests.forEach { style.addLine(questLine(it)) }

        return baseNotification(summary).setStyle(style).build()
    }

    companion object {
        private const val CHANNEL_ID = "quests_hud"
        private const val NOTIFICATION_ID = 1
        private const val POLL_INTERVAL_MS = 60_000L
    }
}
