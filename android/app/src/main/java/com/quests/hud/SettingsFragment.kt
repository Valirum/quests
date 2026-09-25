package com.quests.hud

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import com.quests.hud.data.PrefsStore
import com.quests.hud.databinding.FragmentSettingsBinding
import com.quests.hud.net.ApiClient
import com.quests.hud.net.ApiError
import com.quests.hud.service.QuestsService
import kotlinx.coroutines.launch

/** Settings page of the swipe hub — sits immediately to the left of the journal (quest=192). */
class SettingsFragment : Fragment() {

    private var _binding: FragmentSettingsBinding? = null
    private val binding get() = _binding!!
    private lateinit var prefs: PrefsStore

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startQuestsServiceNow()
        }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?,
    ): View {
        _binding = FragmentSettingsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        prefs = PrefsStore(requireContext())
        binding.apiBaseInput.setText(prefs.apiBase.orEmpty())
        binding.apiTokenInput.setText(prefs.apiToken.orEmpty())

        binding.saveButton.setOnClickListener { onSave() }
        binding.startServiceButton.setOnClickListener { startQuestsService() }

        if (prefs.isConfigured()) {
            binding.statusText.text = getString(R.string.status_configured)
        }
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }

    private fun onSave() {
        val base = binding.apiBaseInput.text.toString().trim()
        val token = binding.apiTokenInput.text.toString().trim()

        if (base.isEmpty()) {
            binding.statusText.text = getString(R.string.status_error_empty_url)
            return
        }

        binding.statusText.text = getString(R.string.status_checking)

        viewLifecycleOwner.lifecycleScope.launch {
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
        val context = requireContext()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        startQuestsServiceNow()
    }

    private fun startQuestsServiceNow() {
        val context = requireContext()
        val intent = Intent(context, QuestsService::class.java)
        ContextCompat.startForegroundService(context, intent)
        requestBatteryOptimizationExemption()
    }

    // Without this, custom-firmware task killers (and stock Doze on some
    // OEMs) can still kill the foreground service between polls even though
    // it's marked ongoing — see quest=192 step 719.
    private fun requestBatteryOptimizationExemption() {
        val context = requireContext()
        val powerManager = context.getSystemService(PowerManager::class.java)
        if (powerManager.isIgnoringBatteryOptimizations(context.packageName)) return
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:${context.packageName}")
        }
        startActivity(intent)
    }
}
