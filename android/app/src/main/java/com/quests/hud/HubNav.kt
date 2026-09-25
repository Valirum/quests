package com.quests.hud

/**
 * Tiny handoff between the settings page and the SPA-hub page: which SPA
 * tab to land on when the pager brings the SPA hub into view. Set right
 * before `setCurrentItem(1, ...)`, read once in WebHubFragment.onResume and
 * cleared. quest=192.
 */
object HubNav {
    const val TAB_JOURNAL = "journal"
    // hero/stats aren't in the header's own tab bar (unfinished) — not part
    // of the swipe strip. Linear, no wrap: settings through calendar.
    val TAB_ORDER = listOf("journal", "toc", "notes", "attachments", "calendar")

    var pendingTab: String? = null
}
