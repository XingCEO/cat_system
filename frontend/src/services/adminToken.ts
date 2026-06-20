// ===== Admin Token 儲存 =====
// 受 require_admin gate 保護的端點（策略寫入、/api/v1/sync、/api/data/refresh、
// /api/cache/clear）需要帶 X-Admin-Token header。token 存在 localStorage，重整後保留。
//
// 設定方式：
//   1. 策略管理頁的「管理 Token」欄位
//   2. 瀏覽器 console: localStorage.setItem('admin_token', '<token>')
//
// 本機開發若後端設 REQUIRE_ADMIN_TOKEN=false，則完全不需要 token。

const KEY = 'admin_token';

export function getAdminToken(): string {
    try {
        return localStorage.getItem(KEY) ?? '';
    } catch {
        return '';  // localStorage 不可用（隱私模式 / 非瀏覽器環境）
    }
}

export function setAdminToken(token: string): void {
    try {
        if (token) localStorage.setItem(KEY, token);
        else localStorage.removeItem(KEY);
    } catch {
        /* localStorage 不可用，忽略 */
    }
}
