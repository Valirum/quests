package com.quests.hud

import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter

/**
 * settings ↔ journal ↔ toc ↔ notes ↔ attachments ↔ calendar ↔ hero ↔ stats,
 * cyclic in both directions (quest=192: swipe left = next, right = previous).
 * ViewPager2 has no built-in infinite mode, so this uses the standard trick:
 * a virtually unbounded item count, real page = position % PAGES.size.
 */
class HubPagerAdapter(activity: FragmentActivity) : FragmentStateAdapter(activity) {

    override fun getItemCount(): Int = Int.MAX_VALUE

    override fun createFragment(position: Int): Fragment {
        val page = PAGES[position % PAGES.size]
        return if (page == "settings") SettingsFragment() else WebTabFragment.newInstance(page)
    }

    override fun getItemId(position: Int): Long = (position % PAGES.size).toLong()

    override fun containsItem(itemId: Long): Boolean = itemId in PAGES.indices.map { it.toLong() }

    companion object {
        // Order matches the SPA's own tab order (App.svelte); "settings" is
        // an Android-only page, not part of the SPA.
        val PAGES = listOf("settings", "journal", "toc", "notes", "attachments", "calendar", "hero", "stats")

        fun startPosition(startOnJournal: Boolean): Int {
            val anchor = (Int.MAX_VALUE / 2) - (Int.MAX_VALUE / 2) % PAGES.size
            return anchor + PAGES.indexOf(if (startOnJournal) "journal" else "settings")
        }
    }
}
