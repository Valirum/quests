package com.quests.hud.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

class ApiError(message: String, val status: Int? = null) : IOException(message)

/**
 * Thin client for the same REST API the desktop overlay talks to (see note=3):
 * GET /api/auth/state, GET /api/health, GET /api/quests?status=...
 * Bearer token auth, same as QUESTS_API_TOKEN on the desktop side.
 */
class ApiClient(private val base: String, private val token: String?) {

    suspend fun authState(): JSONObject = getJson("/api/auth/state", auth = false)

    suspend fun health(): JSONObject = getJson("/api/health", auth = true)

    suspend fun activeQuests(): List<JSONObject> {
        val body = getRaw("/api/quests?status=active&status=delayed", auth = true)
        val arr = org.json.JSONArray(body)
        return (0 until arr.length()).map { arr.getJSONObject(it) }
    }

    private suspend fun getJson(path: String, auth: Boolean): JSONObject =
        JSONObject(getRaw(path, auth))

    private suspend fun getRaw(path: String, auth: Boolean): String = withContext(Dispatchers.IO) {
        val url = URL("$base$path")
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = TimeUnit.SECONDS.toMillis(10).toInt()
        conn.readTimeout = TimeUnit.SECONDS.toMillis(10).toInt()
        if (auth && !token.isNullOrBlank()) {
            conn.setRequestProperty("Authorization", "Bearer $token")
        }
        try {
            val status = conn.responseCode
            val stream = if (status in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (status !in 200..299) {
                throw ApiError("API $status: $text", status)
            }
            text
        } finally {
            conn.disconnect()
        }
    }
}
