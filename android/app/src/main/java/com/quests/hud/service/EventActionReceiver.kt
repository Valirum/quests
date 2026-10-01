package com.quests.hud.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.quests.hud.data.PrefsStore
import com.quests.hud.net.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.time.Instant
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/**
 * Handles heads-up notification actions: complete / postpone N minutes
 * (same payload as site `postponeQuest`, quiet=1) — quest=269.
 */
class EventActionReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent == null) return
        val questId = intent.getIntExtra(EXTRA_QUEST_ID, 0)
        val revision = intent.getIntExtra(EXTRA_REVISION, 0)
        if (questId < 1) return

        val pending = goAsync()
        scope.launch {
            try {
                val prefs = PrefsStore(context)
                val base = prefs.apiBase
                if (base.isNullOrBlank()) {
                    Log.w(TAG, "no api base configured")
                    return@launch
                }
                val client = ApiClient(base, prefs.apiToken)
                when (intent.action) {
                    ACTION_COMPLETE -> {
                        client.patchQuest(questId, JSONObject().put("status", "completed"))
                        Log.i(TAG, "completed quest=$questId")
                    }
                    ACTION_POSTPONE -> {
                        val minutes = intent.getIntExtra(EXTRA_MINUTES, 15).coerceAtLeast(1)
                        val secs = minutes * 60
                        val deadline = Instant.now().plus(secs.toLong(), ChronoUnit.SECONDS)
                        val body = JSONObject()
                            .put("status", "active")
                            .put("deadline_at", DateTimeFormatter.ISO_INSTANT.format(deadline))
                            .put("duration_seconds", secs)
                        client.patchQuest(questId, body)
                        Log.i(TAG, "postponed quest=$questId by ${minutes}m")
                    }
                    else -> return@launch
                }
                EventNotifier.cancel(context, revision)
            } catch (e: Exception) {
                Log.e(TAG, "action failed: ${e.message}", e)
            } finally {
                pending.finish()
            }
        }
    }

    companion object {
        const val ACTION_COMPLETE = "com.quests.hud.action.COMPLETE"
        const val ACTION_POSTPONE = "com.quests.hud.action.POSTPONE"
        const val EXTRA_QUEST_ID = "quest_id"
        const val EXTRA_REVISION = "revision"
        const val EXTRA_MINUTES = "minutes"

        private const val TAG = "QuestsEventAction"
        private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    }
}
