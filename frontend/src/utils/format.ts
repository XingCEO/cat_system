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

// Format volume in lots (張)
export function formatVolume(value?: number | null): string {
    if (value === null || value === undefined) return '-';
    return `${value.toLocaleString('zh-TW')} 張`;
}

// Get color class for change percent
export function getChangeColor(value?: number | null): string {
    if (value === null || value === undefined) return 'text-muted-foreground';
    if (value > 0) return 'text-red-500';
    if (value < 0) return 'text-green-500';
    return 'text-muted-foreground';
}

// Get bg color class for change
export function getChangeBgColor(value?: number | null): string {
    if (value === null || value === undefined) return 'bg-muted';
    if (value > 0) return 'bg-red-500/10';
    if (value < 0) return 'bg-green-500/10';
    return 'bg-muted';
}

// Format date
export function formatDate(date: string | Date): string {
    const d = new Date(date);
    return d.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' });
}
