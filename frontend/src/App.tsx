import { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { useStore } from '@/store/store';
import { Moon, Sun, TrendingUp, Flame, Trophy, Activity, Zap, Loader2 } from 'lucide-react';

// Lazy load pages for code splitting
const HomePage = lazy(() => import('@/pages/HomePage').then(m => ({ default: m.HomePage })));
const HighTurnoverPage = lazy(() => import('@/pages/HighTurnoverPage').then(m => ({ default: m.HighTurnoverPage })));
const Top20TurnoverLimitUpPage = lazy(() => import('@/pages/Top20TurnoverLimitUpPage').then(m => ({ default: m.Top20TurnoverLimitUpPage })));
const TurnoverFiltersPage = lazy(() => import('@/pages/TurnoverFiltersPage').then(m => ({ default: m.TurnoverFiltersPage })));
const MaBreakoutPage = lazy(() => import('@/pages/MaBreakoutPage').then(m => ({ default: m.MaBreakoutPage })));

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

    return (
        <header className="border-b bg-card sticky top-0 z-50">
            <div className="container mx-auto flex items-center justify-between h-14 px-4">
                <Link to="/" className="flex items-center gap-2 font-bold text-lg">
                    <TrendingUp className="w-6 h-6 text-primary" />
                    TWSE 篩選器
                </Link>
                <nav className="hidden md:flex items-center gap-1">
                    <Button variant="ghost" size="sm" asChild><Link to="/">即時篩選</Link></Button>
                    <Button variant="ghost" size="sm" asChild>
                        <Link to="/top20-limit-up" className="flex items-center gap-1">
                            <Trophy className="w-4 h-4 text-yellow-500" />前200周轉漲停
                        </Link>
                    </Button>
                    <Button variant="ghost" size="sm" asChild>
                        <Link to="/turnover-filters" className="flex items-center gap-1">
                            <Activity className="w-4 h-4 text-blue-500" />篩選器
                        </Link>
                    </Button>
                    <Button variant="ghost" size="sm" asChild>
                        <Link to="/ma-breakout" className="flex items-center gap-1">
                            <Zap className="w-4 h-4 text-purple-500" />均線突破
                        </Link>
                    </Button>
                    <Button variant="ghost" size="sm" asChild>
                        <Link to="/turnover" className="flex items-center gap-1">
                            <Flame className="w-4 h-4 text-orange-500" />高周轉漲停
                        </Link>
                    </Button>
                    <Button variant="ghost" size="sm" asChild><Link to="/batch">批次比對</Link></Button>
                    <Button variant="ghost" size="sm" asChild><Link to="/backtest">回測分析</Link></Button>
                    <Button variant="ghost" size="sm" asChild><Link to="/watchlist">監控清單</Link></Button>
                    <Button variant="ghost" size="sm" asChild><Link to="/history">歷史記錄</Link></Button>
                </nav>
                <Button variant="ghost" size="icon" onClick={toggleTheme}>
                    {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </Button>
            </div>
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
                    <Route path="/top20-limit-up" element={<Top20TurnoverLimitUpPage />} />
                    <Route path="/turnover-filters" element={<TurnoverFiltersPage />} />
                    <Route path="/ma-breakout" element={<MaBreakoutPage />} />
                    <Route path="/turnover" element={<HighTurnoverPage />} />
                    <Route path="/batch" element={<BatchComparePage />} />
                    <Route path="/backtest" element={<BacktestPage />} />
                    <Route path="/watchlist" element={<WatchlistPage />} />
                    <Route path="/history" element={<HistoryPage />} />
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
