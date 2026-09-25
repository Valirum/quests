package com.quests.hud

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.fragment.app.Fragment
import com.quests.hud.data.PrefsStore
import com.quests.hud.databinding.FragmentWebTabBinding

/**
 * One SPA tab (journal/toc/notes/...), each its own WebView instance so
 * ViewPager2 can slide between them natively — see HubPagerAdapter and
 * quest=192. Same origin as the other tabs, so cookies (session auth,
 * docs/auth.md) are shared automatically via WebView's CookieManager.
 */
class WebTabFragment : Fragment() {

    private var _binding: FragmentWebTabBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentWebTabBinding.inflate(inflater, container, false)
        return binding.root
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val tab = requireArguments().getString(ARG_TAB)!!
        val base = PrefsStore(requireContext()).apiBase
        if (base.isNullOrBlank()) return

        val webView = binding.tabWebView
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = WebViewClient()
        webView.loadUrl(if (tab == "journal") base else "$base?tab=$tab")
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }

    companion object {
        private const val ARG_TAB = "tab"

        fun newInstance(tab: String) = WebTabFragment().apply {
            arguments = Bundle().apply { putString(ARG_TAB, tab) }
        }
    }
}
