export function isTelegramApp() {
    const tg = window.Telegram?.WebApp;
    if (!tg) return false;
    const user = tg.initDataUnsafe?.user;
    const hasValidUser = user && typeof user.id === "number";
    const realPlatform = tg.platform && tg.platform !== "unknown";
    return Boolean(hasValidUser && realPlatform);
}

export function showMainButton(label, onClick) {
    const tg = window.Telegram?.WebApp;
    if (!tg) {
        console.warn("Telegram WebApp not detected");
        return;
    }

    tg.MainButton.setText(label);
    tg.MainButton.show();
    tg.MainButton.enable();

    // prevent duplicate handlers
    tg.offEvent("mainButtonClicked");
    tg.onEvent("mainButtonClicked", async () => {
        try {
            await onClick?.();
        } catch (err) {
            console.error("MainButton handler error:", err);
        }
    });
}

export function hideMainButton() {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;
    tg.offEvent("mainButtonClicked");
    tg.MainButton.hide();
}


/**
 * Show the Telegram WebApp BackButton and attach a click handler.
 * (BackButton has no label/text.)
 *
 * @param {Function} onClick
 */
export function showBackButton(onClick) {
    const tg = window.Telegram?.WebApp;
    if (!tg?.BackButton) {
        console.warn("Telegram WebApp BackButton not available");
        return;
    }

    tg.BackButton.show();

    // avoid stacking duplicate listeners
    tg.offEvent("backButtonClicked");
    tg.onEvent("backButtonClicked", async () => {
        try {
            await onClick?.();
        } catch (err) {
            alert('hahah hahaha')
            console.error("BackButton handler error:", err);
        }
    });
}

/**
 * Hide the BackButton and remove its click handler.
 */
export function hideBackButton() {
    const tg = window.Telegram?.WebApp;
    if (!tg?.BackButton) return;
    tg.offEvent("backButtonClicked");
    tg.BackButton.hide();
}

// ui/telegram-mainbutton-update.js

/**
 * Update Telegram WebApp MainButton state.
 * Does NOT change visibility or click handlers — only updates provided fields.
 *
 * @param {string | undefined} text     - Optional new label (leave undefined to keep current)
 * @param {boolean | undefined} progress - Optional: true=show spinner, false=hide spinner
 * @param {boolean | undefined} disable  - Optional: true=disable button, false=enable button
 */
export function updateMainButton(text, progress= false, disable=false) {
    const tg = window.Telegram?.WebApp;
    if (!tg?.MainButton) {
        console.warn("Telegram WebApp MainButton not available");
        return;
    }

    if (typeof text === "string") {
        tg.MainButton.setText(text);
    }

    if (typeof progress === "boolean") {
        if (progress) tg.MainButton.showProgress();
        else tg.MainButton.hideProgress();
    }

    if (typeof disable === "boolean") {
        if (disable) tg.MainButton.disable();
        else tg.MainButton.enable();
    }
}

export async function showBackButtonSafe(onClick) {
    const tg = window.Telegram?.WebApp;
    if (!tg?.BackButton) return;

    tg.offEvent("backButtonClicked");
    tg.BackButton.show();
    tg.onEvent("backButtonClicked", () => onClick?.());

    // Wait one second before allowing another show
    await new Promise(r => setTimeout(r, 1000));
}
/* Example:
updateMainButton("Checkout", true, true);   // text="Checkout", show spinner, disable
updateMainButton(undefined, false);         // hide spinner, leave text/disabled unchanged
updateMainButton("Pay", undefined, false);  // set text, enable
*/