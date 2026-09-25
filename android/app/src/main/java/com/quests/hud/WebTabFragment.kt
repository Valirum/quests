package com.quests.hud

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.quests.hud.data.PrefsStore
import com.quests.hud.databinding.FragmentWebTabBinding

/**
 * One SPA tab (journal/toc/notes/...). Reparents the single SharedWebView
 * into this fragment's container and asks it to switch tab — no reload, so
 * ViewPager2 swipes between tabs feel instant instead of re-flashing the
 * whole page (quest=192).
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

    override fun onResume() {
        super.onResume()
        val tab = requireArguments().getString(ARG_TAB)!!
        val base = PrefsStore(requireContext()).apiBase ?: return
        SharedWebView.attach(requireContext(), binding.tabWebContainer, base, tab)
    }

    override fun onPause() {
        SharedWebView.detachFrom(binding.tabWebContainer)
        super.onPause()
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
