package com.quests.hud

import android.content.Context
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.ViewConfiguration
import android.widget.FrameLayout
import kotlin.math.abs

/**
 * Captures a clearly-horizontal drag before a child WebView gets a chance to
 * consume it. WebView inside a ViewPager2 otherwise swallows swipe gestures
 * itself (a known WebView/ViewPager2 interaction), so tab switching here is
 * handled entirely by this layout + JS calls, not by ViewPager2 (quest=192).
 */
class SwipeCaptureLayout @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : FrameLayout(context, attrs) {

    var onSwipeLeft: (() -> Unit)? = null
    var onSwipeRight: (() -> Unit)? = null

    private val touchSlop = ViewConfiguration.get(context).scaledTouchSlop
    private var downX = 0f
    private var downY = 0f
    private var capturing = false

    // WebView calls this as soon as it starts handling a touch (even for a
    // gesture that turns out horizontal), which otherwise stops
    // onInterceptTouchEvent from being consulted for the rest of the
    // sequence. Ignore it until we've made our own direction call.
    override fun requestDisallowInterceptTouchEvent(disallowIntercept: Boolean) {
        if (capturing) super.requestDisallowInterceptTouchEvent(disallowIntercept)
    }

    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = ev.x
                downY = ev.y
                capturing = false
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = ev.x - downX
                val dy = ev.y - downY
                if (!capturing && abs(dx) > touchSlop && abs(dx) > abs(dy) * 1.5f) {
                    val wanted = if (dx < 0) onSwipeLeft != null else onSwipeRight != null
                    if (wanted) {
                        capturing = true
                        return true
                    }
                }
            }
        }
        return false
    }

    override fun onTouchEvent(ev: MotionEvent): Boolean {
        // Track our own down point too: when nothing below us claims ACTION_DOWN
        // (e.g. a tap that lands on empty space, not a Button/EditText),
        // Android skips calling onInterceptTouchEvent again for the rest of
        // this gesture and routes everything straight here instead — so
        // `capturing` (set only from onInterceptTouchEvent) never gets set
        // even though we're still the one seeing every event. Decide purely
        // from displacement at the end, regardless of how we got the events.
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = ev.x
                downY = ev.y
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                val dx = ev.x - downX
                val dy = ev.y - downY
                val threshold = touchSlop * 2
                if (abs(dx) >= threshold && abs(dx) > abs(dy) * 1.5f) {
                    if (dx < 0) onSwipeLeft?.invoke() else onSwipeRight?.invoke()
                }
                capturing = false
            }
        }
        return true
    }
}
