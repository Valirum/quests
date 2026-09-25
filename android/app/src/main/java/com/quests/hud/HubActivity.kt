package com.quests.hud

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.viewpager2.widget.ViewPager2
import com.quests.hud.data.PrefsStore
import com.quests.hud.databinding.ActivityHubBinding

/**
 * Swipeable hub: settings page + the SPA (quest=192). Replaces the old
 * separate MainActivity/QuestsWebActivity.
 */
class HubActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHubBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityHubBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.hubPager.orientation = ViewPager2.ORIENTATION_HORIZONTAL
        binding.hubPager.offscreenPageLimit = 1
        binding.hubPager.adapter = HubPagerAdapter(this)
        // ViewPager2's own drag handling competes with SwipeCaptureLayout for
        // the same gesture (it tries to intercept horizontal drags even on a
        // page with nowhere to go, cancelling our capture first) — every
        // page transition here goes through setCurrentItem() instead, called
        // from each page's own SwipeCaptureLayout.
        binding.hubPager.isUserInputEnabled = false

        val startOnJournal = PrefsStore(this).isConfigured()
        if (startOnJournal) HubNav.pendingTab = HubNav.TAB_JOURNAL
        binding.hubPager.setCurrentItem(
            if (startOnJournal) HubPagerAdapter.PAGE_SPA else HubPagerAdapter.PAGE_SETTINGS,
            false,
        )
    }

    /** Settings → SPA, landing on "journal" (the common/forward case). */
    fun goToJournal() {
        HubNav.pendingTab = HubNav.TAB_JOURNAL
        binding.hubPager.setCurrentItem(HubPagerAdapter.PAGE_SPA, true)
    }

    /** Journal → settings (swiping right off the first SPA tab). */
    fun goToSettings() {
        binding.hubPager.setCurrentItem(HubPagerAdapter.PAGE_SETTINGS, true)
    }
}
