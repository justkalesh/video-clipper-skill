// One short clip cut from a long video, laid out for any output shape.
// Everything comes from the data file written by scripts/build_clip.py:
//   segments -> per shot, which source rectangles go into which panel (optionally moving over time)
//   pages    -> caption groups with word timings
//   style    -> caption style, colours, title, branding, audio
import React, { useEffect, useState } from "react";
import { Audio, Video } from "@remotion/media";
import {
  AbsoluteFill,
  Img,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type Rect = [number, number, number, number]; // x, y, w, h
type Key = [number, number, number]; // frame (from segment start), src x, src y
type Panel = { box: Rect; src: Rect; mode?: "cover" | "contain"; track?: Key[] };
type Segment = { from: number; to: number; layout: string; panels: Panel[] };
type Word = { text: string; startMs: number; endMs: number; emph?: boolean };
type Page = { startMs: number; endMs: number; words: Word[]; marker?: boolean };

export type ClipStyle = {
  captionStyle: "karaoke" | "pop" | "line" | "boxed" | "none";
  textColor: string;
  activeColor: string;
  outlineColor: string;
  glow: boolean;
  monoGrow: boolean;
  caseMode: "as_spoken" | "upper" | "lower";
  captionPosition: "auto" | "top" | "middle" | "bottom";
  font: string;
  fontSize: number;
  titleShow: boolean;
  titlePosition: "top" | "split" | "bottom";
  titleDuration: "full" | "intro";
  titleBg: string;
  titleText: string;
  watermark: string | null;
  watermarkPosition: "top_left" | "top_right" | "bottom_left" | "bottom_right";
  progressBar: boolean;
  endCard: string | null;
  zoomOnStatic: boolean;
  seamPx: number;
  seamColor: string;
  backgroundFill: "blur" | "black";
  fadeMs: number;
  music: string | null;
  musicVolume: number;
};

export type ClipData = {
  id: string;
  title: string;
  fps: number;
  width: number;
  height: number;
  src: string;
  sourceW: number;
  sourceH: number;
  startFrame: number;
  durationInFrames: number;
  segments: Segment[];
  pages: Page[];
  style: ClipStyle;
};
export type ClipProps = { data: ClipData };

export const DEMO: ClipData = {
  id: "demo",
  title: "Pass a clip with --props",
  fps: 30,
  width: 1080,
  height: 1920,
  src: "",
  sourceW: 1920,
  sourceH: 1080,
  startFrame: 0,
  durationInFrames: 60,
  segments: [],
  pages: [],
  style: {
    captionStyle: "karaoke",
    textColor: "#ffffff",
    activeColor: "#ff2d2d",
    outlineColor: "#000000",
    glow: true,
    monoGrow: false,
    caseMode: "as_spoken",
    captionPosition: "auto",
    font: "Montserrat",
    fontSize: 108,
    titleShow: true,
    titlePosition: "top",
    titleDuration: "full",
    titleBg: "#ffffff",
    titleText: "#111111",
    watermark: null,
    watermarkPosition: "top_right",
    progressBar: false,
    endCard: null,
    zoomOnStatic: true,
    seamPx: 8,
    seamColor: "#000000",
    backgroundFill: "blur",
    fadeMs: 250,
    music: null,
    musicVolume: 0.08,
  },
};

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const SYSTEM_FONTS = ["segoe ui black", "segoe ui", "arial black", "arial", "impact", "verdana", "tahoma", "georgia"];

// Load a Google Font when the chosen font isn't a common system font; fall back silently if it can't be fetched.
const useFont = (font: string) => {
  const [handle] = useState(() =>
    SYSTEM_FONTS.includes(font.toLowerCase()) ? null : delayRender(`font ${font}`, { timeoutInMilliseconds: 20000 }),
  );
  useEffect(() => {
    if (handle === null) return;
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        continueRender(handle);
      }
    };
    const family = encodeURIComponent(font).replace(/%20/g, "+");
    const tries = [`${family}:wght@900`, `${family}:wght@700`, family];
    const attempt = (i: number) => {
      if (i >= tries.length) return finish();
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = `https://fonts.googleapis.com/css2?family=${tries[i]}&display=block`;
      link.onload = () => document.fonts.load(`900 40px "${font}"`).then(finish, finish);
      link.onerror = () => attempt(i + 1);
      document.head.appendChild(link);
    };
    attempt(0);
    const t = setTimeout(finish, 10000);
    return () => clearTimeout(t);
  }, [font, handle]);
};

