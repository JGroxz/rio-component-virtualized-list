// VirtualizedList — virtual scroll viewport with absolutely-positioned
// Rio child components and sticky-bottom support.
//
// deltaState keys:
//   children         - ComponentId[]  (Rio children for visible range)
//   rowHeight        - number         (row height in rem)
//   itemCount        - number         (total items)
//   visibleStart     - number         (index of first visible child)
//   autoScrollBottom - boolean        (scroll to bottom after update)
//   debounceMs       - number         (scroll throttle interval ms)
//   fadeDur          - number         (fade animation ms, 0 = disabled)
//   fadeStagger      - number         (stagger delay between items ms)
//
// Messages sent to Python:
//   {type: 'scroll', start: number, end: number}
//   {type: 'auto_follow', enabled: boolean}
//
// Sticky-bottom design:
//   Python decides whether to auto-scroll (autoScrollBottom prop).
//   JS scrolls to bottom on every updateElement when enabled.
//   User scroll-away detected via wheel/touchstart (never fires on
//   programmatic scrollTop changes). _sendRange() always fires —
//   Python-side guards filter during streaming.
//
class _VirtualizedList {
    createElement(context) {
        this._el = document.createElement('div');
        this._el.classList.add('rio-vl');

        this._scroller = document.createElement('div');
        this._scroller.classList.add('rio-vl-scroller');
        this._scroller.classList.add('rio-not-a-child-component');
        this._el.appendChild(this._scroller);

        this._sentinel = document.createElement('div');
        this._sentinel.classList.add('rio-vl-sentinel');
        this._sentinel.classList.add('rio-not-a-child-component');
        this._scroller.appendChild(this._sentinel);

        this._rowHeightPx = 48;
        this._gapPx = 0;
        this._itemCount = 0;
        this._overscan = 5;
        this._visibleStart = -1;
        this._prevVisibleStart = -1;
        this._autoScrollBottom = false;
        this._userDisabledAutoScroll = false;
        this._throttleMs = 80;
        this._fadeDur = 110;
        this._fadeStagger = 18;
        this._lastStart = -1;
        this._lastEnd = -1;
        this._throttleTimer = null;
        this._trailingTimer = null;
        this._userScrollTimer = null;
        this._lastSendTime = 0;
        this._lastScrollToTopSeq = 0;
        this._lastScrollToBottomSeq = 0;

        var self = this;

        // ResizeObserver on sentinel — fires after layout, when
        // scrollHeight is guaranteed to reflect the new sentinel height
        this._resizeObserver = new ResizeObserver(function() {
            if (self._autoScrollBottom) {
                var stride = self._rowHeightPx + self._gapPx;
                var target = self._itemCount * stride - self._gapPx
                    - self._scroller.clientHeight;
                self._scroller.scrollTop = Math.max(0, target);
            }
        });
        this._resizeObserver.observe(this._sentinel);

        // Scroll — throttled range reporting
        this._scroller.addEventListener('scroll', function() {
            var now = Date.now();
            var elapsed = now - self._lastSendTime;
            if (elapsed >= self._throttleMs) {
                self._lastSendTime = now;
                self._sendRange();
            } else if (!self._throttleTimer) {
                self._throttleTimer = setTimeout(function() {
                    self._throttleTimer = null;
                    self._lastSendTime = Date.now();
                    self._sendRange();
                }, self._throttleMs - elapsed);
            }

            clearTimeout(self._trailingTimer);
            self._trailingTimer = setTimeout(function() {
                self._sendRange();
            }, self._throttleMs);
        }, {passive: true});

        // User scroll detection — wheel/touch only fire on real user
        // input, never on programmatic scrollTop changes
        var onUserInput = function() { self._onUserScroll(); };
        this._scroller.addEventListener('wheel', onUserInput, {passive: true});
        this._scroller.addEventListener('touchstart', onUserInput, {passive: true});

        return this._el;
    }

