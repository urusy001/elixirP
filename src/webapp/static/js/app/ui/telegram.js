import { state } from "../state.js?v=1";

export function isTelegramApp() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return false;
  const user = tg.initDataUnsafe?.user;
  const hasValidUser = user && typeof user.id === "number";
  const realPlatform = tg.platform && tg.platform !== "unknown";
  return Boolean(hasValidUser && realPlatform);
}

let _lastMainButtonHandler = null;

export function showMainButton(text, onClick) {
  const tg = state.telegram;
  if (!isTelegramApp() || !tg?.MainButton) return () => {};
  try {
    tg.MainButton.offClick?.();
    if (_lastMainButtonHandler) tg.MainButton.offClick(_lastMainButtonHandler);
  } catch (_) {}

  _lastMainButtonHandler = onClick;
  tg.MainButton.setText(text);
  tg.MainButton.onClick(onClick);
  tg.MainButton.show();

  return () => {
    try {
      tg.MainButton.offClick(onClick);
      tg.MainButton.hide();
    } finally {
      if (_lastMainButtonHandler === onClick) _lastMainButtonHandler = null;
    }
  };
}

export function showBackButton(onClick) {
  const tg = state.telegram;
  if (!isTelegramApp() || !tg?.BackButton) return () => {};
  tg.BackButton.show();
  tg.BackButton.offClick?.();
  tg.BackButton.onClick(onClick);
  return () => tg.BackButton.hide();
}

export function updateMainButton(text) {
  const tg = state.telegram;
  if (isTelegramApp()) tg.MainButton.setText(text);
}

export function hideBackButton(showClose = true, onClose = null) {
  const tg = state.telegram;
  if (!isTelegramApp() || !tg?.BackButton) return;
  tg.BackButton.hide();
  if (showClose) {
    tg.showCloseButton?.();
    if (onClose) tg.onEvent?.("close", onClose);
  }
}

export function hideMainButton() {
  state.telegram?.MainButton?.hide?.();
}