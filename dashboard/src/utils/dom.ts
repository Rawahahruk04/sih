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

export function escapeHtml(str: string): string {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
