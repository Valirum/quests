package com.quests.hud.net

import android.util.Log
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
        Log.i(TAG, "GET $url auth=$auth")
        val started = System.nanoTime()
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        // Mobile → public edge gateway can take several seconds per hop;
        // 10s was timing out on SM-A366B against sslip.io (auth/state ~8s).
        conn.connectTimeout = TimeUnit.SECONDS.toMillis(30).toInt()
        conn.readTimeout = TimeUnit.SECONDS.toMillis(30).toInt()
        conn.setRequestProperty("Accept", "application/json")
        conn.setRequestProperty("Connection", "close")
        if (auth && !token.isNullOrBlank()) {
            conn.setRequestProperty("Authorization", "Bearer $token")
        }
        try {
            val status = conn.responseCode
            val stream = if (status in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            val ms = (System.nanoTime() - started) / 1_000_000
            Log.i(TAG, "GET $path → $status in ${ms}ms (${text.length} bytes)")
            if (status !in 200..299) {
                throw ApiError("API $status: $text", status)
            }
            text
        } catch (e: Exception) {
            val ms = (System.nanoTime() - started) / 1_000_000
            Log.e(TAG, "GET $path failed after ${ms}ms: ${e.javaClass.simpleName}: ${e.message}")
            throw e
        } finally {
            conn.disconnect()
        }
    }

    private companion object {
        const val TAG = "QuestsApi"
    }
}
