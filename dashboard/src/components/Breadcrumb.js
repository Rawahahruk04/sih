/**
 * AIPI Reusable Breadcrumb Component (ES Module)
 */

import { Icons } from '../icons/index.js';
import { htmlToElement } from '../utils/dom.js';

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
            if (isLast || !item.id) {
              return `<span class="breadcrumb-item ${isLast ? 'breadcrumb-current' : ''}" ${isLast ? 'aria-current="page"' : ''}>${item.label}</span>`;
            }
            return `
              <button class="breadcrumb-link" data-nav-id="${item.id}">${item.label}</button>
              ${Icons.chevronRight()}
            `;
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
