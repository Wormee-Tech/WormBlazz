import { useEffect, useRef } from 'react';
import { useViewport } from '@xyflow/react';

export interface CanvasDot {
    id: string;
    /** Flow-space center X */
    x: number;
    /** Flow-space center Y */
    y: number;
    r: number;
    color: string;
    isPrivate?: boolean;
}

export interface CanvasSpoke {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
}

interface Props {
    dots: CanvasDot[];
    spokes: CanvasSpoke[];
}

/**
 * Paints leaf profiles as canvas circles + spokes. Handles ~1000 dots without
 * creating React Flow DOM nodes (the main source of pan/zoom lag).
 */
function SocialCanvasLayer({ dots, spokes }: Props) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const { x: tx, y: ty, zoom } = useViewport();
    const sizeRef = useRef({ w: 0, h: 0 });

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const parent = canvas.parentElement;
        if (!parent) return;

        const paint = () => {
            const width = parent.clientWidth;
            const height = parent.clientHeight;
            if (width === 0 || height === 0) return;

            const dpr = Math.min(window.devicePixelRatio || 1, 2);
            if (sizeRef.current.w !== width || sizeRef.current.h !== height) {
                sizeRef.current = { w: width, h: height };
                canvas.width = Math.floor(width * dpr);
                canvas.height = Math.floor(height * dpr);
                canvas.style.width = `${width}px`;
                canvas.style.height = `${height}px`;
            }

            const ctx = canvas.getContext('2d');
            if (!ctx) return;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.clearRect(0, 0, width, height);

            if (spokes.length > 0 && zoom > 0.06) {
                ctx.beginPath();
                ctx.strokeStyle = 'rgba(100, 116, 139, 0.22)';
                ctx.lineWidth = Math.max(0.35, 0.5 * zoom);
                for (const spoke of spokes) {
                    ctx.moveTo(tx + spoke.x1 * zoom, ty + spoke.y1 * zoom);
                    ctx.lineTo(tx + spoke.x2 * zoom, ty + spoke.y2 * zoom);
                }
                ctx.stroke();
            }

            for (const dot of dots) {
                const sx = tx + dot.x * zoom;
                const sy = ty + dot.y * zoom;
                const pad = 6;
                if (sx < -pad || sy < -pad || sx > width + pad || sy > height + pad) continue;

                const radius = Math.max(1.4, dot.r * zoom);
                ctx.beginPath();
                ctx.arc(sx, sy, radius, 0, Math.PI * 2);
                if (dot.isPrivate) {
                    ctx.fillStyle = '#ffffff';
                    ctx.fill();
                    ctx.strokeStyle = dot.color;
                    ctx.lineWidth = 1;
                    ctx.setLineDash([2, 2]);
                    ctx.stroke();
                    ctx.setLineDash([]);
                } else {
                    ctx.fillStyle = dot.color;
                    ctx.fill();
                }
            }
        };

        paint();
        const observer = new ResizeObserver(() => {
            sizeRef.current = { w: 0, h: 0 };
            paint();
        });
        observer.observe(parent);
        return () => observer.disconnect();
    }, [dots, spokes, tx, ty, zoom]);

    return <canvas ref={canvasRef} className="social-canvas-layer" aria-hidden />;
}

/** Hit-test a flow-space point against canvas dots. */
export function hitTestCanvasDot(
    flowX: number,
    flowY: number,
    dots: CanvasDot[],
    zoom: number,
): string | null {
    const slop = Math.max(6, 10 / Math.max(zoom, 0.1));
    let bestId: string | null = null;
    let bestDist = Infinity;
    for (const dot of dots) {
        const dx = flowX - dot.x;
        const dy = flowY - dot.y;
        const dist = Math.hypot(dx, dy);
        const threshold = Math.max(dot.r, slop);
        if (dist <= threshold && dist < bestDist) {
            bestDist = dist;
            bestId = dot.id;
        }
    }
    return bestId;
}

export default SocialCanvasLayer;
