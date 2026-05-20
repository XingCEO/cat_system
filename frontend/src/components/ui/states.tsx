/**
 * Shared UI state components — loading, empty, error.
 * Use these across screening pages instead of ad-hoc inline rendering.
 */
import { Loader2, SearchX, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface LoadingStateProps {
    label?: string;
    className?: string;
}

export function LoadingState({ label = '載入中…', className }: LoadingStateProps) {
    return (
        <div className={cn('flex flex-col items-center justify-center py-20 text-muted-foreground gap-3', className)}>
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm animate-pulse">{label}</p>
        </div>
    );
}

interface EmptyStateProps {
    message?: string;
    description?: string;
    className?: string;
}

export function EmptyState({
    message = '無符合條件的股票',
    description = '請調整篩選條件後重新查詢',
    className,
}: EmptyStateProps) {
    return (
        <div className={cn('flex flex-col items-center justify-center py-20 text-muted-foreground gap-3', className)}>
            <SearchX className="w-10 h-10 opacity-30" />
            <p className="text-sm font-medium">{message}</p>
            {description && <p className="text-xs opacity-70">{description}</p>}
        </div>
    );
}

interface ErrorStateProps {
    message?: string;
    onRetry?: () => void;
    className?: string;
}

export function ErrorState({
    message = '載入失敗，請稍後再試',
    onRetry,
    className,
}: ErrorStateProps) {
    return (
        <div className={cn('flex flex-col items-center justify-center py-20 text-muted-foreground gap-3', className)}>
            <AlertCircle className="w-10 h-10 text-destructive/70" />
            <p className="text-sm font-medium text-destructive">{message}</p>
            {onRetry && (
                <Button variant="outline" size="sm" onClick={onRetry}>
                    重新載入
                </Button>
            )}
        </div>
    );
}
