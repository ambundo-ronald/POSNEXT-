/**
 * reka-ui's DialogOverlay calls preventDefault() on every left pointerdown it
 * receives. frappe-ui renders DialogContent *inside* that overlay, so presses
 * on inputs inside any Dialog are cancelled too: the browser then skips the
 * mousedown that focuses the field, and the field cannot be typed into.
 *
 * For presses that start inside dialog content, neutralise preventDefault on
 * that one event before it bubbles up to the overlay. Presses on the backdrop
 * itself keep reka-ui's behaviour.
 */
const FIELD_SELECTOR = "input, textarea, select, [contenteditable=''], [contenteditable='true']"

export function installDialogPointerFix() {
	if (typeof window === "undefined" || window.__posDialogPointerFix) return
	window.__posDialogPointerFix = true

	window.addEventListener(
		"pointerdown",
		(event) => {
			const target = event.target
			if (!(target instanceof Element)) return
			// Only typing fields; other widgets may rely on preventDefault
			if (!target.closest(FIELD_SELECTOR)) return
			if (!target.closest(".dialog-content")) return
			// Shadow the prototype method on this event instance only
			Object.defineProperty(event, "preventDefault", {
				value: () => {},
				configurable: true,
			})
		},
		{ capture: true },
	)
}
