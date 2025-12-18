import {state} from "../state.js";
import {navigateTo} from "../router.js";
import {getCurrentPathFromHash, updateBottomNavActive} from "./nav-bottom.js";

/* ---------------- TELEGRAM DETECTION ---------------- */
const tg = state.telegram
export function isTelegramApp() {
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
    if (!isTelegramApp() || !tg?.MainButton) return () => {
    };

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
    tg.MainButton.hideProgress();
    tg.MainButton.enable();
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


export function hideBackButton() {
    if (!isTelegramApp() || !tg?.BackButton) return;

    try {
        if (_backButtonHandler) {
            tg.offEvent?.("backButtonClicked", _backButtonHandler);
        }
    } catch (_) {
    }

    _backButtonHandler = null;
    tg.BackButton.hide();
}

export function showBackButton(onClick) { // keep param, do not use it
    if (!isTelegramApp() || !tg?.BackButton) return () => {
    };

    try {
        if (_backButtonHandler) tg.offEvent?.("backButtonClicked", _backButtonHandler);
    } catch (_) {
    }

    const handler = () => {
        if (window.history.length > 1) {
            window.history.back();
            setTimeout(() => {
                const path = getCurrentPathFromHash();
                updateBottomNavActive(path);
                if (path.includes("checkout")) {
                    hideMainButton();
                }
            }, 0);
        } else navigateTo("/")
    };

    _backButtonHandler = onClick || handler;
    tg.BackButton.show();
    tg.onEvent?.("backButtonClicked", _backButtonHandler);

    return () => {
        if (_backButtonHandler === handler) {
            hideBackButton();
        }
    };
}

export function openTgLink(pathFull) {
    const mobileData = JSON.stringify({ path_full: pathFull });
    const webData = JSON.stringify({
        eventType: 'web_app_open_tg_link',
        eventData: { path_full: pathFull },
    });

    // Desktop / mobile Telegram apps
    if (window.TelegramWebviewProxy && typeof window.TelegramWebviewProxy.postEvent === 'function') {
        window.TelegramWebviewProxy.postEvent('web_app_open_tg_link', mobileData);

        // Web Telegram (Mini App in iframe)
    } else if (window.parent) {
        window.parent.postMessage(webData, 'https://web.telegram.org');
    }
}

export function launchConfettiBurst() {
    if (typeof confetti !== 'function') return;

    // simple “yay” burst
    confetti({
        particleCount: 140,
        spread: 70,
        startVelocity: 45,
        origin: { y: 0.6 }
    });

    // second burst for a richer feel
    setTimeout(() => {
        confetti({
            particleCount: 100,
            spread: 100,
            startVelocity: 35,
            origin: { y: 0.4 }
        });
    }, 250);

    // optional haptic feedback in Telegram
    try {
        window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('rigid');
    } catch (_) {}
}
