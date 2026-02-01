import { Link } from 'react-router-dom';
import { Home, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

/**
 * 404 錯誤頁面
 */
export function NotFoundPage() {
    return (
        <div className="container mx-auto px-4 py-20">
            <div className="max-w-lg mx-auto text-center space-y-8">
                {/* 404 數字 */}
                <div className="text-9xl font-bold text-muted-foreground/20">
                    404
                </div>

                {/* 訊息 */}
                <div className="space-y-3">
                    <h1 className="text-2xl font-bold text-foreground">
                        找不到頁面
                    </h1>
                    <p className="text-muted-foreground">
                        您要找的頁面不存在或已被移除。
                    </p>
                </div>

                {/* 操作按鈕 */}
                <div className="flex gap-3 justify-center">
                    <Button
                        variant="outline"
                        onClick={() => window.history.back()}
                    >
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        返回上一頁
                    </Button>
                    <Button asChild>
                        <Link to="/">
                            <Home className="w-4 h-4 mr-2" />
                            回到首頁
                        </Link>
                    </Button>
                </div>
            </div>
        </div>
    );
}

export default NotFoundPage;
