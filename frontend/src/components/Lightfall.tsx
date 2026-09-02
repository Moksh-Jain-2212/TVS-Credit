"use client";

import { useEffect, useRef } from "react";
import { Mesh, Program, Renderer, Triangle } from "ogl";

const vertex = `attribute vec2 position; attribute vec2 uv; varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position,0.,1.);}`;
const fragment = `precision highp float;
uniform vec2 iResolution; uniform vec2 iMouse; uniform float iTime; uniform float uLight;
varying vec2 vUv;
float hash(float n){return fract(sin(n)*43758.5453123);}
float streak(vec2 uv,float id){float x=hash(id)*1.3-.15;float speed=.14+hash(id+12.)*.32;float y=fract(hash(id+4.)-iTime*speed);float width=.0015+hash(id+9.)*.003;float glow=1.-smoothstep(width,width*9.,abs(uv.x-x));float tail=smoothstep(.18,0.,abs(uv.y-y));return glow*tail;}
void main(){vec2 uv=vUv;vec3 bg=mix(vec3(.95,.98,1.),vec3(.015,.06,.16),1.-uLight);vec3 col=bg;float sum=0.;for(int i=0;i<22;i++){float s=streak(uv,float(i));sum+=s;vec3 c=mod(float(i),3.)<1.?vec3(.49,.98,1.):mod(float(i),3.)<2.?vec3(.35,.55,1.):vec3(.75,.45,1.);col+=c*s*(uLight>.5?.45:1.35);}float mouse=exp(-length(uv-iMouse)*7.)*.22;col+=vec3(.3,.9,1.)*mouse;gl_FragColor=vec4(col,1.);}`;

export default function Lightfall({ lightMode = false }: { lightMode?: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const container = ref.current; if (!container || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const renderer = new Renderer({ dpr: Math.min(window.devicePixelRatio || 1, 2), alpha: true });
    const gl = renderer.gl; const canvas = gl.canvas; canvas.className = "lightfall-canvas"; container.appendChild(canvas);
    const uniforms = { iResolution: { value: [1, 1] }, iMouse: { value: [0.5, 0.5] }, iTime: { value: 0 }, uLight: { value: lightMode ? 1 : 0 } };
    const program = new Program(gl, { vertex, fragment, uniforms }); const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });
    const resize = () => { const rect = container.getBoundingClientRect(); renderer.setSize(rect.width, rect.height); uniforms.iResolution.value = [gl.drawingBufferWidth, gl.drawingBufferHeight]; };
    const pointer = (event: PointerEvent) => { const rect = canvas.getBoundingClientRect(); uniforms.iMouse.value = [(event.clientX - rect.left) / rect.width, 1 - (event.clientY - rect.top) / rect.height]; };
    const observer = new ResizeObserver(resize); observer.observe(container); canvas.addEventListener("pointermove", pointer); resize();
    let frame = 0; const render = (time: number) => { uniforms.iTime.value = time * .001; renderer.render({ scene: mesh }); frame = requestAnimationFrame(render); }; frame = requestAnimationFrame(render);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); canvas.removeEventListener("pointermove", pointer); canvas.remove(); };
  }, [lightMode]);
  return <div ref={ref} className="lightfall-container" aria-hidden="true" />;
}
