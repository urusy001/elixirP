import { state } from "../state.js";

/* ---------------- TELEGRAM DETECTION ---------------- */
export function isTelegramApp() {
    const tg = window.Telegram?.WebApp;
    if (!tg) return false;
    const user = tg.initDataUnsafe?.user;
    const hasValidUser = user && typeof user.id === "number";
    const realPlatform = tg.platform && tg.platform !== "unknown";
    return Boolean(hasValidUser && realPlatform);
}

// Module-level variables to track the *currently active* handler
let _mainButtonHandler = null;
let _backButtonHandler = null;

/* ---------------- MAIN BUTTON ---------------- */

/**
 * Shows the Main Button and sets its handler.
 * @returns {Function} A cleanup function to hide the button.
 */
export function showMainButton(text, onClick) {
    const tg = state.telegram;
    if (!isTelegramApp() || !tg?.MainButton) return () => {};

    // 1. Remove the *previous* handler, if one exists
    try {
        if (_mainButtonHandler) {
            tg.offEvent?.("mainButtonClicked", _mainButtonHandler);
        }
    } catch (err) {
        console.warn("[TG] offEvent(mainButtonClicked) failed:", err);
    }

    // 2. Set the new handler and button properties
    _mainButtonHandler = onClick;
    tg.MainButton.setText(text);
    tg.MainButton.show();
    tg.onEvent?.("mainButtonClicked", _mainButtonHandler);

    // 3. Return a cleanup function that only runs if *this*
    //    handler is still the active one.
    return () => {
        if (_mainButtonHandler === onClick) {
            hideMainButton();
        }
    };
}

export function updateMainButton(text, disable, progress) {
    const tg = state.telegram;
    if (!isTelegramApp() || !tg?.MainButton) return;

    // Update text
    if (typeof text === 'string') {
        tg.MainButton.setText(text);
    }

    // Update progress state (must come before disable)
    if (progress === true) {
        tg.MainButton.showProgress();
    } else if (progress === false) {
        tg.MainButton.hideProgress();
    }

    // Update enabled/disabled state
    if (disable === true) {
        tg.MainButton.disable();
    } else if (disable === false) {
        tg.MainButton.enable();
    }
}

/**
 * Hides the Main Button and removes its handler.
 */
export function hideMainButton() {
    const tg = state.telegram;
    if (!isTelegramApp() || !tg?.MainButton) return;

    try {
        if (_mainButtonHandler) {
            tg.offEvent?.("mainButtonClicked", _mainButtonHandler);
        }
    } catch (err) {
        console.warn("[TG] offEvent(mainButtonClicked) cleanup failed:", err);
    }

    tg.MainButton.hide();
    tg.MainButton.hideProgress(); // Also hide progress on cleanup
    tg.MainButton.enable();       // Reset to enabled state
    _mainButtonHandler = null;
}

/* ---------------- BACK BUTTON ---------------- */

/**
 * Shows the Back Button and sets its handler.
 * @returns {Function} A cleanup function to hide the button.
 */
export function showBackButton(onClick) {
    const tg = state.telegram;
    if (!isTelegramApp() || !tg?.BackButton) return () => {};

    // 1. Remove the previous handler
    try {
        if (_backButtonHandler) {
            tg.offEvent?.("backButtonClicked", _backButtonHandler);
        }
    } catch (_) {}

    // 2. Set the new handler
    _backButtonHandler = onClick;
    tg.BackButton.show();
    tg.onEvent?.("backButtonClicked", _backButtonHandler);

    // 3. Return a cleanup function that only cleans up
    //    if this handler is still the active one.
    return () => {
        if (_backButtonHandler === onClick) {
            hideBackButton(); // Use default hide logic
        }
    };
}

/**
 * Hides the Back Button and removes its handler.
 */
export function hideBackButton(showClose = true, onClose = null) {
    const tg = state.telegram;
    if (!isTelegramApp() || !tg?.BackButton) return;

    try {
        if (_backButtonHandler) {
            tg.offEvent?.("backButtonClicked", _backButtonHandler);
        }
    } catch (_) {}

    tg.BackButton.hide();
    _backButtonHandler = null;

    if (showClose) {
        tg.showCloseButton?.();
        if (onClose) tg.onEvent?.("close", onClose);
    }
}