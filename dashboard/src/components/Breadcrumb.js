/**
 * AIPI Reusable Breadcrumb Component (ES Module)
 */

import { Icons } from '../icons/index.js';
import { escapeHtml, htmlToElement } from '../utils/dom.js';

export class Breadcrumb {
  constructor(callbacks = {}) {
    this.items = [];
    this.callbacks = callbacks;
  }

  setTrail(items) {
    this.items = items;
  }

  render() {
    const nav = htmlToElement(`
      <nav class="breadcrumbs" aria-label="Breadcrumb">
        ${this.items
          .map((item, index) => {
            const isLast = index === this.items.length - 1;
            const safeLabel = escapeHtml(item.label);
            const content =
              item.id && !isLast
                ? `<button class="breadcrumb-link" data-nav-id="${item.id}">${safeLabel}</button>`
                : `<span class="breadcrumb-item ${isLast ? 'breadcrumb-current' : ''}" ${isLast ? 'aria-current="page"' : ''}>${safeLabel}</span>`;
            const sep = !isLast
              ? `<span class="breadcrumb-separator" aria-hidden="true">${Icons.chevronRight()}</span>`
              : '';
            return `<div class="breadcrumb-node">${content}${sep}</div>`;
          })
          .join('')}
      </nav>
    `);

    const links = nav.querySelectorAll('.breadcrumb-link');
    links.forEach((link) => {
      link.addEventListener('click', () => {
        const id = link.dataset.navId;
        if (id && this.callbacks.onNavigate) {
          this.callbacks.onNavigate(id);
        }
      });
    });

    return nav;
  }
}
