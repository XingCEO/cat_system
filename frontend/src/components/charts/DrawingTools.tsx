/**
 * K線圖專業繪圖工具 - 圖表座標版
 *
 * 設計原則：
 * 1. 使用圖表座標（logicalIndex + price），繪圖跟隨K線圖移動
 * 2. 正常模式：不攔截任何事件，K線圖完全正常運作
 * 3. 選擇模式：攔截事件，可點選繪圖進行刪除
 * 4. 繪圖模式：攔截事件，可繪製新圖形
 */
import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import {
    MousePointer, X, Trash2, TrendingUp, Minus, ArrowRight,
    MoveHorizontal, MoveVertical, GitBranch, BarChart3, Square, Type, Hand
} from 'lucide-react';

export type DrawingType =
    | 'off'            // 正常模式（不攔截事件，K線圖正常運作）
    | 'select'         // 選擇模式（可選取繪圖刪除）
    | 'trendline'      // 趨勢線（延伸至邊界）
    | 'segment'        // 線段（兩點之間）
    | 'ray'            // 射線（單向延伸）
    | 'horizontal'     // 水平線
    | 'vertical'       // 垂直線
    | 'parallel'       // 平行通道
    | 'fibonacci'      // 斐波那契回調
    | 'golden'         // 黃金分割率
    | 'rectangle'      // 矩形區域
    | 'text';          // 文字標註

// 圖表座標點（跟隨K線移動）
interface ChartPoint {
    logicalIndex: number;  // K線邏輯索引
    price: number;         // 價格
}

export interface DrawingObject {
    id: string;
    type: DrawingType;
    points: ChartPoint[];  // 圖表座標
    color: string;
    text?: string;
}

interface DrawingToolsProps {
    activeType: DrawingType;
    onTypeChange: (type: DrawingType) => void;
    drawingCount?: number;
}

const DRAWING_TOOLS: { type: DrawingType; label: string; icon: React.ReactNode }[] = [
    { type: 'trendline', label: '趨勢線', icon: <TrendingUp className="h-3.5 w-3.5" /> },
    { type: 'segment', label: '線段', icon: <Minus className="h-3.5 w-3.5" /> },
    { type: 'ray', label: '射線', icon: <ArrowRight className="h-3.5 w-3.5" /> },
    { type: 'horizontal', label: '水平', icon: <MoveHorizontal className="h-3.5 w-3.5" /> },
    { type: 'vertical', label: '垂直', icon: <MoveVertical className="h-3.5 w-3.5" /> },
    { type: 'parallel', label: '通道', icon: <GitBranch className="h-3.5 w-3.5" /> },
    { type: 'fibonacci', label: '斐波那契', icon: <BarChart3 className="h-3.5 w-3.5" /> },
    { type: 'golden', label: '黃金分割', icon: <BarChart3 className="h-3.5 w-3.5" /> },
    { type: 'rectangle', label: '矩形', icon: <Square className="h-3.5 w-3.5" /> },
    { type: 'text', label: '文字', icon: <Type className="h-3.5 w-3.5" /> },
];

const COLORS = [
    '#ef4444', '#f97316', '#eab308', '#22c55e',
    '#3b82f6', '#8b5cf6', '#ec4899', '#64748b',
];

export function DrawingToolbar({ activeType, onTypeChange, drawingCount = 0 }: DrawingToolsProps) {
    return (
        <div className="flex items-center gap-0.5 flex-wrap">
            {/* 正常模式（預設） */}
            <Button
                variant={activeType === 'off' ? 'default' : 'ghost'}
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => onTypeChange('off')}
                title="正常模式（可拖曳/十字軸）"
            >
                <Hand className="h-3.5 w-3.5" />
            </Button>

            {/* 選擇模式（有繪圖時才顯示） */}
            {drawingCount > 0 && (
                <Button
                    variant={activeType === 'select' ? 'default' : 'ghost'}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => onTypeChange('select')}
                    title="選擇模式（點選繪圖刪除）"
                >
                    <MousePointer className="h-3.5 w-3.5" />
                    <span className="ml-0.5 text-[10px] bg-muted px-1 rounded">{drawingCount}</span>
                </Button>
            )}

            <div className="w-px h-5 bg-border mx-0.5" />

            {/* 繪圖工具橫排按鈕 */}
            {DRAWING_TOOLS.map(tool => (
                <Button
                    key={tool.type}
                    variant={activeType === tool.type ? 'default' : 'ghost'}
                    size="sm"
                    className="h-7 px-1.5 text-xs"
                    onClick={() => onTypeChange(tool.type)}
                    title={tool.label}
                >
                    {tool.icon}
                    <span className="ml-0.5 hidden sm:inline">{tool.label}</span>
                </Button>
            ))}
        </div>
    );
}

