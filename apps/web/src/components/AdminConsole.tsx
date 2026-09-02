import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import maplibregl from "maplibre-gl";
import {
  adminLogin,
  fetchAdminAudit,
  fetchAdminPreview,
  fetchAdminStates,
  publishAdminUpload,
  rollbackAdminUpload,
  uploadAdminGis,
  type StateOption,
} from "../api";
import { DEFAULT_BASEMAP_ID, getBasemap } from "../lib/basemap";
import brandLogo from "../assets/propinsight-logo.png";

type UploadResult = {
  id: number;
  status: string;
  validation_report: Record<string, unknown>;
};

const TARGETS = [
  ["states", "State boundaries"],
  ["lgas", "LGA boundaries"],
  ["wards", "Ward boundaries"],
  ["masterplans", "Masterplans"],
] as const;

function readinessClass(readiness: string) {
  if (readiness === "ready") return "bg-emerald-100 text-emerald-700";
  if (readiness === "partial") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-600";
}

function GeoJsonPreview({ collection }: { collection: GeoJSON.FeatureCollection | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const map = new maplibregl.Map({
      container,
      style: getBasemap(DEFAULT_BASEMAP_ID).style,
      center: [8, 9.6],
      zoom: 4.8,
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !collection) return;
    const apply = () => {
      if (map.getLayer("admin-preview-fill")) map.removeLayer("admin-preview-fill");
      if (map.getLayer("admin-preview-line")) map.removeLayer("admin-preview-line");
      if (map.getSource("admin-preview")) map.removeSource("admin-preview");
      map.addSource("admin-preview", { type: "geojson", data: collection });
      map.addLayer({
        id: "admin-preview-fill",
        type: "fill",
        source: "admin-preview",
        paint: { "fill-color": "#10b981", "fill-opacity": 0.18 },
      });
      map.addLayer({
        id: "admin-preview-line",
        type: "line",
        source: "admin-preview",
        paint: { "line-color": "#047857", "line-width": 2 },
      });
      const coords: number[][] = [];
      const collect = (value: unknown) => {
        if (!Array.isArray(value)) return;
        if (typeof value[0] === "number" && typeof value[1] === "number") {
          coords.push(value as number[]);
          return;
        }
        value.forEach(collect);
      };
      collection.features.forEach((feature) => {
        const geometry = feature.geometry;
        if (geometry && "coordinates" in geometry) collect(geometry.coordinates);
      });
      if (coords.length) {
        const bounds = coords.reduce(
          (b, coord) => b.extend([coord[0], coord[1]]),
          new maplibregl.LngLatBounds([coords[0][0], coords[0][1]], [coords[0][0], coords[0][1]]),
        );
        map.fitBounds(bounds, { padding: 36, duration: 500, maxZoom: 11 });
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [collection]);

  return <div ref={containerRef} className="h-72 overflow-hidden rounded-3xl border border-slate-200 bg-slate-100" />;
}

export function AdminConsole() {
  const [token, setToken] = useState(() => localStorage.getItem("propinsight_admin_token") ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [states, setStates] = useState<StateOption[]>([]);
  const [audit, setAudit] = useState<Array<Record<string, unknown>>>([]);
  const [target, setTarget] = useState("masterplans");
  const [stateCode, setStateCode] = useState("FC");
  const [sourceName, setSourceName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [licenseNote, setLicenseNote] = useState("");
  const [attributeMapping, setAttributeMapping] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [preview, setPreview] = useState<GeoJSON.FeatureCollection | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedState = useMemo(
    () => states.find((state) => state.code === stateCode),
    [stateCode, states],
  );

  const refresh = async (authToken = token) => {
    if (!authToken) return;
    const [stateRows, auditRows] = await Promise.all([
      fetchAdminStates(authToken),
      fetchAdminAudit(authToken),
    ]);
    setStates(stateRows);
    setAudit(auditRows);
    if (!stateRows.some((state) => state.code === stateCode)) {
      setStateCode(stateRows.find((state) => state.code === "FC")?.code ?? stateRows[0]?.code ?? "FC");
    }
  };

  useEffect(() => {
    if (!token) return;
    refresh().catch(() => {
      localStorage.removeItem("propinsight_admin_token");
      setToken("");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await adminLogin(email, password);
      localStorage.setItem("propinsight_admin_token", result.access_token);
      setToken(result.access_token);
      setNotice(`Signed in as ${result.user.email}`);
    } catch (err) {
      setError((err as Error).message || "Login failed.");
    } finally {
      setBusy(false);
    }
  };

  const submitUpload = async () => {
    if (!file) {
      setError("Choose a zipped shapefile or GeoJSON file first.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    setPreview(null);
    try {
      const form = new FormData();
      form.append("target_layer", target);
      form.append("source_name", sourceName || "Admin GIS upload");
      if (target !== "states") form.append("state_code", stateCode);
      if (sourceUrl) form.append("source_url", sourceUrl);
      if (licenseNote) form.append("license_note", licenseNote);
      if (attributeMapping.trim()) form.append("attribute_mapping", attributeMapping);
      form.append("file", file);
      const result = await uploadAdminGis(token, form);
      setUpload(result);
      setNotice(result.status === "validated" ? "Upload validated and ready to preview." : "Upload stored but validation found blockers.");
      const previewRows = await fetchAdminPreview(token, result.id);
      setPreview(previewRows);
      await refresh();
    } catch (err) {
      setError((err as Error).message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      const result = await publishAdminUpload(token, upload.id);
      setNotice(`Published ${target} version ${result.version} for ${result.states.join(", ")}.`);
      await refresh();
    } catch (err) {
      setError((err as Error).message || "Publish failed.");
    } finally {
      setBusy(false);
    }
  };

  const rollback = async () => {
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      const result = await rollbackAdminUpload(token, upload.id);
      setNotice(`Rolled back batch ${result.id}${result.restored_version ? ` to ${result.restored_version}` : ""}.`);
      await refresh();
    } catch (err) {
      setError((err as Error).message || "Rollback failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-sky-50 via-white to-emerald-50 p-5">
        <section className="w-full max-w-md rounded-[2rem] border border-white/70 bg-white/80 p-7 shadow-2xl backdrop-blur-2xl">
          <div className="flex items-center gap-3">
            <img src={brandLogo} alt="" className="h-12 w-12 object-contain" />
            <div>
              <h1 className="text-2xl font-black text-slate-950">PropInsight Admin</h1>
              <p className="text-sm text-slate-500">GIS data QA and publishing console</p>
            </div>
          </div>
          <label className="mt-6 block text-sm font-bold text-slate-700">
            Email
            <input className="mt-2 h-12 w-full rounded-2xl border border-slate-200 px-4 outline-none focus:border-emerald-400" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="mt-4 block text-sm font-bold text-slate-700">
            Password
            <input type="password" className="mt-2 h-12 w-full rounded-2xl border border-slate-200 px-4 outline-none focus:border-emerald-400" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <button type="button" disabled={busy} onClick={() => void login()} className="mt-6 w-full rounded-2xl bg-emerald-500 px-5 py-3 font-black text-white shadow-lg hover:bg-emerald-600 disabled:cursor-wait disabled:opacity-60">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-emerald-50 p-5 text-slate-900">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-[2rem] border border-white/70 bg-white/75 p-5 shadow-xl backdrop-blur-2xl">
          <div className="flex items-center gap-3">
            <img src={brandLogo} alt="" className="h-12 w-12 object-contain" />
            <div>
              <h1 className="text-2xl font-black">Admin GIS Console</h1>
              <p className="text-sm text-slate-500">Upload, validate, preview, publish and rollback nationwide layers.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              localStorage.removeItem("propinsight_admin_token");
              setToken("");
            }}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50"
          >
            Sign out
          </button>
        </header>

        {(notice || error) && (
          <div className={clsx("mt-4 rounded-2xl px-4 py-3 text-sm font-bold", error ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700")}>
            {error ?? notice}
          </div>
        )}

        <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
          <section className="rounded-[2rem] border border-white/70 bg-white/78 p-5 shadow-xl backdrop-blur-2xl">
            <h2 className="text-lg font-black">New GIS upload</h2>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="text-sm font-bold">
                Target layer
                <select value={target} onChange={(event) => setTarget(event.target.value)} className="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-white px-3">
                  {TARGETS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="text-sm font-bold">
                State
                <select value={stateCode} onChange={(event) => setStateCode(event.target.value)} disabled={target === "states"} className="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-white px-3 disabled:bg-slate-100">
                  {states.map((state) => <option key={state.code} value={state.code}>{state.name} · {state.readiness_label}</option>)}
                </select>
              </label>
              <label className="text-sm font-bold">
                Source name
                <input value={sourceName} onChange={(event) => setSourceName(event.target.value)} placeholder="Official source / agency" className="mt-2 h-12 w-full rounded-2xl border border-slate-200 px-4" />
              </label>
              <label className="text-sm font-bold">
                Source URL
                <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://…" className="mt-2 h-12 w-full rounded-2xl border border-slate-200 px-4" />
              </label>
              <label className="text-sm font-bold md:col-span-2">
                License / reuse note
                <input value={licenseNote} onChange={(event) => setLicenseNote(event.target.value)} placeholder="Official reuse terms, internal-only note, etc." className="mt-2 h-12 w-full rounded-2xl border border-slate-200 px-4" />
              </label>
              <label className="text-sm font-bold md:col-span-2">
                Attribute mapping JSON
                <textarea
                  value={attributeMapping}
                  onChange={(event) => setAttributeMapping(event.target.value)}
                  placeholder='{"source_id":"LGA_CODE","name":"LGA_NAME","state_code":"STATE_CODE"}'
                  className="mt-2 h-24 w-full rounded-2xl border border-slate-200 px-4 py-3 font-mono text-xs"
                />
              </label>
              <label className="rounded-2xl border border-dashed border-emerald-300 bg-emerald-50/60 p-4 text-sm font-bold md:col-span-2">
                Zipped shapefile or GeoJSON
                <input type="file" accept=".zip,.geojson,.json,application/geo+json,application/json" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-3 block w-full text-sm" />
              </label>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <button type="button" disabled={busy} onClick={() => void submitUpload()} className="rounded-2xl bg-emerald-500 px-5 py-3 font-black text-white shadow-lg hover:bg-emerald-600 disabled:cursor-wait disabled:opacity-60">
                {busy ? "Working…" : "Upload and validate"}
              </button>
              <button type="button" disabled={busy || !upload || upload.status !== "validated"} onClick={() => void publish()} className="rounded-2xl bg-sky-500 px-5 py-3 font-black text-white shadow-lg hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50">
                Publish
              </button>
              <button type="button" disabled={busy || !upload} onClick={() => void rollback()} className="rounded-2xl border border-slate-200 bg-white px-5 py-3 font-black text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
                Roll back batch
              </button>
            </div>
          </section>

          <section className="rounded-[2rem] border border-white/70 bg-white/78 p-5 shadow-xl backdrop-blur-2xl">
            <h2 className="text-lg font-black">Validation and preview</h2>
            {upload ? (
              <div className="mt-4 space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-black">Batch #{upload.id} · {upload.status}</p>
                  <pre className="mt-3 max-h-52 overflow-auto text-xs text-slate-700">{JSON.stringify(upload.validation_report, null, 2)}</pre>
                </div>
                <GeoJsonPreview collection={preview} />
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Upload a layer to see validation blockers, warnings, feature counts, detected fields and a map preview.</p>
            )}
          </section>
        </div>

        <section className="mt-5 grid gap-5 xl:grid-cols-[.9fr_1.1fr]">
          <div className="rounded-[2rem] border border-white/70 bg-white/78 p-5 shadow-xl backdrop-blur-2xl">
            <h2 className="text-lg font-black">State readiness</h2>
            <div className="mt-4 max-h-[32rem] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white/95 text-xs uppercase text-slate-500">
                  <tr><th className="py-2">State</th><th>Status</th><th>Published layers</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {states.map((state) => {
                    const published = Object.values(state.layers || {}).filter((layer) => layer.status === "published").length;
                    return (
                      <tr key={state.code}>
                        <td className="py-2 font-bold">{state.name}</td>
                        <td><span className={clsx("rounded-full px-2 py-1 text-xs font-black", readinessClass(state.readiness))}>{state.readiness_label}</span></td>
                        <td className="text-slate-500">{published}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {selectedState && <p className="mt-3 text-xs text-slate-500">Selected state: {selectedState.name}. New uploads for this state will update its readiness badges after publishing.</p>}
          </div>

          <div className="rounded-[2rem] border border-white/70 bg-white/78 p-5 shadow-xl backdrop-blur-2xl">
            <h2 className="text-lg font-black">Audit trail</h2>
            <div className="mt-4 max-h-[32rem] overflow-auto divide-y divide-slate-100">
              {audit.map((row) => (
                <div key={String(row.id)} className="py-3 text-sm">
                  <p className="font-black">{String(row.action)} · {String(row.target_type)} #{String(row.target_id ?? "")}</p>
                  <p className="text-xs text-slate-500">{String(row.actor_email ?? "system")} · {String(row.created_at ?? "")}</p>
                </div>
              ))}
              {!audit.length && <p className="text-sm text-slate-500">No admin actions recorded yet.</p>}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