    updateElement(deltaState, context) {
        if (deltaState.rowHeight !== undefined || deltaState.gap !== undefined) {
            var fs = parseFloat(
                getComputedStyle(document.documentElement).fontSize
            ) || 16;
            if (deltaState.rowHeight !== undefined) {
                this._rowHeightPx = deltaState.rowHeight * fs;
            }
            if (deltaState.gap !== undefined) {
                this._gapPx = deltaState.gap * fs;
            }
        }
        if (deltaState.itemCount !== undefined) {
            this._itemCount = deltaState.itemCount;
        }
        if (deltaState.visibleStart !== undefined) {
            this._prevVisibleStart = this._visibleStart;
            this._visibleStart = deltaState.visibleStart;
        }
        if (deltaState.autoScrollBottom !== undefined) {
            if (deltaState.autoScrollBottom) {
                if (!this._userDisabledAutoScroll) {
                    this._autoScrollBottom = true;
                }
            } else {
                this._autoScrollBottom = false;
                this._userDisabledAutoScroll = false;
            }
        }
        if (deltaState.debounceMs !== undefined) {
            this._throttleMs = deltaState.debounceMs;
        }
        if (deltaState.fadeDur !== undefined) {
            this._fadeDur = deltaState.fadeDur;
        }
        if (deltaState.fadeStagger !== undefined) {
            this._fadeStagger = deltaState.fadeStagger;
        }
        if (deltaState.snap !== undefined) {
            this._el.classList.toggle('rio-vl-snap', deltaState.snap);
        }
        if (deltaState.showScrollbar !== undefined) {
            this._scroller.classList.toggle(
                'rio-vl-show-scrollbar', deltaState.showScrollbar
            );
        }

        // Place children
        this.__rioWrapper__.replaceChildren(
            context, deltaState.children, this._scroller, true
        );

        // Position each child wrapper absolutely
        var wrappers = this._scroller.querySelectorAll(
            ':scope > .rio-child-wrapper'
        );
        var rh = this._rowHeightPx;
        var stride = rh + this._gapPx;
        var startIdx = this._visibleStart;
        for (var i = 0; i < wrappers.length; i++) {
            wrappers[i].style.top = ((startIdx + i) * stride) + 'px';
            wrappers[i].style.height = rh + 'px';
        }

        // Sentinel height — last item has no trailing gap
        this._sentinel.style.height =
            (this._itemCount * stride - this._gapPx) + 'px';

        // Scroll commands — counter-based, triggered by button presses
        if (deltaState.scrollToTopSeq !== undefined
            && deltaState.scrollToTopSeq !== this._lastScrollToTopSeq) {
            this._lastScrollToTopSeq = deltaState.scrollToTopSeq;
            this._autoScrollBottom = false;
            this._userDisabledAutoScroll = false;
            this._scroller.scrollTop = 0;
        }
        if (deltaState.scrollToBottomSeq !== undefined
            && deltaState.scrollToBottomSeq !== this._lastScrollToBottomSeq) {
            this._lastScrollToBottomSeq = deltaState.scrollToBottomSeq;
            this._userDisabledAutoScroll = false;
            this._autoScrollBottom = true;
            var stride = this._rowHeightPx + this._gapPx;
            this._scroller.scrollTop = this._itemCount * stride;
        }

        // Auto-scroll handled by ResizeObserver on sentinel

        // Fade-in: only when visibleStart changed and we have a previous
        if (this._fadeDur > 0 && this._prevVisibleStart >= 0
            && this._visibleStart !== this._prevVisibleStart) {
            this._applyFade(wrappers);
        }
    }

    _onUserScroll() {
        clearTimeout(this._userScrollTimer);
        var self = this;
        this._userScrollTimer = setTimeout(function() {
            var atBottom = self._isAtBottom();
            if (self._autoScrollBottom && !atBottom) {
                self._autoScrollBottom = false;
                self._userDisabledAutoScroll = true;
                self.__rioWrapper__.sendMessageToBackend({
                    type: 'auto_follow', enabled: false
                });

                // Immediately report range — _sendRange() is now unguarded
                self._doSendRange();
            } else if (!self._autoScrollBottom && atBottom) {
                self._autoScrollBottom = true;
                self._userDisabledAutoScroll = false;
                self.__rioWrapper__.sendMessageToBackend({
                    type: 'auto_follow', enabled: true
                });
            }
        }, 150);
    }

    _applyFade(wrappers) {
        var oldStart = this._prevVisibleStart;
        var newStart = this._visibleStart;
        var count = wrappers.length;
        var oldEnd = oldStart + count;

        var scrollDown = newStart > oldStart;
        var animName = scrollDown ? 'rio-vl-fade-up' : 'rio-vl-fade-down';
        var dur = this._fadeDur;
        var stagger = this._fadeStagger;

        var newIndices = [];
        for (var i = 0; i < count; i++) {
            var dataIdx = newStart + i;
            if (dataIdx >= oldStart && dataIdx < oldEnd) {
                wrappers[i].style.animation = '';
            } else {
                newIndices.push(i);
            }
        }

        if (!scrollDown) newIndices.reverse();

        for (var j = 0; j < newIndices.length; j++) {
            var w = wrappers[newIndices[j]];
            w.style.animation = 'none';
            void w.offsetHeight;
            w.style.animation = animName + ' ' + dur + 'ms ease-out '
                + (j * stagger) + 'ms both';
        }
    }

    _isAtBottom() {
        var s = this._scroller;
        var stride = this._rowHeightPx + this._gapPx;
        var totalHeight = this._itemCount * stride - this._gapPx;
        return s.scrollTop + s.clientHeight >= totalHeight - 15;
    }

    _sendRange() {
        // During auto-scroll, Python controls the window — suppress
        // range reports from programmatic scrollTop changes
        if (this._autoScrollBottom) return;
        this._doSendRange();
    }

    _doSendRange() {
        var stride = this._rowHeightPx + this._gapPx;
        if (stride <= 0) return;
        var top = this._scroller.scrollTop;
        var vh = this._scroller.clientHeight;
        if (vh <= 0) return;
        var os = this._overscan;
        var s = Math.max(0, Math.floor(top / stride) - os);
        var e = Math.min(
            this._itemCount,
            Math.ceil((top + vh) / stride) + os
        );
        if (s !== this._lastStart || e !== this._lastEnd) {
            this._lastStart = s;
            this._lastEnd = e;
            this.__rioWrapper__.sendMessageToBackend({
                type: 'scroll', start: s, end: e
            });
        }
    }

    deconstruct() {
        clearTimeout(this._throttleTimer);
        clearTimeout(this._trailingTimer);
        clearTimeout(this._userScrollTimer);
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
        }
    }
}
