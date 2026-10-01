package com.quests.hud.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.quests.hud.HubActivity
import com.quests.hud.R
import org.json.JSONObject

/** Heads-up event notifications (separate from the ongoing HUD list). */
object EventNotifier {

    const val CHANNEL_ID = "quests_events"
    private const val NOTIFICATION_ID_BASE = 1000

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.event_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = context.getString(R.string.event_channel_description)
            enableVibration(true)
        }
        manager.createNotificationChannel(channel)
    }

    fun notificationId(revision: Int): Int = NOTIFICATION_ID_BASE + (revision and 0xffff)

    fun show(context: Context, event: JSONObject) {
        val kind = event.optString("kind")
        val revision = event.optInt("revision", 0)
        val questId = event.optInt("quest_id", 0)
        val title = event.optString("title").ifBlank { "—" }
        val eyebrow = context.getString(QuestEventPolicy.eyebrowRes(kind))
        val notifId = notificationId(revision)

        val openApp = PendingIntent.getActivity(
            context,
            notifId,
            Intent(context, HubActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(eyebrow)
            .setContentText(title)
            .setStyle(NotificationCompat.BigTextStyle().bigText(title))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setAutoCancel(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openApp)

        QuestEventPolicy.actionsFor(kind).forEachIndexed { index, action ->
            builder.addAction(actionPending(context, notifId, questId, revision, action, index))
        }

        context.getSystemService(NotificationManager::class.java)
            .notify(notifId, builder.build())
    }

    fun cancel(context: Context, revision: Int) {
        context.getSystemService(NotificationManager::class.java)
            .cancel(notificationId(revision))
    }

    private fun actionPending(
        context: Context,
        notifId: Int,
        questId: Int,
        revision: Int,
        action: EventAction,
        index: Int,
    ): NotificationCompat.Action {
        val (act, label, minutes) = when (action) {
            EventAction.Complete -> Triple(
                EventActionReceiver.ACTION_COMPLETE,
                context.getString(R.string.event_action_complete),
                0,
            )
            is EventAction.Postpone -> Triple(
                EventActionReceiver.ACTION_POSTPONE,
                context.getString(R.string.event_action_postpone_min, action.minutes),
                action.minutes,
            )
        }
        val intent = Intent(context, EventActionReceiver::class.java).apply {
            this.action = act
            putExtra(EventActionReceiver.EXTRA_QUEST_ID, questId)
            putExtra(EventActionReceiver.EXTRA_REVISION, revision)
            putExtra(EventActionReceiver.EXTRA_MINUTES, minutes)
        }
        val pi = PendingIntent.getBroadcast(
            context,
            notifId * 10 + index,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Action.Builder(0, label, pi).build()
    }
}