interface DrawingCanvasProps {
    width: number;
    height: number;
    drawings: DrawingObject[];
    activeType: DrawingType;
    selectedId: string | null;
    onAddDrawing: (drawing: DrawingObject) => void;
    onSelectDrawing: (id: string | null) => void;
    onDeleteDrawing: (id: string) => void;
    // 圖表相關 - 用於座標轉換
    chart: IChartApi | null;
    mainSeries: ISeriesApi<'Candlestick'> | null;
}

export function DrawingCanvas({
    width,
    height,
    drawings,
    activeType,
    selectedId,
    onAddDrawing,
    onSelectDrawing,
    onDeleteDrawing,
    chart,
    mainSeries,
}: DrawingCanvasProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const rafRef = useRef<number>(0);

    // 使用 ref 保存最新的 chart/mainSeries
    const chartRef = useRef(chart);
    const seriesRef = useRef(mainSeries);
    useEffect(() => {
        chartRef.current = chart;
        seriesRef.current = mainSeries;
    }, [chart, mainSeries]);

    // 繪製狀態（像素座標，僅用於繪製過程）
    const [isDrawing, setIsDrawing] = useState(false);
    const [startPixel, setStartPixel] = useState<{ x: number; y: number } | null>(null);
    const [currentPixel, setCurrentPixel] = useState<{ x: number; y: number } | null>(null);
    const [thirdPixel, setThirdPixel] = useState<{ x: number; y: number } | null>(null);
    const [drawStep, setDrawStep] = useState(0);

    // 文字輸入
    const [textInput, setTextInput] = useState<{ x: number; y: number; show: boolean }>({ x: 0, y: 0, show: false });
    const [textValue, setTextValue] = useState('');

    // 當前顏色
    const currentColorRef = useRef(COLORS[0]);

    // 重繪觸發器
    const [redrawTrigger, setRedrawTrigger] = useState(0);

    // 模式判斷
    const isNormalMode = activeType === 'off';
    const isSelectMode = activeType === 'select';
    const isDrawingMode = !isNormalMode && !isSelectMode;

    // ========== 座標轉換 ==========

    // 像素座標 → 圖表座標
    const pixelToChart = useCallback((pixel: { x: number; y: number }): ChartPoint | null => {
        const c = chartRef.current;
        const s = seriesRef.current;
        if (!c || !s) return null;

        try {
            const timeScale = c.timeScale();
            const logicalIndex = timeScale.coordinateToLogical(pixel.x);
            const price = s.coordinateToPrice(pixel.y);
            if (logicalIndex === null || price === null) return null;
            return { logicalIndex, price };
        } catch {
            return null;
        }
    }, []);

    // 圖表座標 → 像素座標
    const chartToPixel = useCallback((point: ChartPoint): { x: number; y: number } | null => {
        const c = chartRef.current;
        const s = seriesRef.current;
        if (!c || !s) return null;

        try {
            const timeScale = c.timeScale();
            const x = timeScale.logicalToCoordinate(point.logicalIndex as unknown as import('lightweight-charts').Logical);
            const y = s.priceToCoordinate(point.price);
            if (x === null || y === null) return null;
            return { x, y };
        } catch {
            return null;
        }
    }, []);

    // 監聽圖表範圍變化，觸發重繪
    useEffect(() => {
        if (!chart) return;

        const handleRangeChange = () => {
            setRedrawTrigger(t => t + 1);
        };

        chart.timeScale().subscribeVisibleLogicalRangeChange(handleRangeChange);

        return () => {
            chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleRangeChange);
        };
    }, [chart]);

    // 計算選中繪圖的刪除按鈕位置
    const deleteButtonPos = useMemo(() => {
        if (!selectedId) return null;
        const drawing = drawings.find(d => d.id === selectedId);
        if (!drawing || drawing.points.length === 0) return null;

        // 將第一個點轉為像素座標
        const p0 = chartToPixel(drawing.points[0]);
        if (!p0) return null;

        let x = p0.x;
        let y = p0.y;

        if (drawing.type === 'horizontal') {
            x = width / 2;
        } else if (drawing.type === 'vertical') {
            y = height / 2;
        } else if (drawing.points.length >= 2) {
            const p1 = chartToPixel(drawing.points[1]);
            if (p1) {
                x = (p0.x + p1.x) / 2;
                y = (p0.y + p1.y) / 2;
            }
        }

        x = Math.max(50, Math.min(width - 50, x));
        y = Math.max(25, Math.min(height - 25, y));

        return { x, y };
    }, [selectedId, drawings, width, height, chartToPixel, redrawTrigger]);

    // ========== 繪圖輔助函數 ==========

    const distance = useCallback((p1: { x: number; y: number }, p2: { x: number; y: number }) => {
        return Math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2);
    }, []);

    const isPointNearLine = useCallback((point: { x: number; y: number }, p1: { x: number; y: number }, p2: { x: number; y: number }, threshold = 10) => {
        const len = distance(p1, p2);
        if (len === 0) return distance(point, p1) < threshold;
        const t = Math.max(0, Math.min(1, ((point.x - p1.x) * (p2.x - p1.x) + (point.y - p1.y) * (p2.y - p1.y)) / (len * len)));
        const projection = { x: p1.x + t * (p2.x - p1.x), y: p1.y + t * (p2.y - p1.y) };
        return distance(point, projection) < threshold;
    }, [distance]);

    const drawLine = useCallback((ctx: CanvasRenderingContext2D, p1: { x: number; y: number }, p2: { x: number; y: number }, extend: 'none' | 'both' | 'end' = 'none') => {
        ctx.beginPath();
        if (extend === 'none') {
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
        } else {
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const len = Math.sqrt(dx * dx + dy * dy);
            if (len === 0) return;
            const ux = dx / len, uy = dy / len;

            const extendToEdge = (px: number, py: number, dirX: number, dirY: number) => {
                let t = Infinity;
                if (dirX > 0) t = Math.min(t, (width - px) / dirX);
                if (dirX < 0) t = Math.min(t, -px / dirX);
                if (dirY > 0) t = Math.min(t, (height - py) / dirY);
                if (dirY < 0) t = Math.min(t, -py / dirY);
                return { x: px + dirX * t, y: py + dirY * t };
            };

            if (extend === 'both') {
                const start = extendToEdge(p1.x, p1.y, -ux, -uy);
                const end = extendToEdge(p2.x, p2.y, ux, uy);
                ctx.moveTo(start.x, start.y);
                ctx.lineTo(end.x, end.y);
            } else {
                const end = extendToEdge(p2.x, p2.y, ux, uy);
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(end.x, end.y);
            }
        }
        ctx.stroke();
    }, [width, height]);

    const drawFibonacci = useCallback((ctx: CanvasRenderingContext2D, p1: { x: number; y: number }, p2: { x: number; y: number }, selected: boolean) => {
        const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
        const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6', '#ef4444'];
        const minX = Math.min(p1.x, p2.x), maxX = Math.max(p1.x, p2.x);

        levels.forEach((level, i) => {
            const y = p1.y + (p2.y - p1.y) * level;
            ctx.strokeStyle = selected ? '#fff' : colors[i];
            ctx.lineWidth = 1.5;
            ctx.setLineDash([5, 3]);
            ctx.beginPath();
            ctx.moveTo(minX, y);
            ctx.lineTo(maxX, y);
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.font = '10px sans-serif';
            ctx.fillStyle = selected ? '#fff' : colors[i];
            ctx.fillText(`${(level * 100).toFixed(1)}%`, maxX + 5, y + 3);
        });
    }, []);

    const drawGoldenRatio = useCallback((ctx: CanvasRenderingContext2D, p1: { x: number; y: number }, p2: { x: number; y: number }, selected: boolean) => {
        const levels = [0, 0.382, 0.5, 0.618, 1];
        const labels = ['0%', '38.2%', '50%', '61.8%', '100%'];
        const colors = ['#ef4444', '#ffc107', '#22c55e', '#3b82f6', '#ef4444'];
        const minX = Math.min(p1.x, p2.x), maxX = Math.max(p1.x, p2.x);

        levels.forEach((level, i) => {
            const y = p1.y + (p2.y - p1.y) * level;
            ctx.strokeStyle = selected ? '#fff' : colors[i];
            ctx.lineWidth = level === 0.618 ? 2.5 : 1.5;
            ctx.setLineDash(level === 0.5 ? [5, 3] : []);
            ctx.beginPath();
            ctx.moveTo(minX, y);
            ctx.lineTo(maxX, y);
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.font = level === 0.618 ? 'bold 11px sans-serif' : '10px sans-serif';
            ctx.fillStyle = selected ? '#fff' : colors[i];
            ctx.fillText(labels[i] + (level === 0.618 ? ' ★' : ''), maxX + 5, y + 3);
        });

        const y382 = p1.y + (p2.y - p1.y) * 0.382;
        const y618 = p1.y + (p2.y - p1.y) * 0.618;
        ctx.fillStyle = (selected ? '#ffffff' : '#ffc107') + '15';
        ctx.fillRect(minX, Math.min(y382, y618), maxX - minX, Math.abs(y618 - y382));
    }, []);

    // ========== Canvas 重繪 ==========

    const redraw = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.clearRect(0, 0, width, height);

        // 繪製已保存的圖形（使用圖表座標轉換）
        for (const drawing of drawings) {
            // 將圖表座標轉為像素座標
            const pixelPoints = drawing.points.map(p => chartToPixel(p)).filter((p): p is { x: number; y: number } => p !== null);
            if (pixelPoints.length === 0) continue;

            const isSelected = drawing.id === selectedId;
            ctx.strokeStyle = isSelected ? '#ffffff' : drawing.color;
            ctx.fillStyle = isSelected ? '#ffffff' : drawing.color;
            ctx.lineWidth = isSelected ? 2.5 : 2;
            ctx.setLineDash([]);

            switch (drawing.type) {
                case 'trendline':
                    if (pixelPoints.length >= 2) {
                        drawLine(ctx, pixelPoints[0], pixelPoints[1], 'both');
                        [0, 1].forEach(i => {
                            ctx.beginPath();
                            ctx.arc(pixelPoints[i].x, pixelPoints[i].y, isSelected ? 5 : 4, 0, Math.PI * 2);
                            ctx.fill();
                        });
                    }
                    break;
                case 'segment':
                    if (pixelPoints.length >= 2) {
                        drawLine(ctx, pixelPoints[0], pixelPoints[1], 'none');
                        [0, 1].forEach(i => {
                            ctx.beginPath();
                            ctx.arc(pixelPoints[i].x, pixelPoints[i].y, isSelected ? 5 : 4, 0, Math.PI * 2);
                            ctx.fill();
                        });
                    }
                    break;
                case 'ray':
                    if (pixelPoints.length >= 2) {
                        drawLine(ctx, pixelPoints[0], pixelPoints[1], 'end');
                        ctx.beginPath();
                        ctx.arc(pixelPoints[0].x, pixelPoints[0].y, isSelected ? 5 : 4, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    break;
                case 'horizontal':
                    if (pixelPoints.length >= 1) {
                        ctx.setLineDash([8, 4]);
                        ctx.beginPath();
                        ctx.moveTo(0, pixelPoints[0].y);
                        ctx.lineTo(width, pixelPoints[0].y);
                        ctx.stroke();
                        ctx.setLineDash([]);
                    }
                    break;
                case 'vertical':
                    if (pixelPoints.length >= 1) {
                        ctx.setLineDash([8, 4]);
                        ctx.beginPath();
                        ctx.moveTo(pixelPoints[0].x, 0);
                        ctx.lineTo(pixelPoints[0].x, height);
                        ctx.stroke();
                        ctx.setLineDash([]);
                    }
                    break;
                case 'parallel':
                    if (pixelPoints.length >= 3) {
                        drawLine(ctx, pixelPoints[0], pixelPoints[1], 'both');
                        const dx = pixelPoints[1].x - pixelPoints[0].x;
                        const dy = pixelPoints[1].y - pixelPoints[0].y;
                        const p3 = pixelPoints[2];
                        drawLine(ctx, { x: p3.x - dx, y: p3.y - dy }, { x: p3.x + dx, y: p3.y + dy }, 'both');
                        ctx.fillStyle = (isSelected ? '#ffffff' : drawing.color) + '15';
                        ctx.beginPath();
                        ctx.moveTo(pixelPoints[0].x, pixelPoints[0].y);
                        ctx.lineTo(pixelPoints[1].x, pixelPoints[1].y);
                        ctx.lineTo(p3.x + dx, p3.y + dy);
                        ctx.lineTo(p3.x - dx, p3.y - dy);
                        ctx.closePath();
                        ctx.fill();
                    }
                    break;
                case 'fibonacci':
                    if (pixelPoints.length >= 2) drawFibonacci(ctx, pixelPoints[0], pixelPoints[1], isSelected);
                    break;
                case 'golden':
                    if (pixelPoints.length >= 2) drawGoldenRatio(ctx, pixelPoints[0], pixelPoints[1], isSelected);
                    break;
                case 'rectangle':
                    if (pixelPoints.length >= 2) {
                        const x = Math.min(pixelPoints[0].x, pixelPoints[1].x);
                        const y = Math.min(pixelPoints[0].y, pixelPoints[1].y);
                        const w = Math.abs(pixelPoints[1].x - pixelPoints[0].x);
                        const h = Math.abs(pixelPoints[1].y - pixelPoints[0].y);
                        ctx.fillStyle = (isSelected ? '#ffffff' : drawing.color) + '20';
                        ctx.fillRect(x, y, w, h);
                        ctx.strokeRect(x, y, w, h);
                    }
                    break;
                case 'text':
                    if (pixelPoints.length >= 1 && drawing.text) {
                        ctx.font = 'bold 13px sans-serif';
                        const metrics = ctx.measureText(drawing.text);
                        ctx.fillStyle = '#00000080';
                        ctx.fillRect(pixelPoints[0].x - 2, pixelPoints[0].y - 14, metrics.width + 4, 18);
                        ctx.fillStyle = isSelected ? '#ffffff' : drawing.color;
                        ctx.fillText(drawing.text, pixelPoints[0].x, pixelPoints[0].y);
                    }
                    break;
            }
        }

        // 繪製預覽（使用像素座標）
        if (isDrawing && startPixel && isDrawingMode) {
            ctx.strokeStyle = currentColorRef.current;
            ctx.fillStyle = currentColorRef.current;
            ctx.lineWidth = 2;
            ctx.setLineDash([]);
            const endPt = currentPixel || startPixel;

            switch (activeType) {
                case 'trendline': drawLine(ctx, startPixel, endPt, 'both'); break;
                case 'segment': drawLine(ctx, startPixel, endPt, 'none'); break;
                case 'ray': drawLine(ctx, startPixel, endPt, 'end'); break;
                case 'horizontal':
                    ctx.setLineDash([8, 4]);
                    ctx.beginPath();
                    ctx.moveTo(0, endPt.y);
                    ctx.lineTo(width, endPt.y);
                    ctx.stroke();
                    break;
                case 'vertical':
                    ctx.setLineDash([8, 4]);
                    ctx.beginPath();
                    ctx.moveTo(endPt.x, 0);
                    ctx.lineTo(endPt.x, height);
                    ctx.stroke();
                    break;
                case 'parallel':
                    if (drawStep === 0) {
                        drawLine(ctx, startPixel, endPt, 'both');
                    } else if (thirdPixel) {
                        drawLine(ctx, startPixel, thirdPixel, 'both');
                        const dx = thirdPixel.x - startPixel.x;
                        const dy = thirdPixel.y - startPixel.y;
                        drawLine(ctx, { x: endPt.x - dx, y: endPt.y - dy }, { x: endPt.x + dx, y: endPt.y + dy }, 'both');
                    }
                    break;
                case 'fibonacci': drawFibonacci(ctx, startPixel, endPt, false); break;
                case 'golden': drawGoldenRatio(ctx, startPixel, endPt, false); break;
                case 'rectangle': {
                    const x = Math.min(startPixel.x, endPt.x);
                    const y = Math.min(startPixel.y, endPt.y);
                    const w = Math.abs(endPt.x - startPixel.x);
                    const h = Math.abs(endPt.y - startPixel.y);
                    ctx.fillStyle = currentColorRef.current + '20';
                    ctx.fillRect(x, y, w, h);
                    ctx.strokeRect(x, y, w, h);
                    break;
                }
            }
        }
    }, [drawings, width, height, isDrawing, startPixel, currentPixel, thirdPixel, activeType, selectedId, drawStep, isDrawingMode, drawLine, drawFibonacci, drawGoldenRatio, chartToPixel, redrawTrigger]);

    useEffect(() => {
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
        rafRef.current = requestAnimationFrame(redraw);
        return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    }, [redraw]);

    // ========== 點擊檢測 ==========

    const findDrawingAtPoint = useCallback((pixel: { x: number; y: number }): DrawingObject | null => {
        for (let i = drawings.length - 1; i >= 0; i--) {
            const d = drawings[i];
            const pixelPoints = d.points.map(p => chartToPixel(p)).filter((p): p is { x: number; y: number } => p !== null);
            if (pixelPoints.length === 0) continue;

            switch (d.type) {
                case 'trendline':
                case 'segment':
                case 'ray':
                    if (pixelPoints.length >= 2 && isPointNearLine(pixel, pixelPoints[0], pixelPoints[1], 12)) return d;
                    break;
                case 'horizontal':
                    if (pixelPoints.length >= 1 && Math.abs(pixel.y - pixelPoints[0].y) < 12) return d;
                    break;
                case 'vertical':
                    if (pixelPoints.length >= 1 && Math.abs(pixel.x - pixelPoints[0].x) < 12) return d;
                    break;
                case 'parallel':
                    if (pixelPoints.length >= 3) {
                        if (isPointNearLine(pixel, pixelPoints[0], pixelPoints[1], 12)) return d;
                        const dx = pixelPoints[1].x - pixelPoints[0].x;
                        const dy = pixelPoints[1].y - pixelPoints[0].y;
                        const p3 = pixelPoints[2];
                        if (isPointNearLine(pixel, { x: p3.x - dx, y: p3.y - dy }, { x: p3.x + dx, y: p3.y + dy }, 12)) return d;
                    }
                    break;
                case 'rectangle':
                case 'fibonacci':
                case 'golden':
                    if (pixelPoints.length >= 2) {
                        const minX = Math.min(pixelPoints[0].x, pixelPoints[1].x) - 5;
                        const maxX = Math.max(pixelPoints[0].x, pixelPoints[1].x) + 5;
                        const minY = Math.min(pixelPoints[0].y, pixelPoints[1].y) - 5;
                        const maxY = Math.max(pixelPoints[0].y, pixelPoints[1].y) + 5;
                        if (pixel.x >= minX && pixel.x <= maxX && pixel.y >= minY && pixel.y <= maxY) return d;
                    }
                    break;
                case 'text':
                    if (pixelPoints.length >= 1 && d.text) {
                        const textWidth = d.text.length * 8 + 10;
                        if (pixel.x >= pixelPoints[0].x - 5 && pixel.x <= pixelPoints[0].x + textWidth &&
                            pixel.y >= pixelPoints[0].y - 18 && pixel.y <= pixelPoints[0].y + 5) return d;
                    }
                    break;
            }
        }
        return null;
    }, [drawings, isPointNearLine, chartToPixel]);

    // ========== 事件處理 ==========

    const getPixelFromEvent = useCallback((e: React.MouseEvent): { x: number; y: number } | null => {
        const rect = canvasRef.current?.getBoundingClientRect();
        if (!rect) return null;
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }, []);

    // 繪圖模式事件
    const handleCanvasMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!isDrawingMode) return;

        const pixel = getPixelFromEvent(e);
        if (!pixel) return;

        if (activeType === 'text') {
            setTextInput({ x: pixel.x, y: pixel.y, show: true });
            return;
        }

        currentColorRef.current = COLORS[Math.floor(Math.random() * COLORS.length)];
        setIsDrawing(true);
        setStartPixel(pixel);
        setCurrentPixel(pixel);
        setDrawStep(0);
    }, [isDrawingMode, activeType, getPixelFromEvent]);

    const handleCanvasMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!isDrawing || !isDrawingMode) return;
        const pixel = getPixelFromEvent(e);
        if (pixel) setCurrentPixel(pixel);
    }, [isDrawing, isDrawingMode, getPixelFromEvent]);

    const handleCanvasMouseUp = useCallback(() => {
        if (!isDrawing || !startPixel || !isDrawingMode) return;

        const endPt = currentPixel || startPixel;

        // 轉換為圖表座標
        const startChart = pixelToChart(startPixel);
        const endChart = pixelToChart(endPt);

        if (!startChart || !endChart) {
            console.warn('座標轉換失敗，圖表可能未準備好');
            setIsDrawing(false);
            setStartPixel(null);
            setCurrentPixel(null);
            setThirdPixel(null);
            setDrawStep(0);
            return;
        }

        if (activeType === 'parallel' && drawStep === 0) {
            setThirdPixel(endPt);
            setDrawStep(1);
            return;
        }

        let points: ChartPoint[];
        if (activeType === 'horizontal' || activeType === 'vertical') {
            points = [endChart];
        } else if (activeType === 'parallel' && thirdPixel) {
            const thirdChart = pixelToChart(thirdPixel);
            if (!thirdChart) {
                setIsDrawing(false);
                setStartPixel(null);
                setCurrentPixel(null);
                setThirdPixel(null);
                setDrawStep(0);
                return;
            }
            points = [startChart, thirdChart, endChart];
        } else {
            points = [startChart, endChart];
        }

        const newDrawing: DrawingObject = {
            id: Date.now().toString(),
            type: activeType,
            points,
            color: currentColorRef.current,
        };

        onAddDrawing(newDrawing);
        setIsDrawing(false);
        setStartPixel(null);
        setCurrentPixel(null);
        setThirdPixel(null);
        setDrawStep(0);
    }, [isDrawing, isDrawingMode, startPixel, currentPixel, activeType, thirdPixel, drawStep, onAddDrawing, pixelToChart]);

    // 選擇模式事件
    const handleSelectMouseDown = useCallback((e: React.MouseEvent) => {
        if (!isSelectMode) return;

        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return;

        const pixel = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        const found = findDrawingAtPoint(pixel);

        if (found) {
            onSelectDrawing(found.id);
            e.stopPropagation();
            e.preventDefault();
        } else {
            onSelectDrawing(null);
        }
    }, [isSelectMode, findDrawingAtPoint, onSelectDrawing]);

    const handleTextSubmit = useCallback(() => {
        if (!textValue.trim()) {
            setTextInput({ x: 0, y: 0, show: false });
            return;
        }

        const chartPoint = pixelToChart({ x: textInput.x, y: textInput.y });
        if (!chartPoint) {
            console.warn('文字座標轉換失敗');
            setTextInput({ x: 0, y: 0, show: false });
            setTextValue('');
            return;
        }

        onAddDrawing({
            id: Date.now().toString(),
            type: 'text',
            points: [chartPoint],
            color: COLORS[Math.floor(Math.random() * COLORS.length)],
            text: textValue,
        });
        setTextInput({ x: 0, y: 0, show: false });
        setTextValue('');
    }, [textValue, textInput, onAddDrawing, pixelToChart]);

    const handleDeleteSelected = useCallback(() => {
        if (selectedId) {
            onDeleteDrawing(selectedId);
            onSelectDrawing(null);
        }
    }, [selectedId, onDeleteDrawing, onSelectDrawing]);

    // ========== 渲染 ==========

    // 正常模式：完全不攔截事件
    if (isNormalMode) {
        return (
            <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 10 }}>
                <canvas
                    ref={canvasRef}
                    width={width}
                    height={height}
                    className="absolute inset-0"
                />
            </div>
        );
    }

    return (
        <div
            ref={containerRef}
            className="absolute inset-0"
            style={{ zIndex: 10 }}
        >
            {/* 繪圖模式 Canvas */}
            {isDrawingMode && (
                <canvas
                    ref={canvasRef}
                    width={width}
                    height={height}
                    className="absolute inset-0 cursor-crosshair"
                    style={{ pointerEvents: 'auto' }}
                    onMouseDown={handleCanvasMouseDown}
                    onMouseMove={handleCanvasMouseMove}
                    onMouseUp={handleCanvasMouseUp}
                    onMouseLeave={() => {
                        if (isDrawing && activeType !== 'parallel') handleCanvasMouseUp();
                    }}
                />
            )}

            {/* 選擇模式 */}
            {isSelectMode && (
                <>
                    <canvas
                        ref={canvasRef}
                        width={width}
                        height={height}
                        className="absolute inset-0"
                        style={{ pointerEvents: 'none' }}
                    />
                    <div
                        className="absolute inset-0 cursor-pointer"
                        style={{ pointerEvents: 'auto' }}
                        onMouseDown={handleSelectMouseDown}
                    />
                </>
            )}

            {/* 浮動刪除按鈕 */}
            {selectedId && deleteButtonPos && isSelectMode && (
                <Button
                    variant="destructive"
                    size="sm"
                    className="absolute h-7 px-2 text-xs shadow-lg animate-in fade-in zoom-in duration-150"
                    style={{
                        left: deleteButtonPos.x - 30,
                        top: deleteButtonPos.y - 14,
                        pointerEvents: 'auto',
                        zIndex: 20,
                    }}
                    onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSelected();
                    }}
                >
                    <Trash2 className="h-3.5 w-3.5 mr-1" />
                    刪除
                </Button>
            )}

            {/* 文字輸入框 */}
            {textInput.show && (
                <div
                    className="absolute flex items-center gap-1 bg-white dark:bg-gray-800 p-1 rounded shadow-lg border"
                    style={{ left: textInput.x, top: textInput.y, pointerEvents: 'auto', zIndex: 30 }}
                >
                    <Input
                        value={textValue}
                        onChange={(e) => setTextValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleTextSubmit();
                            if (e.key === 'Escape') setTextInput({ x: 0, y: 0, show: false });
                        }}
                        placeholder="輸入標註..."
                        className="h-7 w-40 text-xs"
                        autoFocus
                    />
                    <Button size="sm" className="h-7 px-2" onClick={handleTextSubmit}>確定</Button>
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => setTextInput({ x: 0, y: 0, show: false })}>
                        <X className="h-3 w-3" />
                    </Button>
                </div>
            )}
        </div>
    );
}

