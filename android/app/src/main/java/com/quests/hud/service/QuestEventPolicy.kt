package com.quests.hud.service

import org.json.JSONObject

/**
 * Which live events become Android heads-up notifications (quest=269).
 * Mirrors overlay major kinds + automated demotion from NoticeRouter.
 */
object QuestEventPolicy {

    val MAJOR_KINDS = setOf(
        "quest_created",
        "quest_appeared",
        "quest_started",
        "quest_completed",
        "quest_failed",
        "quest_expired",
    )

    private val AUTOMATED_DEMOTE = setOf(
        "quest_created",
        "quest_appeared",
        "quest_started",
    )

    fun shouldNotify(event: JSONObject): Boolean {
        if (event.optString("type") != "quests_changed") return false
        val kind = event.optString("kind")
        if (kind !in MAJOR_KINDS) return false
        if (!event.optBoolean("toast", true)) return false
        if (event.optBoolean("automated", false) && kind in AUTOMATED_DEMOTE) return false
        return true
    }

    fun eyebrowRes(kind: String): Int = when (kind) {
        "quest_created", "quest_appeared" -> com.quests.hud.R.string.event_eyebrow_received
        "quest_started" -> com.quests.hud.R.string.event_eyebrow_started
        "quest_completed" -> com.quests.hud.R.string.event_eyebrow_completed
        "quest_failed" -> com.quests.hud.R.string.event_eyebrow_failed
        "quest_expired" -> com.quests.hud.R.string.event_eyebrow_expired
        else -> com.quests.hud.R.string.event_eyebrow_received
    }

    /** Action preset for notification buttons (max ~3). */
    fun actionsFor(kind: String): List<EventAction> = when (kind) {
        "quest_created", "quest_appeared" -> listOf(
            EventAction.Postpone(15),
            EventAction.Postpone(30),
            EventAction.Postpone(60),
        )
        "quest_started", "quest_expired" -> listOf(
            EventAction.Complete,
            EventAction.Postpone(15),
            EventAction.Postpone(30),
        )
        else -> emptyList() // completed / failed — swipe to dismiss
    }
}

sealed class EventAction {
    data object Complete : EventAction()
    data class Postpone(val minutes: Int) : EventAction()
}
