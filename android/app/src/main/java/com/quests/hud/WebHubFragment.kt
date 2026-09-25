package com.quests.hud

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.quests.hud.data.PrefsStore
import com.quests.hud.databinding.FragmentWebHubBinding
import org.json.JSONObject

/**
 * All SPA tabs in a single, never-reparented WebView (page 1 of HubActivity's
 * 2-page pager). Swiping left/right here never touches ViewPager2 — it's
 * caught by SwipeCaptureLayout and switches tabs via window.questsNav.setTab
 * (App.svelte), so nothing reloads. Linear strip, no wrap: swiping right off
 * "journal" (the first tab) hands off to the settings page; swiping left off
 * "calendar" (the last tab) does nothing. quest=192.
 */
class WebHubFragment : Fragment() {

    private var _binding: FragmentWebHubBinding? = null
    private val binding get() = _binding!!
    private var loaded = false
    private var currentTab = HubNav.TAB_JOURNAL

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentWebHubBinding.inflate(inflater, container, false)
        return binding.root
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.spaWebView.settings.javaScriptEnabled = true
        binding.spaWebView.settings.domStorageEnabled = true
        // This WebView's HTTP cache survives across app runs and can pin an
        // old bundle from a previous debug install — e.g. one predating the
        // questsNav hook this fragment depends on. Always revalidate.
        binding.spaWebView.settings.cacheMode = android.webkit.WebSettings.LOAD_NO_CACHE
        binding.spaWebView.clearCache(true)
        binding.spaWebView.webViewClient = android.webkit.WebViewClient()

        binding.root.onSwipeLeft = { onSwipe(forward = true) }
        binding.root.onSwipeRight = { onSwipe(forward = false) }
    }

    override fun onResume() {
        super.onResume()
        val landingTab = HubNav.pendingTab ?: HubNav.TAB_JOURNAL
        HubNav.pendingTab = null

        val base = PrefsStore(requireContext()).apiBase
        if (base.isNullOrBlank()) return

        currentTab = landingTab
        if (!loaded) {
            loaded = true
            binding.spaWebView.loadUrl(if (landingTab == "journal") base else "$base?tab=$landingTab")
        } else {
            setTab(landingTab)
        }
    }

    private fun onSwipe(forward: Boolean) {
        val order = HubNav.TAB_ORDER
        val idx = order.indexOf(currentTab).let { if (it == -1) 0 else it }
        val nextIdx = if (forward) idx + 1 else idx - 1

        if (nextIdx < 0) {
            // Off the start (journal) — hand off to settings.
            (activity as? HubActivity)?.goToSettings()
            return
        }
        if (nextIdx >= order.size) {
            // Off the end (calendar) — linear strip, nowhere further to go.
            return
        }

        currentTab = order[nextIdx]
        setTab(currentTab)
    }

    private fun setTab(tab: String) {
        binding.spaWebView.evaluateJavascript(
            "window.questsNav && window.questsNav.setTab(${JSONObject.quote(tab)});",
            null,
        )
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }
}
