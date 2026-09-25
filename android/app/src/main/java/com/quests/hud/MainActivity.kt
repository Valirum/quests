package com.quests.hud

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.quests.hud.data.PrefsStore
import com.quests.hud.databinding.ActivityMainBinding
import com.quests.hud.net.ApiClient
import com.quests.hud.net.ApiError
import com.quests.hud.service.QuestsService
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: PrefsStore

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startQuestsServiceNow()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = PrefsStore(this)
        binding.apiBaseInput.setText(prefs.apiBase.orEmpty())
        binding.apiTokenInput.setText(prefs.apiToken.orEmpty())

        binding.saveButton.setOnClickListener { onSave() }
        binding.startServiceButton.setOnClickListener { startQuestsService() }
        binding.openWebButton.setOnClickListener {
            startActivity(Intent(this, QuestsWebActivity::class.java))
        }

        if (prefs.isConfigured()) {
            binding.statusText.text = getString(R.string.status_configured)
        }
    }

    private fun onSave() {
        val base = binding.apiBaseInput.text.toString().trim()
        val token = binding.apiTokenInput.text.toString().trim()

        if (base.isEmpty()) {
            binding.statusText.text = getString(R.string.status_error_empty_url)
            return
        }

        binding.statusText.text = getString(R.string.status_checking)

        lifecycleScope.launch {
            try {
                val client = ApiClient(base.trimEnd('/'), token.ifBlank { null })
                val authState = client.authState()
                val authRequired = authState.optBoolean("auth_required", false)

                if (authRequired && token.isBlank()) {
                    binding.statusText.text = getString(R.string.status_error_token_required)
                    return@launch
                }

                // health requires auth when auth_required is true; also doubles
                // as a token validity check.
                client.health()

                prefs.apiBase = base
                prefs.apiToken = token.ifBlank { null }
                binding.statusText.text = getString(R.string.status_ok)
            } catch (e: ApiError) {
                binding.statusText.text = getString(R.string.status_error_api, e.message)
            } catch (e: Exception) {
                binding.statusText.text = getString(R.string.status_error_generic, e.message)
            }
        }
    }

    private fun startQuestsService() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        startQuestsServiceNow()
    }

    private fun startQuestsServiceNow() {
        val intent = Intent(this, QuestsService::class.java)
        ContextCompat.startForegroundService(this, intent)
        requestBatteryOptimizationExemption()
    }

    // Without this, custom-firmware task killers (and stock Doze on some
    // OEMs) can still kill the foreground service between polls even though
    // it's marked ongoing — see quest=192 step 719.
    private fun requestBatteryOptimizationExemption() {
        val powerManager = getSystemService(PowerManager::class.java)
        if (powerManager.isIgnoringBatteryOptimizations(packageName)) return
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:$packageName")
        }
        startActivity(intent)
    }
}
