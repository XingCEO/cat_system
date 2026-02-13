export interface NormalizedDateInput {
    normalized: string | null;
    wasAdjusted: boolean;
}

function formatIsoDate(year: number, month: number, day: number): string {
    return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function toIsoDateFromDate(d: Date): string {
    return formatIsoDate(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

function normalizeYmd(year: number, month: number, day: number): NormalizedDateInput {
    if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
        return { normalized: null, wasAdjusted: false };
    }
    if (month < 1 || month > 12) {
        return { normalized: null, wasAdjusted: false };
    }

    const lastDay = new Date(year, month, 0).getDate();
    const clampedDay = Math.min(Math.max(day, 1), lastDay);
    const normalized = formatIsoDate(year, month, clampedDay);
    const expected = formatIsoDate(year, month, day);
    return { normalized, wasAdjusted: normalized !== expected };
}

/**
 * Normalize flexible date input.
 * Supports YYYY-MM-DD and YYYY/MM/DD, and clamps invalid day to month end.
 */
export function normalizeFlexibleDateInput(raw: string, nowDate: Date = new Date()): NormalizedDateInput {
    const input = (raw || '').trim();
    if (!input) {
        return { normalized: null, wasAdjusted: false };
    }

    const lowered = input.toLowerCase();
    if (lowered === '今天' || lowered === '今日' || lowered === 'today' || lowered === 'now') {
        return { normalized: toIsoDateFromDate(nowDate), wasAdjusted: false };
    }
    if (lowered === '昨天' || lowered === '昨日' || lowered === 'yesterday') {
        const d = new Date(nowDate);
        d.setDate(d.getDate() - 1);
        return { normalized: toIsoDateFromDate(d), wasAdjusted: false };
    }
    if (lowered === '前天') {
        const d = new Date(nowDate);
        d.setDate(d.getDate() - 2);
        return { normalized: toIsoDateFromDate(d), wasAdjusted: false };
    }

    // YYYY-MM-DD / YYYY/MM/DD
    const match = input.match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/);
    if (match) {
        return normalizeYmd(Number(match[1]), Number(match[2]), Number(match[3]));
    }

    // ROC year, e.g. 114/11/01 -> 2025-11-01
    const roc = input.match(/^(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})$/);
    if (roc) {
        const rocYear = Number(roc[1]);
        const year = rocYear + 1911;
        return normalizeYmd(year, Number(roc[2]), Number(roc[3]));
    }

    // YYYYMMDD
    const yyyymmdd = input.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (yyyymmdd) {
        return normalizeYmd(
            Number(yyyymmdd[1]),
            Number(yyyymmdd[2]),
            Number(yyyymmdd[3]),
        );
    }

    // ROC compact: YYYMMDD (e.g. 1141101 -> 2025-11-01)
    const rocCompact = input.match(/^(\d{3})(\d{2})(\d{2})$/);
    if (rocCompact) {
        return normalizeYmd(
            Number(rocCompact[1]) + 1911,
            Number(rocCompact[2]),
            Number(rocCompact[3]),
        );
    }

    // MM/DD or M/D -> current year
    const short = input.match(/^(\d{1,2})[/-](\d{1,2})$/);
    if (short) {
        return normalizeYmd(nowDate.getFullYear(), Number(short[1]), Number(short[2]));
    }

    // MMDD / MDD -> current year
    const compact = input.match(/^(\d{3,4})$/);
    if (compact) {
        const text = compact[1];
        const monthText = text.length === 3 ? text.slice(0, 1) : text.slice(0, 2);
        const dayText = text.length === 3 ? text.slice(1) : text.slice(2);
        return normalizeYmd(nowDate.getFullYear(), Number(monthText), Number(dayText));
    }

    return { normalized: null, wasAdjusted: false };
}
