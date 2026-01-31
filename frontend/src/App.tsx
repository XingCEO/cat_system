import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HomePage } from '@/pages/HomePage';
import { BacktestPage, WatchlistPage, HistoryPage, BatchComparePage } from '@/pages/OtherPages';
import { HighTurnoverPage } from '@/pages/HighTurnoverPage';
import { Top20TurnoverLimitUpPage } from '@/pages/Top20TurnoverLimitUpPage';
import { TurnoverFiltersPage } from '@/pages/TurnoverFiltersPage';
import { MaBreakoutPage } from '@/pages/MaBreakoutPage';
import { Button } from '@/components/ui/button';
import { useStore } from '@/store/store';
import { Moon, Sun, TrendingUp, Flame, Trophy, Activity, Zap } from 'lucide-react';

const queryClient = new QueryClient({
    defaultOptions: {
        queries: { retry: 2, staleTime: 60000 },
    },
});

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

