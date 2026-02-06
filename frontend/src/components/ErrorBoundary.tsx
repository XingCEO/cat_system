import React, { Component, ErrorInfo, ReactNode } from 'react';
import { RefreshCw, AlertTriangle } from 'lucide-react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
    };

    public static getDerivedStateFromError(error: Error): State {
        // Update state so the next render will show the fallback UI.
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
    }

    private handleReload = () => {
        window.location.reload();
    };

    public render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100 p-6">
                    <div className="max-w-md w-full text-center space-y-6">
                        <div className="flex justify-center">
                            <div className="p-4 bg-red-100 dark:bg-red-900/30 rounded-full">
                                <AlertTriangle className="w-12 h-12 text-red-600 dark:text-red-400" />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <h1 className="text-2xl font-bold">Oops! Something went wrong</h1>
                            <p className="text-gray-600 dark:text-gray-400">
                                The application encountered an unexpected error.
                            </p>
                        </div>

                        {this.state.error && (
                            <div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-left overflow-auto max-h-40 text-sm font-mono text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
                                {this.state.error.toString()}
                            </div>
                        )}

                        <button
                            onClick={this.handleReload}
                            className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors shadow-sm"
                        >
                            <RefreshCw className="w-5 h-5 mr-2" />
                            Reload Application
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