// ========== Hook ==========

export function useDrawings() {
    const [drawings, setDrawings] = useState<DrawingObject[]>([]);
    const [activeType, setActiveType] = useState<DrawingType>('off');  // 預設正常模式
    const [selectedId, setSelectedId] = useState<string | null>(null);

    const addDrawing = useCallback((drawing: DrawingObject) => {
        setDrawings(prev => [...prev, drawing]);
    }, []);

    const deleteDrawing = useCallback((id: string) => {
        setDrawings(prev => prev.filter(d => d.id !== id));
        setSelectedId(prev => prev === id ? null : prev);
    }, []);

    const updateDrawing = useCallback((id: string, updates: Partial<DrawingObject>) => {
        setDrawings(prev => prev.map(d => d.id === id ? { ...d, ...updates } : d));
    }, []);

    const clearDrawings = useCallback(() => {
        setDrawings([]);
        setSelectedId(null);
    }, []);

    const selectedDrawing = useMemo(
        () => drawings.find(d => d.id === selectedId) || null,
        [drawings, selectedId]
    );

    return {
        drawings,
        activeType,
        setActiveType,
        selectedId,
        setSelectedId,
        selectedDrawing,
        addDrawing,
        deleteDrawing,
        updateDrawing,
        clearDrawings,
    };
}

export default DrawingToolbar;
