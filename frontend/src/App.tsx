import { useEffect, lazy, Suspense, useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { useStore } from '@/stores/store';
import { Moon, Sun, TrendingUp, Flame, Trophy, Activity, Zap, Loader2, Menu, X, BookMarked, Cat, Target } from 'lucide-react';

// Lazy load pages for code splitting
const HomePage = lazy(() => import('@/pages/HomePage').then(m => ({ default: m.HomePage })));
const HighTurnoverPage = lazy(() => import('@/pages/HighTurnoverPage').then(m => ({ default: m.HighTurnoverPage })));
const Top20TurnoverLimitUpPage = lazy(() => import('@/pages/Top20TurnoverLimitUpPage').then(m => ({ default: m.Top20TurnoverLimitUpPage })));
const TurnoverFiltersPage = lazy(() => import('@/pages/TurnoverFiltersPage').then(m => ({ default: m.TurnoverFiltersPage })));
const MaBreakoutPage = lazy(() => import('@/pages/MaBreakoutPage').then(m => ({ default: m.MaBreakoutPage })));
const TrendScreenPage = lazy(() => import('@/pages/TrendScreenPage').then(m => ({ default: m.TrendScreenPage })));

// Lazy load OtherPages components individually
const BacktestPage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.BacktestPage })));
const WatchlistPage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.WatchlistPage })));
const HistoryPage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.HistoryPage })));
const BatchComparePage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.BatchComparePage })));

// 喵喵選股 v1
const StrategiesPage = lazy(() => import('@/pages/StrategiesPage'));

const queryClient = new QueryClient({
    defaultOptions: {
        queries: { retry: 2, staleTime: 60000 },
    },
});

// Loading fallback component
function PageLoader() {
    return (
        <div className="flex items-center justify-center min-h-[50vh]">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
    );
}

function NavBar() {
    const { theme, toggleTheme } = useStore();
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const location = useLocation();

    // 路由變化時關閉選單
    useEffect(() => {
        setMobileMenuOpen(false);
    }, [location.pathname]);

    const navItems = [
        { to: '/', label: '即時篩選', icon: <TrendingUp className="w-4 h-4" /> },
        { to: '/strategies', label: '策略管理', icon: <BookMarked className="w-4 h-4 text-emerald-500" /> },
        { to: '/top20-limit-up', label: '前200周轉漲停', icon: <Trophy className="w-4 h-4 text-yellow-500" /> },
        { to: '/turnover-filters', label: '篩選器', icon: <Activity className="w-4 h-4 text-blue-500" /> },
        { to: '/ma-breakout', label: '均線突破', icon: <Zap className="w-4 h-4 text-purple-500" /> },
        { to: '/trend-screen', label: '趨勢選股', icon: <Target className="w-4 h-4 text-amber-500" /> },
        { to: '/turnover', label: '高周轉漲停', icon: <Flame className="w-4 h-4 text-orange-500" /> },
        { to: '/batch', label: '批次比對', icon: null },
        { to: '/backtest', label: '回測分析', icon: null },
        { to: '/watchlist', label: '監控清單', icon: null },
        { to: '/history', label: '歷史記錄', icon: null },
    ];

    return (
        <header className="border-b border-border/40 bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
            <div className="container mx-auto flex items-center justify-between h-14 px-4">
                <Link to="/" className="flex items-center gap-2 font-bold text-lg tracking-tight group">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-primary-foreground shadow-sm group-hover:shadow-md transition-shadow">
                        <Cat className="w-5 h-5" />
                    </div>
                    <span className="bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">喵喵選股</span>
                </Link>
                {/* Desktop Nav */}
                <nav className="hidden lg:flex items-center gap-0.5">
                    {navItems.map((item) => {
                        const isActive = location.pathname === item.to;
                        return (
                            <Link
                                key={item.to}
                                to={item.to}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                                    isActive
                                        ? 'bg-primary/10 text-primary shadow-sm'
                                        : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                                }`}
                            >
                                {item.icon}{item.label}
                            </Link>
                        );
                    })}
                </nav>
                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-lg">
                        {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                    </Button>
                    {/* Mobile Menu Button */}
                    <Button
                        variant="ghost"
                        size="icon"
                        className="lg:hidden rounded-lg"
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                        aria-label="開啟選單"
                    >
                        {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                    </Button>
                </div>
            </div>
            {/* Mobile Nav Dropdown */}
            {mobileMenuOpen && (
                <nav className="lg:hidden border-t border-border/40 bg-background/95 backdrop-blur-md">
                    <div className="container mx-auto px-4 py-2 flex flex-col gap-0.5">
                        {navItems.map((item) => (
                            <Link
                                key={item.to}
                                to={item.to}
                                className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors hover:bg-accent ${location.pathname === item.to ? 'bg-primary/10 text-primary' : 'text-foreground'}`}
                            >
                                {item.icon}{item.label}
                            </Link>
                        ))}
                    </div>
                </nav>
            )}
        </header>
    );
}

function AppContent() {
    const { theme } = useStore();

    useEffect(() => {
        document.documentElement.classList.toggle('dark', theme === 'dark');
    }, [theme]);

    return (
        <div className="min-h-screen bg-background">
            <NavBar />
            <Suspense fallback={<PageLoader />}>
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/strategies" element={<StrategiesPage />} />
                    {/* 原有功能 */}
                    <Route path="/top20-limit-up" element={<Top20TurnoverLimitUpPage />} />
                    <Route path="/turnover-filters" element={<TurnoverFiltersPage />} />
                    <Route path="/ma-breakout" element={<MaBreakoutPage />} />
                    <Route path="/trend-screen" element={<TrendScreenPage />} />
                    <Route path="/turnover" element={<HighTurnoverPage />} />
                    <Route path="/batch" element={<BatchComparePage />} />
                    <Route path="/backtest" element={<BacktestPage />} />
                    <Route path="/watchlist" element={<WatchlistPage />} />
                    <Route path="/history" element={<HistoryPage />} />
                    {/* 404 catch-all */}
                    <Route path="*" element={
                        <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
                            <Cat className="w-16 h-16 text-muted-foreground/50 mb-4" />
                            <h2 className="text-xl font-semibold mb-2">找不到此頁面</h2>
                            <p className="text-muted-foreground mb-4">此頁面不存在或已移除</p>
                            <Link to="/" className="text-primary hover:underline">回到首頁</Link>
                        </div>
                    } />
                </Routes>
            </Suspense>
        </div>
    );
}

export default function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <BrowserRouter>
                <AppContent />
            </BrowserRouter>
        </QueryClientProvider>
    );
}
