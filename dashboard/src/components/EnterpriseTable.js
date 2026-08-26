/**
 * AIPI Reusable Enterprise Table Component (ES Module)
 */

import { escapeHtml, htmlToElement } from '../utils/dom.js';

export class EnterpriseTable {
  constructor() {
    this.sortKey = null;
    this.sortDir = 'asc';
  }

  render(container, props) {
    let filteredData = [...props.data];

    // 1. Search Filter
    if (props.searchQuery && props.searchQuery.trim() !== '') {
      const q = props.searchQuery.toLowerCase().trim();
      const fields = props.searchFields || props.columns.map((c) => c.key);

      filteredData = filteredData.filter((row) =>
        fields.some((f) => {
          const val = row[f];
          return val != null && String(val).toLowerCase().includes(q);
        })
      );
    }

    // 2. Sorting
    if (this.sortKey) {
      const col = props.columns.find((c) => c.key === this.sortKey);
      if (col && col.sortable !== false) {
        filteredData.sort((a, b) => {
          const valA = a[this.sortKey];
          const valB = b[this.sortKey];

          if (valA == null) return 1;
          if (valB == null) return -1;

          if (typeof valA === 'number' && typeof valB === 'number') {
            return this.sortDir === 'asc' ? valA - valB : valB - valA;
          }

          return this.sortDir === 'asc'
            ? String(valA).localeCompare(String(valB))
            : String(valB).localeCompare(String(valA));
        });
      }
    }

    // 3. Render Table HTML
    if (filteredData.length === 0) {
      container.innerHTML = `
        <div class="empty-state-container" style="padding: 32px 16px;">
          <p class="text-body-muted">${props.emptyMessage || 'No matching records found.'}</p>
        </div>
      `;
      return;
    }

    const table = htmlToElement(`
      <div class="enterprise-table-container">
        <table class="enterprise-table" role="table" aria-label="${escapeHtml(props.ariaLabel) || 'Data table'}">
          <thead>
            <tr role="row">
              ${props.columns
                .map((col) => {
                  const isSorted = this.sortKey === col.key;
                  const sortIndicator = isSorted ? (this.sortDir === 'asc' ? ' ▲' : ' ▼') : '';
                  const alignClass = col.align ? `align-${col.align}` : 'align-left';
                  const styleAttr = col.width ? `style="width: ${col.width};"` : '';
                  const ariaSort = col.sortable === false ? '' : isSorted ? `aria-sort="${this.sortDir === 'asc' ? 'ascending' : 'descending'}"` : 'aria-sort="none"';

                  return `
                  <th class="${alignClass} ${col.sortable !== false ? 'sortable' : ''} ${isSorted ? 'sorted' : ''}"
                      data-col-key="${col.key}"
                      ${styleAttr}
                      role="columnheader"
                      ${ariaSort}
                      tabindex="${col.sortable !== false ? '0' : '-1'}">
                    <span>${col.label}</span>
                    <span class="sort-icon">${sortIndicator}</span>
                  </th>
                `;
                })
                .join('')}
            </tr>
          </thead>
          <tbody>
            ${filteredData
              .map((row) => {
                const rowKey = String(row[props.keyField]);
                return `
                <tr class="table-row ${props.onRowClick ? 'clickable' : ''}" data-row-key="${rowKey}" role="row" tabindex="${props.onRowClick ? '0' : '-1'}">
                  ${props.columns
                    .map((col) => {
                      const cellContent = col.render ? col.render(row) : row[col.key] != null ? String(row[col.key]) : '—';
                      const alignClass = col.align ? `align-${col.align}` : 'align-left';
                      return `<td class="${alignClass}" role="cell">${cellContent}</td>`;
                    })
                    .join('')}
                </tr>
              `;
              })
              .join('')}
          </tbody>
        </table>
      </div>
    `);

    // 4. Attach Sort Header Listeners
    const headers = table.querySelectorAll('th.sortable');
    headers.forEach((th) => {
      const handleSort = () => {
        const key = th.dataset.colKey;
        if (!key) return;

        if (this.sortKey === key) {
          this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          this.sortKey = key;
          this.sortDir = 'desc';
        }

        this.render(container, props);
      };

      th.addEventListener('click', handleSort);
      th.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleSort();
        }
      });
    });

    // 5. Attach Row Click Listeners
    if (props.onRowClick) {
      const rows = table.querySelectorAll('.table-row.clickable');
      rows.forEach((r) => {
        const handleRow = () => {
          const key = r.dataset.rowKey;
          const found = props.data.find((d) => String(d[props.keyField]) === key);
          if (found && props.onRowClick) {
            props.onRowClick(found);
          }
        };

        r.addEventListener('click', handleRow);
        r.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleRow();
          }
        });
      });
    }

    container.innerHTML = '';
    container.appendChild(table);
  }
}
