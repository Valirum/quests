package com.quests.hud.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.quests.hud.HubActivity
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
 * Foreground service: ongoing quest list + live event heads-ups (quest=269).
 * List polls `/api/quests`; events poll `/api/events?since=` (same auth as HUD).
 */
class QuestsService : Service() {

    private val job = SupervisorJob()
    private val scope = CoroutineScope(job)
    private lateinit var prefs: PrefsStore
    private var eventsSince: Int = 0
    private var eventsSeeded: Boolean = false

    override fun onCreate() {
        super.onCreate()
        prefs = PrefsStore(this)
        createOngoingChannel()
        EventNotifier.ensureChannel(this)
        startForeground(
            ONGOING_NOTIFICATION_ID,
            buildMessageNotification(getString(R.string.notification_placeholder_text)),
        )
        startPollingLoops()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        job.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    /**
     * One loop for both polls so HttpURLConnection calls never overlap —
     * parallel quests+events requests were timing out on the mobile gateway.
     */
    private fun startPollingLoops() {
        scope.launch {
            var ongoingAge = ONGOING_POLL_MS // poll list immediately on start
            while (isActive) {
                if (ongoingAge >= ONGOING_POLL_MS) {
                    pollOngoingOnce()
                    ongoingAge = 0L
                }
                pollEventsOnce()
                delay(EVENTS_POLL_MS)
                ongoingAge += EVENTS_POLL_MS
            }
        }
    }
    private suspend fun pollOngoingOnce() {
        val base = prefs.apiBase
        if (base.isNullOrBlank()) {
            notifyOngoing(buildMessageNotification(getString(R.string.notification_not_configured)))
            return
        }
        try {
            val client = ApiClient(base, prefs.apiToken)
            val quests = client.activeQuests()
            notifyOngoing(buildQuestListNotification(quests))
        } catch (e: Exception) {
            notifyOngoing(buildMessageNotification(getString(R.string.notification_error, e.message)))
        }
    }

    private suspend fun pollEventsOnce() {
        val base = prefs.apiBase
        if (base.isNullOrBlank()) return
        try {
            val client = ApiClient(base, prefs.apiToken)
            val (revision, events) = client.eventsSince(eventsSince)
            if (!eventsSeeded) {
                // Don't replay history as heads-ups on service start — only new.
                eventsSince = revision
                eventsSeeded = true
                Log.i(TAG, "events seeded at revision=$revision")
                return
            }
            for (event in events) {
                val rev = event.optInt("revision", 0)
                if (rev > eventsSince) eventsSince = rev
                if (!QuestEventPolicy.shouldNotify(event)) continue
                Log.i(TAG, "event notify kind=${event.optString("kind")} rev=$rev")
                EventNotifier.show(this@QuestsService, event)
            }
            if (revision > eventsSince) eventsSince = revision
        } catch (e: Exception) {
            Log.w(TAG, "events poll: ${e.message}")
        }
    }

    private fun notifyOngoing(notification: Notification) {
        getSystemService(NotificationManager::class.java).notify(ONGOING_NOTIFICATION_ID, notification)
    }

    private fun questLine(quest: JSONObject): String {
        val title = quest.optString("title")
        val progress = quest.optString("progress_label").ifBlank { null }
        return if (progress != null) "$title — $progress" else title
    }

    private fun createOngoingChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            ONGOING_CHANNEL_ID,
            getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_LOW,
        )
        manager.createNotificationChannel(channel)
    }

    private fun openWebIntent(): PendingIntent = PendingIntent.getActivity(
        this,
        0,
        Intent(this, HubActivity::class.java),
        PendingIntent.FLAG_IMMUTABLE,
    )

    private fun baseNotification(contentText: String): NotificationCompat.Builder =
        NotificationCompat.Builder(this, ONGOING_CHANNEL_ID)
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
        private const val TAG = "QuestsService"
        private const val ONGOING_CHANNEL_ID = "quests_hud"
        private const val ONGOING_NOTIFICATION_ID = 1
        private const val ONGOING_POLL_MS = 60_000L
        private const val EVENTS_POLL_MS = 5_000L
    }
}
