/**
 * AIPI Reusable Breadcrumb Component
 * 
 * Generates hierarchical navigation trails with responsive truncation,
 * semantic nav landmarks, and keyboard accessibility.
 */

import { Icons } from '../icons/index.js';
import { BreadcrumbItem, NavigationKey } from '../types/navigation.js';
import { htmlToElement } from '../utils/dom.js';

export interface BreadcrumbCallbacks {
  onNavigate?: (id: NavigationKey) => void;
}

export class Breadcrumb {
  private items: BreadcrumbItem[] = [];
  private callbacks: BreadcrumbCallbacks;

  constructor(callbacks: BreadcrumbCallbacks = {}) {
    this.callbacks = callbacks;
  }

  public setTrail(items: BreadcrumbItem[]): void {
    this.items = items;
  }

  public render(): HTMLElement {
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

    const links = nav.querySelectorAll<HTMLButtonElement>('.breadcrumb-link');
    links.forEach((link) => {
      link.addEventListener('click', () => {
        const id = link.dataset.navId as NavigationKey;
        if (id && this.callbacks.onNavigate) {
          this.callbacks.onNavigate(id);
        }
      });
    });

    return nav;
  }
}
