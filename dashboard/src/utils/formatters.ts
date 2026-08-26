/**
 * AIPI Institutional Formatters
 * 
 * Strict formatting utilities adhering to FDS typographic standards and tabular numerals.
 */

export const fmt = {
  /**
   * Format index points to 1 or 2 decimals (e.g. 104.5 or 104.52)
   */
  index: (val: number | null | undefined, decimals = 2): string => {
    if (val == null || isNaN(val)) return '—';
    return val.toFixed(decimals);
  },

  /**
   * Format signed deltas with + / - (e.g. +4.52 pts)
   */
  signedDelta: (val: number | null | undefined, unit = 'pts', decimals = 2): string => {
    if (val == null || isNaN(val)) return '—';
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toFixed(decimals)} ${unit}`;
  },

  /**
   * Format percentages (e.g. 94.70%)
   */
  percent: (val: number | null | undefined, decimals = 2): string => {
    if (val == null || isNaN(val)) return '—';
    return `${val.toFixed(decimals)}%`;
  },

  /**
   * Format integer quantities with thousands commas (e.g. 21,035)
   */
  integer: (val: number | null | undefined): string => {
    if (val == null || isNaN(val)) return '—';
    return Math.round(val).toLocaleString('en-IN');
  },

  /**
   * Format ISO date string into standard institutional format (e.g. 2026-08-14)
   */
  isoDate: (iso: string | null | undefined): string => {
    if (!iso) return '—';
    return iso.slice(0, 10);
  },

  /**
   * Truncate Git commit SHA or Config Hash with monospace display
   */
  hashTruncate: (hash: string | null | undefined, len = 8): string => {
    if (!hash) return '—';
    return hash.slice(0, len);
  }
};
