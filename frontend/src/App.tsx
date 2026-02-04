import { useEffect, lazy, Suspense, useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { useStore } from '@/store/store';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Moon, Sun, Cat, Flame, Trophy, Activity, Zap, Loader2, Menu, X, TrendingUp } from 'lucide-react';

// Lazy load pages for code splitting
const HomePage = lazy(() => import('@/pages/HomePage').then(m => ({ default: m.HomePage })));
const HighTurnoverPage = lazy(() => import('@/pages/HighTurnoverPage').then(m => ({ default: m.HighTurnoverPage })));
const Top20TurnoverLimitUpPage = lazy(() => import('@/pages/Top20TurnoverLimitUpPage').then(m => ({ default: m.Top20TurnoverLimitUpPage })));
const TurnoverFiltersPage = lazy(() => import('@/pages/TurnoverFiltersPage').then(m => ({ default: m.TurnoverFiltersPage })));
const MaBreakoutPage = lazy(() => import('@/pages/MaBreakoutPage').then(m => ({ default: m.MaBreakoutPage })));
const MaStrategyPage = lazy(() => import('@/pages/MaStrategyPage'));
const RealtimeMonitorPage = lazy(() => import('@/pages/RealtimeMonitorPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));

// Lazy load OtherPages components individually
const BacktestPage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.BacktestPage })));
const WatchlistPage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.WatchlistPage })));
const HistoryPage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.HistoryPage })));
const BatchComparePage = lazy(() => import('@/pages/OtherPages').then(m => ({ default: m.BatchComparePage })));

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
        { to: '/', label: '即時篩選', icon: null },
        { to: '/realtime', label: '盤中監控', icon: <Zap className="w-4 h-4 text-amber-500" /> },
        { to: '/top20-limit-up', label: '前200周轉漲停', icon: <Trophy className="w-4 h-4 text-amber-500" /> },
        { to: '/turnover-filters', label: '篩選器', icon: <Activity className="w-4 h-4 text-blue-500" /> },
        { to: '/ma-breakout', label: '均線突破', icon: <Zap className="w-4 h-4 text-violet-500" /> },
        { to: '/ma-strategy', label: '均線策略', icon: <TrendingUp className="w-4 h-4 text-green-500" /> },
        { to: '/turnover', label: '高周轉漲停', icon: <Flame className="w-4 h-4 text-orange-500" /> },
        { to: '/batch', label: '批次比對', icon: null },
        { to: '/backtest', label: '回測分析', icon: null },
        { to: '/watchlist', label: '監控清單', icon: null },
        { to: '/history', label: '歷史記錄', icon: null },
    ];

    const isActive = (path: string) => location.pathname === path;

    return (
        <header className="sticky top-0 z-50 w-full">
            {/* 主導航 - 玻璃態效果 */}
            <div className="mx-0 mt-0 border-b border-border/50 bg-card/80 backdrop-blur-xl shadow-lg dark:bg-card/60 dark:border-border/30">
                <div className="container mx-auto flex items-center justify-between h-14 px-4">
                    <Link to="/" className="flex items-center gap-2.5 font-bold text-lg group">
                        <div className="p-1.5 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                            <Cat className="w-5 h-5 text-primary" />
                        </div>
                        <span className="hidden sm:inline bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">
                            TWSE 篩選器
                        </span>
                    </Link>

                    {/* Desktop Nav */}
                    <nav className="hidden lg:flex items-center gap-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.to}
                                to={item.to}
                                className={`
                                    nav-item flex items-center gap-1.5 cursor-pointer
                                    ${isActive(item.to) ? 'active' : ''}
                                `}
                            >
                                {item.icon}
                                <span>{item.label}</span>
                            </Link>
                        ))}
                    </nav>

                    <div className="flex items-center gap-2">
                        {/* Theme Toggle */}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={toggleTheme}
                            className="rounded-xl hover:bg-muted"
                        >
                            {theme === 'dark' ? (
                                <Sun className="w-5 h-5 text-amber-500" />
                            ) : (
                                <Moon className="w-5 h-5 text-slate-600" />
                            )}
                        </Button>

                        {/* Mobile Menu Button */}
                        <Button
                            variant="ghost"
                            size="icon"
                            className="lg:hidden rounded-xl hover:bg-muted"
                            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                            aria-label="開啟選單"
                        >
                            {mobileMenuOpen ? (
                                <X className="w-5 h-5" />
                            ) : (
                                <Menu className="w-5 h-5" />
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Mobile Nav Dropdown */}
            {mobileMenuOpen && (
                <div className="lg:hidden mx-4 mt-2 rounded-xl border border-border/50 bg-card/95 backdrop-blur-xl shadow-lg animate-fade-in">
                    <nav className="p-2 flex flex-col gap-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.to}
                                to={item.to}
                                className={`
                                    flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm font-medium
                                    transition-all duration-200 cursor-pointer
                                    ${isActive(item.to)
                                        ? 'bg-primary/10 text-primary'
                                        : 'text-foreground hover:bg-muted'
                                    }
                                `}
                            >
                                {item.icon}
                                <span>{item.label}</span>
                            </Link>
                        ))}
                    </nav>
                </div>
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
            <ErrorBoundary>
                <Suspense fallback={<PageLoader />}>
                    <Routes>
                        <Route path="/" element={<HomePage />} />
                        <Route path="/top20-limit-up" element={<Top20TurnoverLimitUpPage />} />
                        <Route path="/turnover-filters" element={<TurnoverFiltersPage />} />
                        <Route path="/ma-breakout" element={<MaBreakoutPage />} />
                        <Route path="/ma-strategy" element={<MaStrategyPage />} />
                        <Route path="/realtime" element={<RealtimeMonitorPage />} />
                        <Route path="/turnover" element={<HighTurnoverPage />} />
                        <Route path="/batch" element={<BatchComparePage />} />
                        <Route path="/backtest" element={<BacktestPage />} />
                        <Route path="/watchlist" element={<WatchlistPage />} />
                        <Route path="/history" element={<HistoryPage />} />
                        <Route path="*" element={<NotFoundPage />} />
                    </Routes>
                </Suspense>
            </ErrorBoundary>
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
