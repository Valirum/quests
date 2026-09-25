package com.quests.hud

import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter

/**
 * Just 2 real ViewPager2 pages: settings and the SPA hub. The 7 SPA tabs
 * live *inside* page 1 (WebHubFragment), switched via JS, not via
 * ViewPager2 — see quest=192 and WebHubFragment's doc comment for why.
 */
class HubPagerAdapter(activity: FragmentActivity) : FragmentStateAdapter(activity) {

    override fun getItemCount(): Int = 2

    override fun createFragment(position: Int): Fragment =
        if (position == 0) SettingsFragment() else WebHubFragment()

    companion object {
        const val PAGE_SETTINGS = 0
        const val PAGE_SPA = 1
    }
}
