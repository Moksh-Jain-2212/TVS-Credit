"use client";

import { useCallback, useEffect, useRef, type CSSProperties, type ReactNode } from "react";
import "./ElectricBorder.css";

type Props = { children: ReactNode; color?: string; speed?: number; chaos?: number; thickness?: number; borderRadius?: number; className?: string; style?: CSSProperties };
type Point = { x: number; y: number };

export default function ElectricBorder({ children, color = "#7df9ff", speed = 1, chaos = 0.12, thickness = 2, borderRadius = 16, className = "", style }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const timeRef = useRef(0);
  const lastFrameRef = useRef(0);
  const random = useCallback((value: number) => (Math.sin(value * 12.9898) * 43758.5453) % 1, []);
  const noise = useCallback((x: number, y: number) => {
    const i = Math.floor(x), j = Math.floor(y), fx = x - i, fy = y - j;
    const a = random(i + j * 57), b = random(i + 1 + j * 57), c = random(i + (j + 1) * 57), d = random(i + 1 + (j + 1) * 57);
    const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
    return a * (1 - ux) * (1 - uy) + b * ux * (1 - uy) + c * (1 - ux) * uy + d * ux * uy;
  }, [random]);
  const octavedNoise = useCallback((x: number, time: number, seed: number) => {
    let total = 0, amplitude = chaos, frequency = 10;
    for (let index = 0; index < 10; index += 1) { total += amplitude * noise(frequency * x + seed * 100, time * frequency * 0.3); frequency *= 1.6; amplitude *= 0.7; }
    return total;
  }, [chaos, noise]);
  const roundedPoint = useCallback((progress: number, left: number, top: number, width: number, height: number, radius: number): Point => {
    const horizontal = width - 2 * radius, vertical = height - 2 * radius, arc = Math.PI * radius / 2;
    const distance = progress * (2 * horizontal + 2 * vertical + 4 * arc); let used = 0;
    const corner = (x: number, y: number, start: number, p: number): Point => ({ x: x + radius * Math.cos(start + p * Math.PI / 2), y: y + radius * Math.sin(start + p * Math.PI / 2) });
    if (distance <= horizontal) return { x: left + radius + distance, y: top }; used += horizontal;
    if (distance <= used + arc) return corner(left + width - radius, top + radius, -Math.PI / 2, (distance - used) / arc); used += arc;
    if (distance <= used + vertical) return { x: left + width, y: top + radius + distance - used }; used += vertical;
    if (distance <= used + arc) return corner(left + width - radius, top + height - radius, 0, (distance - used) / arc); used += arc;
    if (distance <= used + horizontal) return { x: left + width - radius - (distance - used), y: top + height }; used += horizontal;
    if (distance <= used + arc) return corner(left + radius, top + height - radius, Math.PI / 2, (distance - used) / arc); used += arc;
    if (distance <= used + vertical) return { x: left, y: top + height - radius - (distance - used) }; used += vertical;
    return corner(left + radius, top + radius, Math.PI, (distance - used) / arc);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current, container = containerRef.current;
    if (!canvas || !container || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    const offset = 24;
    const resize = () => { const rect = container.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2), width = rect.width + offset * 2, height = rect.height + offset * 2; canvas.width = width * dpr; canvas.height = height * dpr; canvas.style.width = `${width}px`; canvas.style.height = `${height}px`; return { width, height, dpr }; };
    let size = resize();
    const draw = (now: number) => {
      timeRef.current += (lastFrameRef.current ? (now - lastFrameRef.current) / 1000 : 0) * speed; lastFrameRef.current = now;
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.scale(size.dpr, size.dpr);
      const width = size.width - offset * 2, height = size.height - offset * 2, radius = Math.min(borderRadius, width / 2, height / 2), samples = Math.max(120, Math.floor((2 * (width + height) + 2 * Math.PI * radius) / 2));
      ctx.strokeStyle = color; ctx.lineWidth = thickness; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.beginPath();
      for (let index = 0; index <= samples; index += 1) { const p = index / samples, point = roundedPoint(p, offset, offset, width, height, radius), x = point.x + octavedNoise(p * 8, timeRef.current, 0) * 28, y = point.y + octavedNoise(p * 8, timeRef.current, 1) * 28; if (!index) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
      ctx.closePath(); ctx.stroke(); frameRef.current = requestAnimationFrame(draw);
    };
    const observer = new ResizeObserver(() => { size = resize(); }); observer.observe(container); frameRef.current = requestAnimationFrame(draw);
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); observer.disconnect(); };
  }, [borderRadius, color, octavedNoise, roundedPoint, speed, thickness]);

  const variables = { "--electric-border-color": color, borderRadius: `${borderRadius}px`, ...style } as CSSProperties;
  return <div ref={containerRef} className={`electric-border ${className}`} style={variables}><div className="eb-canvas-container"><canvas ref={canvasRef} className="eb-canvas" /></div><div className="eb-layers"><div className="eb-glow-1" /><div className="eb-glow-2" /><div className="eb-background-glow" /></div><div className="eb-content">{children}</div></div>;
}
