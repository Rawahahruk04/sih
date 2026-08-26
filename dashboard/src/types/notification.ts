/**
 * AIPI Global Notification Layer Types
 */

export type NotificationType = 'success' | 'warning' | 'error' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message?: string;
  durationMs?: number; // 0 or undefined for persistent
  dismissible?: boolean;
}
