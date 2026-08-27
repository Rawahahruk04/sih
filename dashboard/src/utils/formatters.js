/**
 * AIPI Institutional Formatters (ES Module)
 */

export const fmt = {
  index: (val, decimals = 2) => {
    if (val == null || isNaN(val)) return '—';
    return Number(val).toFixed(decimals);
  },

  signedDelta: (val, unit = 'pts', decimals = 2) => {
    if (val == null || isNaN(val)) return '—';
    const num = Number(val);
    const sign = num >= 0 ? '+' : '';
    const formatted = num.toFixed(decimals);
    return unit === '%' ? `${sign}${formatted}%` : `${sign}${formatted} ${unit}`;
  },

  percent: (val, decimals = 2) => {
    if (val == null || isNaN(val)) return '—';
    return `${Number(val).toFixed(decimals)}%`;
  },

  integer: (val) => {
    if (val == null || isNaN(val)) return '—';
    return Math.round(Number(val)).toLocaleString('en-IN');
  },

  isoDate: (iso) => {
    if (!iso) return '—';
    return String(iso).slice(0, 10);
  },

  hashTruncate: (hash, len = 8) => {
    if (!hash) return '—';
    return String(hash).slice(0, len);
  }
};
