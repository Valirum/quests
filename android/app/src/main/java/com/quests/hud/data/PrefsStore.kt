package com.quests.hud.data

import android.content.Context

/** Server address + API token, kept in the app's private SharedPreferences. */
class PrefsStore(context: Context) {

    private val prefs = context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    var apiBase: String?
        get() = prefs.getString(KEY_API_BASE, null)
        set(value) = prefs.edit().putString(KEY_API_BASE, value).apply()

    var apiToken: String?
        get() = prefs.getString(KEY_API_TOKEN, null)
        set(value) = prefs.edit().putString(KEY_API_TOKEN, value).apply()

    fun isConfigured(): Boolean = !apiBase.isNullOrBlank()

    private companion object {
        const val FILE = "quests_hud"
        const val KEY_API_BASE = "api_base"
        const val KEY_API_TOKEN = "api_token"
    }
}
