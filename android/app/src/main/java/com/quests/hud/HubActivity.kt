package com.quests.hud

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.viewpager2.widget.ViewPager2
import com.quests.hud.data.PrefsStore
import com.quests.hud.databinding.ActivityHubBinding

/**
 * Swipeable hub: settings + every SPA tab as one horizontal, cyclic strip
 * (quest=192). Replaces the old separate MainActivity/QuestsWebActivity.
 */
class HubActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHubBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityHubBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val startOnJournal = PrefsStore(this).isConfigured()
        binding.hubPager.orientation = ViewPager2.ORIENTATION_HORIZONTAL
        binding.hubPager.adapter = HubPagerAdapter(this)
        binding.hubPager.setCurrentItem(HubPagerAdapter.startPosition(startOnJournal), false)
    }
}
