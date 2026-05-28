import { derived, writable } from 'svelte/store';
import type { Notification, NotificationLevel, ToastData } from '$lib/types';

export const notifications = writable<Notification[]>([]);
export const toasts = writable<ToastData[]>([]);
export const centerOpen = writable(false);

export const unreadCount = derived(
  notifications,
  ($notifications) => $notifications.filter((notification) => !notification.read).length,
);

export const hasUnreadError = derived(
  notifications,
  ($notifications) => $notifications.some((notification) => !notification.read && notification.level === 'error'),
);

const MAX_NOTIFICATIONS = 50;
const MAX_TOASTS = 5;

const DEFAULT_DURATIONS: Record<NotificationLevel, number> = {
  success: 3000,
  error: 5500,
  warning: 4500,
  info: 3500,
};

interface NotifyOptions {
  href?: string;
  toastDuration?: number;
  toastOnly?: boolean;
}

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function addNotification(
  level: NotificationLevel,
  title: string,
  message: string,
  options: NotifyOptions = {},
): string {
  const id = createId();
  const duration = options.toastDuration ?? DEFAULT_DURATIONS[level];

  if (!options.toastOnly) {
    const notification: Notification = {
      id,
      level,
      title,
      message,
      timestamp: new Date(),
      read: false,
      href: options.href ?? null,
      toastDuration: duration,
    };

    notifications.update((list) => [notification, ...list].slice(0, MAX_NOTIFICATIONS));
  }

  if (duration > 0) {
    const toast: ToastData = {
      id,
      level,
      title,
      message,
      duration,
      exiting: false,
    };

    toasts.update((list) => [...list, toast].slice(-MAX_TOASTS));
    setTimeout(() => dismissToast(id), duration);
  }

  return id;
}

export function dismissToast(id: string): void {
  toasts.update((list) =>
    list.map((toast) => (toast.id === id ? { ...toast, exiting: true } : toast)),
  );

  setTimeout(() => {
    toasts.update((list) => list.filter((toast) => toast.id !== id));
  }, 180);
}

export function markNotificationRead(id: string): void {
  notifications.update((list) =>
    list.map((notification) =>
      notification.id === id ? { ...notification, read: true } : notification,
    ),
  );
}

export function markAllNotificationsRead(): void {
  notifications.update((list) => list.map((notification) => ({ ...notification, read: true })));
}

export function clearNotifications(): void {
  notifications.set([]);
}

export function toggleNotificationCenter(): void {
  centerOpen.update((open) => !open);
}

export const notify = {
  success: (title: string, message: string, options?: NotifyOptions) =>
    addNotification('success', title, message, options),
  error: (title: string, message: string, options?: NotifyOptions) =>
    addNotification('error', title, message, options),
  warning: (title: string, message: string, options?: NotifyOptions) =>
    addNotification('warning', title, message, options),
  info: (title: string, message: string, options?: NotifyOptions) =>
    addNotification('info', title, message, options),
};
