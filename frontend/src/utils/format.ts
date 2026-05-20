// Format number with % sign
export function formatPercent(value?: number | null, decimals = 2): string {
    if (value === null || value === undefined) return '-';
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;
}

// Format number with thousand separators
export function formatNumber(value?: number | null): string {
    if (value === null || value === undefined) return '-';
    return value.toLocaleString('zh-TW');
}

// Format price
export function formatPrice(value?: number | null): string {
    if (value === null || value === undefined) return '-';
    return value.toFixed(2);
}

// Get color class for change percent.
// Taiwan convention: up = red (chartUp token), down = green (chartDown token).
// Uses Tailwind theme tokens defined in tailwind.config.js via CSS variables.
export function getChangeColor(value?: number | null): string {
    if (value === null || value === undefined) return 'text-muted-foreground';
    if (value > 0) return 'text-chartUp';
    if (value < 0) return 'text-chartDown';
    return 'text-muted-foreground';
}

/**
 * 取得本地日期字串 YYYY-MM-DD（避免 toISOString 的 UTC 時差問題）
 */
export function toLocalDateStr(d: Date = new Date()): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}
