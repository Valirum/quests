package com.quests.hud

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.quests.hud.data.PrefsStore

/**
 * Full quest list, reusing the existing SPA instead of building a native
 * list screen — same origin as the desktop browser, same session-cookie
 * auth (see docs/auth.md; this is a browser client, not the bearer-token
 * headless path QuestsService/ApiClient use). quest=192 step "full list".
 */
class QuestsWebActivity : AppCompatActivity() {

    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_quests_web)

        val base = PrefsStore(this).apiBase
        if (base.isNullOrBlank()) {
            Toast.makeText(this, getString(R.string.status_error_empty_url), Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        webView = findViewById(R.id.questsWebView)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = WebViewClient()
        webView.loadUrl(base)

        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (webView.canGoBack()) webView.goBack() else finish()
                }
            },
        )
    }
}
