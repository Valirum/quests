package com.quests.hud

import android.annotation.SuppressLint
import android.content.Context
import android.view.ViewGroup
import android.webkit.WebView
import android.webkit.WebViewClient

/**
 * One WebView for every SPA tab, app-process-lifetime singleton. Swiping
 * between tabs used to create a fresh WebView per tab (full reload, header
 * flashing on every swipe) — now WebTabFragment just reparents this single
 * instance and drives tab switches through window.questsNav.setTab() (see
 * App.svelte) instead of loadUrl, so only the very first navigation ever
 * reloads the page. quest=192.
 */
@SuppressLint("SetJavaScriptEnabled")
object SharedWebView {

    private var webView: WebView? = null
    private var loadedBase: String? = null

    fun attach(context: Context, container: ViewGroup, base: String, initialTab: String) {
        val view = webView ?: WebView(context.applicationContext).also {
            it.settings.javaScriptEnabled = true
            it.settings.domStorageEnabled = true
            it.webViewClient = WebViewClient()
            webView = it
        }

        (view.parent as? ViewGroup)?.let { oldParent ->
            if (oldParent !== container) oldParent.removeView(view)
        }
        if (view.parent == null) container.addView(view)

        if (loadedBase != base) {
            loadedBase = base
            view.loadUrl(if (initialTab == "journal") base else "$base?tab=$initialTab")
        } else {
            setTab(initialTab)
        }
    }

    fun setTab(tab: String) {
        webView?.evaluateJavascript(
            "window.questsNav && window.questsNav.setTab(${org.json.JSONObject.quote(tab)});",
            null,
        )
    }

    fun detachFrom(container: ViewGroup) {
        if (webView?.parent === container) container.removeView(webView)
    }
}