const srcAt = (panel: Panel, frame: number): [number, number] => {
  const t = panel.track;
  if (!t || t.length === 0) return [panel.src[0], panel.src[1]];
  if (t.length === 1) return [t[0][1], t[0][2]];
  const fs = t.map((k) => k[0]);
  return [interpolate(frame, fs, t.map((k) => k[1]), CLAMP), interpolate(frame, fs, t.map((k) => k[2]), CLAMP)];
};

const PanelView: React.FC<{ panel: Panel; data: ClipData; trim: number; push: boolean; length: number }> = ({
  panel,
  data,
  trim,
  push,
  length,
}) => {
  const frame = useCurrentFrame();
  const [bx, by, bw, bh] = panel.box;
  const [, , sw, sh] = panel.src;
  const [sx, sy] = srcAt(panel, frame);
  const zoom = push ? interpolate(frame, [0, Math.max(length, 1)], [1, 1.05]) : 1;
  const video = (scale: number, offX: number, offY: number, extra?: React.CSSProperties) => (
    <Video
      src={staticFile(data.src)}
      trimBefore={trim}
      muted
      objectFit="fill"
      style={{
        position: "absolute",
        left: offX - sx * scale,
        top: offY - sy * scale,
        width: data.sourceW * scale,
        height: data.sourceH * scale,
        ...extra,
      }}
    />
  );
  let inner: React.ReactNode;
  if (panel.mode === "contain") {
    const fit = Math.min(bw / sw, bh / sh);
    const cover = Math.max(bw / sw, bh / sh) * 1.15;
    inner = (
      <>
        {data.style.backgroundFill === "blur" &&
          video(cover, (bw - sw * cover) / 2, (bh - sh * cover) / 2, { filter: "blur(36px) brightness(0.55)" })}
        {video(fit, (bw - sw * fit) / 2, (bh - sh * fit) / 2)}
      </>
    );
  } else {
    const scale = Math.max(bw / sw, bh / sh);
    inner = video(scale, (bw - sw * scale) / 2, (bh - sh * scale) / 2);
  }
  return (
    <div style={{ position: "absolute", left: bx, top: by, width: bw, height: bh, overflow: "hidden", background: "#000" }}>
      <div style={{ position: "absolute", inset: 0, transform: `scale(${zoom})`, transformOrigin: "50% 38%" }}>{inner}</div>
    </div>
  );
};

// Lines on every inner panel edge.
const Seams: React.FC<{ panels: Panel[]; px: number; color: string }> = ({ panels, px, color }) => {
  const { width, height } = useVideoConfig();
  if (px <= 0) return null;
  const lines: React.CSSProperties[] = [];
  for (const { box } of panels) {
    const [x, y, w, h] = box;
    if (x + w < width - 1) lines.push({ left: x + w - px / 2, top: y, width: px, height: h });
    if (y + h < height - 1) lines.push({ left: x, top: y + h - px / 2, width: w, height: px });
  }
  return (
    <>
      {lines.map((s, i) => (
        <div key={i} style={{ position: "absolute", background: color, ...s }} />
      ))}
    </>
  );
};

// y of the horizontal line between split views closest to the middle, if there is one
const seamY = (seg: Segment | undefined, height: number): number | null => {
  if (!seg || seg.panels.length < 2) return null;
  const ys = seg.panels.map((p) => p.box[1] + p.box[3]).filter((y) => y < height - 1);
  if (!ys.length) return null;
  return ys.reduce((a, b) => (Math.abs(b - height / 2) < Math.abs(a - height / 2) ? b : a));
};

