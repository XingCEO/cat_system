import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

/**
 * React Error Boundary - 捕獲子元件渲染錯誤
 * 防止整個應用程式因單一元件錯誤而崩潰
 */
export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = {
            hasError: false,
            error: null,
            errorInfo: null
        };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
        this.setState({ errorInfo });

        // 記錄錯誤到 console（生產環境可改為錯誤追蹤服務）
        console.error('ErrorBoundary caught an error:', error);
        console.error('Component stack:', errorInfo.componentStack);
    }

    handleReset = (): void => {
        this.setState({
            hasError: false,
            error: null,
            errorInfo: null
        });
    };

    handleReload = (): void => {
        window.location.reload();
    };

    render(): ReactNode {
        if (this.state.hasError) {
            // 如果有自定義 fallback，使用它
            if (this.props.fallback) {
                return this.props.fallback;
            }

            // 預設錯誤 UI
            return (
                <div className="min-h-[400px] flex items-center justify-center p-8">
                    <div className="max-w-md w-full text-center space-y-6">
                        <div className="flex justify-center">
                            <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center">
                                <AlertTriangle className="w-8 h-8 text-red-500" />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <h2 className="text-xl font-semibold text-foreground">
                                發生錯誤
                            </h2>
                            <p className="text-muted-foreground">
                                頁面載入時發生問題，請嘗試重新整理或回到首頁。
                            </p>
                        </div>

                        {/* 開發模式顯示錯誤詳情 */}
                        {process.env.NODE_ENV === 'development' && this.state.error && (
                            <div className="text-left bg-muted/50 rounded-lg p-4 text-sm overflow-auto max-h-48">
                                <p className="font-mono text-red-600 dark:text-red-400">
                                    {this.state.error.toString()}
                                </p>
                                {this.state.errorInfo && (
                                    <pre className="mt-2 text-xs text-muted-foreground whitespace-pre-wrap">
                                        {this.state.errorInfo.componentStack}
                                    </pre>
                                )}
                            </div>
                        )}

                        <div className="flex gap-3 justify-center">
                            <Button
                                variant="outline"
                                onClick={this.handleReset}
                            >
                                重試
                            </Button>
                            <Button
                                onClick={this.handleReload}
                            >
                                <RefreshCw className="w-4 h-4 mr-2" />
                                重新整理頁面
                            </Button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

/**
 * 頁面級 Error Boundary - 用於包裹整個頁面
 */
export function PageErrorBoundary({ children }: { children: ReactNode }) {
    return (
        <ErrorBoundary
            fallback={
                <div className="container mx-auto px-4 py-20">
                    <div className="max-w-lg mx-auto text-center space-y-6">
                        <AlertTriangle className="w-16 h-16 text-amber-500 mx-auto" />
                        <h1 className="text-2xl font-bold">頁面載入失敗</h1>
                        <p className="text-muted-foreground">
                            此頁面無法正常載入，請嘗試重新整理。
                        </p>
                        <Button onClick={() => window.location.reload()}>
                            <RefreshCw className="w-4 h-4 mr-2" />
                            重新整理
                        </Button>
                    </div>
                </div>
            }
        >
            {children}
        </ErrorBoundary>
    );
}

export default ErrorBoundary;
