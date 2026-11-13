"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { apiFetch } from "@/lib/api";

const MONTREAL: [number, number] = [45.5017, -73.5673];
// Leave room around the island when viewing it at a wider zoom.
const MONTREAL_BOUNDS: [[number, number], [number, number]] = [[45.0, -74.6], [46.05, -72.95]];
const ISLAND_BOUNDS: [[number, number], [number, number]] = [[45.38, -74.02], [45.75, -73.42]];
const DEFAULT_ZOOM = 14;
const MARKER_FOCUS_ZOOM = 16;
type Kind = "restaurant" | "ordered_restaurant" | "courier" | "customer";
type Point = { id: string; label: string; kind: Kind; latitude: string; longitude: string; detail: string };
type MapData = { role: "customer" | "restaurant" | "courier" | "operator"; points: Point[]; notices: string[] };
const legend: Record<Kind, { color: string; label: string }> = {
  restaurant: { color: "#43834A", label: "Restaurant" },
  ordered_restaurant: { color: "#DC6A16", label: "Your active order's restaurant" },
  courier: { color: "#2563EB", label: "Courier" },
  customer: { color: "#9333EA", label: "Delivery destination" },
};

export default function MontrealMap() {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const focusRef = useRef<(() => void) | null>(null);
  const refreshRef = useRef<(() => Promise<void>) | null>(null);
  const selectingRef = useRef(false);
  const [selecting, setSelecting] = useState(false);
  const [draft, setDraft] = useState<[number, number] | null>(null);
  const [data, setData] = useState<MapData | null>(null);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [tileError, setTileError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    let map: LeafletMap | undefined;
    let observer: ResizeObserver | undefined;
    let timer: ReturnType<typeof setInterval> | undefined;
    const controller = new AbortController();

    async function initialize() {
      try {
        const L = await import("leaflet");
        if (disposed || !container.current) return;
        const bounds = L.latLngBounds(MONTREAL_BOUNDS);
        const currentMap = L.map(container.current, {
          scrollWheelZoom: false,
          maxBounds: bounds,
          maxBoundsViscosity: 1,
          minZoom: 10,
          maxZoom: 19,
        }).setView(MONTREAL, DEFAULT_ZOOM);
        let focusCoordinates: [number, number][] = [];
        focusRef.current = () => {
          if (focusCoordinates.length) {
            currentMap.fitBounds(L.latLngBounds(focusCoordinates), { padding: [45, 45], maxZoom: MARKER_FOCUS_ZOOM });
          } else {
            currentMap.setView(MONTREAL, Math.max(DEFAULT_ZOOM, currentMap.getMinZoom()));
          }
        };
        const constrainViewport = () => {
          currentMap.invalidateSize();
          // Allow the entire island to fit, including on narrower screens.
          currentMap.setMinZoom(Math.min(10, currentMap.getBoundsZoom(L.latLngBounds(ISLAND_BOUNDS))));
          currentMap.panInsideBounds(bounds, { animate: false });
        };
        map = currentMap;
        mapRef.current = map;
        const points = L.layerGroup().addTo(map);
        let selection: ReturnType<typeof L.circleMarker> | undefined;
        map.on("click", (event) => {
          if (!selectingRef.current) return;
          selection?.remove();
          const position: [number, number] = [Number(event.latlng.lat.toFixed(6)), Number(event.latlng.lng.toFixed(6))];
          setDraft(position);
          selection = L.circleMarker(position, { radius: 13, color: "#111827", fillOpacity: 0.15, dashArray: "4 4" }).addTo(currentMap);
        });
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).on("tileerror", () => { if (!disposed) setTileError(true); }).addTo(map);
        constrainViewport();
        observer = new ResizeObserver(constrainViewport);
        observer.observe(container.current);
        setReady(true);
        let inFlight = false;
        let firstView = true;
        async function refresh() {
          if (inFlight || disposed) return;
          inFlight = true;
          try {
            const response = await apiFetch("/api/map/", { signal: controller.signal });
            if (!response.ok) throw new Error("Map locations could not be loaded. Refresh or sign in again.");
            const result: MapData = await response.json();
            if (disposed) return;
            points.clearLayers();
            const coordinates: [number, number][] = [];
            for (const point of result.points) {
              const position: [number, number] = [Number(point.latitude), Number(point.longitude)];
              if (!position.every(Number.isFinite)) continue;
              if (bounds.contains(position)) coordinates.push(position);
              const popup = document.createElement("div");
              const title = document.createElement("strong");
              title.textContent = point.label;
              const detail = document.createElement("p");
              detail.textContent = point.detail;
              popup.append(title, detail);
              const tooltip = document.createElement("span");
              tooltip.textContent = point.label;
              if (result.role === "courier") {
                const pinLabel = point.kind === "courier" ? "Your location" : point.kind === "customer" ? "Customer destination" : "Restaurant";
                const letter = point.kind === "courier" ? "C" : point.kind === "customer" ? "D" : "R";
                tooltip.textContent = pinLabel;
                const icon = L.divIcon({
                  className: "delivery-map-pin",
                  // Colors and letters come only from the fixed marker definitions.
                  html: `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="46" viewBox="0 0 36 46" aria-hidden="true"><path d="M18 44C14 38 2 26 2 18a16 16 0 1 1 32 0c0 8-12 20-16 26Z" fill="${legend[point.kind].color}" stroke="white" stroke-width="2"/><text x="18" y="24" text-anchor="middle" fill="white" font-family="Arial,sans-serif" font-size="17" font-weight="bold">${letter}</text></svg>`,
                  iconSize: [36, 46],
                  iconAnchor: [18, 44],
                  popupAnchor: [0, -42],
                  tooltipAnchor: [0, -40],
                });
                L.marker(position, { icon, title: `${pinLabel}: ${point.label}`, alt: pinLabel })
                  .bindPopup(popup).bindTooltip(tooltip, { direction: "top" }).addTo(points);
              } else {
                L.circleMarker(position, {
                  radius: point.kind === "ordered_restaurant" ? 13 : point.kind === "restaurant" ? 10 : 7,
                  color: "#FFFFFF", weight: 2, fillColor: legend[point.kind].color, fillOpacity: 1,
                }).bindPopup(popup).bindTooltip(tooltip, { direction: "top" }).addTo(points);
              }
            }
            focusCoordinates = coordinates;
            if (firstView && coordinates.length) {
              focusRef.current?.();
              firstView = false;
            }
            if (!selectingRef.current) selection?.remove();
            setData(result);
            setError("");
          } catch (err) {
            if (!disposed) {
              points.clearLayers();
              setData(null);
              setError(err instanceof Error ? err.message : "Could not load map locations.");
            }
          } finally { inFlight = false; }
        }
        refreshRef.current = refresh;
        await refresh();
        if (!disposed) timer = setInterval(() => void refresh(), 15000);
      } catch {
        if (!disposed) setError("The map could not be loaded. Please try again.");
      }
    }
    void initialize();
    return () => {
      disposed = true;
      controller.abort();
      clearInterval(timer);
      observer?.disconnect();
      map?.remove();
      mapRef.current = null;
      refreshRef.current = null;
      focusRef.current = null;
    };
  }, [attempt]);

  async function saveLocation() {
    if (!draft || saving) return;
    setSaving(true);
    setNotice("");
    try {
      const response = await apiFetch("/api/map/location/", {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latitude: draft[0].toFixed(6), longitude: draft[1].toFixed(6) }),
      });
      if (!response.ok) throw new Error("Could not save your location. Please try again.");
      selectingRef.current = false;
      setSelecting(false);
      setDraft(null);
      setNotice("Location saved.");
      await refreshRef.current?.();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save location."); }
    finally { setSaving(false); }
  }

  return (
    <section aria-label="Montreal map" className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h2 className="section-title">Montreal delivery map</h2>
        </div>
        <button type="button" className="btn btn-secondary" disabled={!ready} onClick={() => focusRef.current?.()}>Focus locations</button>
      </div>
      {data && data.role === "courier" && <div className="mb-4 rounded-xl bg-[var(--color-sage-light)] p-4">
        <button type="button" className="btn btn-secondary" disabled={saving} onClick={() => { selectingRef.current = true; setSelecting(true); setDraft(null); setNotice(""); }}>
          Update my position
        </button>
        {selecting && <div className="mt-3 flex flex-wrap items-center gap-3">
          <p className="body-text">{draft ? `Selected: ${draft[0]}, ${draft[1]}` : "Click the map to choose your location."}</p>
          <button type="button" className="btn btn-primary" disabled={!draft || saving} onClick={() => void saveLocation()}>{saving ? "Saving…" : "Save location"}</button>
          <button type="button" className="btn btn-secondary" disabled={saving} onClick={() => { selectingRef.current = false; setSelecting(false); setDraft(null); void refreshRef.current?.(); }}>Cancel</button>
        </div>}
      </div>}
      {notice && <p role="status" className="message message-success mb-3">{notice}</p>}
      {(error || tileError) && <div role="alert" className="message message-error mb-4">
        <p>{error || "Some map tiles could not load. Check your internet connection and try again."}</p>
        <button type="button" className="btn btn-secondary mt-2" onClick={() => { setReady(false); setError(""); setTileError(false); setAttempt((value) => value + 1); }}>Retry map</button>
      </div>}
      <div ref={container} aria-label="Interactive street map of Montreal" className="relative z-0 w-full rounded-2xl border border-[var(--color-border)]" style={{ height: "min(65vh, 620px)", minHeight: 340 }} />
      <div className="flex flex-wrap gap-4 mt-3 text-sm" aria-label="Map legend">
        {(Object.keys(legend) as Kind[]).filter((kind) => data?.points.some((point) => point.kind === kind)).map((kind) => <span key={kind} className="flex items-center gap-2"><span aria-hidden="true" className="h-3 w-3 rounded-full" style={{ background: legend[kind].color }} />{legend[kind].label}</span>)}
      </div>

      {data && !data.points.length && <p className="body-text mt-3">No locations to show yet.</p>}
      {!!data?.points.length && <details className="mt-4"><summary className="cursor-pointer font-semibold">Locations ({data.points.length})</summary><ul className="mt-3 space-y-2">{data.points.map((point) => <li key={point.id}><button type="button" className="text-left underline" onClick={() => mapRef.current?.setView([Number(point.latitude), Number(point.longitude)], 15)}>{point.label}</button><span className="form-help"> · {point.detail}</span></li>)}</ul></details>}
    </section>
  );
}