const Title: React.FC<{ data: ClipData; y: number; scale: number }> = ({ data, y, scale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = data.style;
  const pop = spring({ frame, fps, config: { damping: 14, stiffness: 160 } });
  const fadeOut = s.titleDuration === "intro" ? interpolate(frame, [fps * 2.6, fps * 3], [1, 0], CLAMP) : 1;
  if (fadeOut <= 0) return null;
  return (
    <div style={{ position: "absolute", top: y, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
      <div
        style={{
          background: s.titleBg,
          color: s.titleText,
          fontFamily: `'${s.font}', 'Montserrat', 'Segoe UI Black', 'Arial Black', 'Helvetica Neue', Arial, sans-serif`,
          fontWeight: 900,
          fontSize: 50 * scale,
          padding: `${16 * scale}px ${34 * scale}px`,
          borderRadius: 22 * scale,
          maxWidth: data.width * 0.86,
          textAlign: "center",
          boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
          transform: `translateY(-50%) scale(${0.6 + 0.4 * pop})`,
          opacity: pop * fadeOut,
        }}
      >
        {data.title}
      </div>
    </div>
  );
};

const Captions: React.FC<{ data: ClipData; y: number; scale: number }> = ({ data, y, scale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = data.style;
  if (s.captionStyle === "none") return null;
  const ms = (frame / fps) * 1000;
  const page = data.pages.find((p) => ms >= p.startMs && ms < p.endMs);
  if (!page) return null;
  const pageFrame = frame - Math.round((page.startMs / 1000) * fps);
  const popIn = spring({ frame: pageFrame, fps, config: { damping: 12, stiffness: 220 }, durationInFrames: 6 });
  let active = -1;
  page.words.forEach((w, i) => {
    if (ms >= w.startMs) active = i;
  });
  const line = s.captionStyle === "line";
  const pop = s.captionStyle === "pop";
  const boxed = s.captionStyle === "boxed";
  const size = s.fontSize * scale * (line ? 0.6 : pop ? 1.2 : 1) * (page.marker ? 0.6 : 1);
  const stroke = boxed ? 0 : Math.max(2, size * (line ? 0.08 : 0.13));
  const transform = pop
    ? `translateY(-50%) scale(${0.55 + 0.45 * popIn})`
    : `translateY(-50%) scale(${line ? 1 : 0.85 + 0.15 * popIn})`;
  return (
    <div
      style={{
        position: "absolute",
        left: 40 * scale,
        right: 40 * scale,
        top: y,
        transform,
        display: "flex",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: `0 ${size * (line ? 0.25 : 0.28)}px`,
          fontFamily: `'${s.font}', 'Montserrat', 'Segoe UI Black', 'Arial Black', 'Helvetica Neue', Arial, sans-serif`,
          fontWeight: 900,
          fontStyle: page.marker ? "italic" : "normal",
          fontSize: size,
          lineHeight: 1.12,
          textAlign: "center",
          textTransform: s.caseMode === "upper" ? "uppercase" : s.caseMode === "lower" ? "lowercase" : "none",
          ...(boxed
            ? { background: "rgba(0,0,0,0.78)", borderRadius: 18 * scale, padding: `${10 * scale}px ${26 * scale}px` }
            : {}),
        }}
      >
        {page.words.map((w, i) => {
          const on = !line && !page.marker && i === active;
          const hot = on || (!line && w.emph);
          const color = hot && !s.monoGrow ? s.activeColor : s.textColor;
          const grow = on ? (s.monoGrow ? 1.18 : 1.08) : 1;
          const glow = hot && s.glow && !s.monoGrow ? `0 0 ${size * 0.28}px ${s.activeColor}` : "";
          const drop = boxed ? "" : `0 ${size * 0.06}px 0 ${s.outlineColor}`;
          return (
            <span
              key={i}
              style={{
                color,
                WebkitTextStroke: stroke ? `${stroke}px ${s.outlineColor}` : undefined,
                paintOrder: "stroke fill",
                textShadow: [glow, drop].filter(Boolean).join(", ") || undefined,
                transform: `scale(${grow})`,
                display: "inline-block",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};

const Watermark: React.FC<{ src: string; position: ClipStyle["watermarkPosition"]; scale: number }> = ({
  src,
  position,
  scale,
}) => {
  const m = 40 * scale;
  const pos: React.CSSProperties = {
    top: position.startsWith("top") ? m : undefined,
    bottom: position.startsWith("bottom") ? m : undefined,
    left: position.endsWith("left") ? m : undefined,
    right: position.endsWith("right") ? m : undefined,
  };
  return <Img src={staticFile(src)} style={{ position: "absolute", width: 150 * scale, opacity: 0.85, ...pos }} />;
};

const ProgressBar: React.FC<{ color: string; scale: number }> = ({ color, scale }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        bottom: 0,
        height: 10 * scale,
        width: `${(frame / Math.max(durationInFrames - 1, 1)) * 100}%`,
        background: color,
      }}
    />
  );
};

const EndCard: React.FC<{ text: string; data: ClipData; scale: number }> = ({ text, data, scale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(frame, [0, fps * 0.3], [0, 1], CLAMP);
  return (
    <AbsoluteFill style={{ background: "rgba(0,0,0,0.6)", justifyContent: "center", alignItems: "center", opacity }}>
      <div
        style={{
          color: "#fff",
          fontFamily: `'${data.style.font}', 'Montserrat', 'Segoe UI Black', 'Arial Black', 'Helvetica Neue', Arial, sans-serif`,
          fontWeight: 900,
          fontSize: 84 * scale,
          textAlign: "center",
          padding: 60 * scale,
          WebkitTextStroke: `${8 * scale}px #000`,
          paintOrder: "stroke fill",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

export const Clip: React.FC<ClipProps> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = data.style;
  useFont(s.font);
  const scale = Math.min(data.width, data.height) / 1080;
  const seg = data.segments.find((x) => frame >= x.from && frame < x.to) ?? data.segments[data.segments.length - 1];
  const seam = seamY(seg, data.height);
  const portrait = data.height > data.width;

  const capY = (() => {
    if (s.captionPosition === "top") return data.height * (s.titleShow && s.titlePosition === "top" ? 0.24 : 0.16);
    if (s.captionPosition === "middle") return data.height * 0.5;
    if (s.captionPosition === "bottom") return data.height * 0.84;
    if (seam !== null && portrait) return seam;
    return data.height * (portrait ? 0.8 : 0.84);
  })();
  const titleY = (() => {
    if (s.titlePosition === "bottom") return data.height * 0.93;
    // on the line between split views; with a single view there is no line, so it goes to the top
    if (s.titlePosition === "split" && seam !== null) return seam - s.fontSize * scale * 1.15;
    return data.height * 0.075;
  })();
  const fadeF = Math.round((s.fadeMs / 1000) * fps);
  const endFrames = Math.round(fps * 1.5);

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {data.segments.map((x, i) => (
        <Sequence key={i} from={x.from} durationInFrames={Math.max(x.to - x.from, 1)} name={`${x.layout} ${i}`}>
          {x.panels.map((p, j) => (
            <PanelView
              key={j}
              panel={p}
              data={data}
              trim={data.startFrame + x.from}
              push={s.zoomOnStatic && x.panels.length === 1 && !p.track && p.mode !== "contain"}
              length={x.to - x.from}
            />
          ))}
          <Seams panels={x.panels} px={s.seamPx * scale} color={s.seamColor} />
        </Sequence>
      ))}
      {data.src ? (
        <Audio
          src={staticFile(data.src)}
          trimBefore={data.startFrame}
          volume={(f) =>
            fadeF > 0
              ? interpolate(f, [0, fadeF, data.durationInFrames - fadeF, data.durationInFrames], [0, 1, 1, 0], CLAMP)
              : 1
          }
        />
      ) : null}
      {s.music ? <Audio src={staticFile(s.music)} volume={s.musicVolume} loop /> : null}
      {s.titleShow ? <Title data={data} y={titleY} scale={scale} /> : null}
      <Captions data={data} y={capY} scale={scale} />
      {s.watermark ? <Watermark src={s.watermark} position={s.watermarkPosition} scale={scale} /> : null}
      {s.progressBar ? <ProgressBar color={s.activeColor} scale={scale} /> : null}
      {s.endCard ? (
        <Sequence from={Math.max(data.durationInFrames - endFrames, 0)} durationInFrames={endFrames}>
          <EndCard text={s.endCard} data={data} scale={scale} />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};
