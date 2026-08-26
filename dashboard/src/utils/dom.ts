/**
 * AIPI DOM Helper Utilities
 * 
 * Safe HTML node creation, mounting, and attribute management.
 */

export function htmlToElement<T extends HTMLElement = HTMLElement>(html: string): T {
  const template = document.createElement('template');
  template.innerHTML = html.trim();
  return template.content.firstElementChild as T;
}

export function escapeHtml(str: string | null | undefined): string {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
