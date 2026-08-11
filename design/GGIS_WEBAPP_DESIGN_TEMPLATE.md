# GGIS Webapp Design Template

Reusable visual system distilled from **Flood Watch** (Nigeria Flood Dashboard).  
Copy this folder into a new app, rename tokens to your product, keep the structure.

**PropInsight (this repo):** treat this file + `tokens.css` as the visual source of
truth. Adapt layout to the map + location-scorecard console — do not clone Flood
Watch alert chrome screen-for-screen. Web app wires tokens via `@design/tokens.css`
(`apps/web/vite.config.ts` alias).

---

## 1. Brand posture

| Rule | Practice |
|------|----------|
| Brand first | Product name is hero-level on branded surfaces — not only nav text |
| One job per section | One purpose, one headline, one short supporting line |
| Atmosphere | Prefer soft gradients / mist washes over flat single-color canvases |
| Avoid AI clichés | No purple-on-white defaults, cream+terracotta stacks, broadsheet hairlines, glow-pill overload |
| Cards sparingly | Cards only when they hold interaction; avoid card-wrapping everything |
| Motion | 2–3 intentional transitions; never decorative noise |

**Flood Watch accent family:** river sky / cyan / teal (water intelligence), slate ink, amber/orange/red for alerts.

---

## 2. Typography

| Role | Font | Usage |
|------|------|--------|
| Body / UI | **Source Sans 3** | Labels, tables, forms, map chrome |
| Display | **Source Sans 3** | Brand titles, panel H1/H2, KPI numbers |

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap"
  rel="stylesheet"
/>
```

```css
body { font-family: 'Source Sans 3', ui-sans-serif, system-ui, sans-serif; }
.font-display { font-family: 'Source Sans 3', ui-sans-serif, system-ui, sans-serif; }
```

**Type scale (common in Flood Watch)**

| Element | Classes / size |
|---------|----------------|
| Eyebrow / kicker | `text-[10px]`–`text-[11px] font-semibold uppercase tracking-[0.14em]`–`tracking-[0.18em]` + accent color |
| Page title | `font-display text-3xl`–`text-4xl font-semibold tracking-tight` |
| Panel title | `font-display text-xl font-semibold` or `text-sm font-semibold` in dense expert chrome |
| Body | `text-sm` / `text-xs` with `leading-relaxed` |
| Meta | `text-[11px]` muted slate |

---

## 3. Color tokens

See also [`tokens.css`](tokens.css). Rename `--app-*` for new products.

### Core brand

| Token | Value | Role |
|-------|-------|------|
| Ink | `#0f172a` | Primary text / dark surfaces |
| River | `#0369a1` | Brand link / river accent |
| Mist | `#e0f2fe` | Soft sky wash |
| Primary CTA | `sky-700` / `#0369a1` → hover `sky-600` | Buttons |
| Live / OK | teal / emerald | Status “Live”, Normal tier |

### Light shell

- Canvas: `bg-slate-100` or gradient `from-sky-50 via-white to-cyan-50/60`
- Panels: `bg-white/90`–`bg-white/95`, border `border-slate-200`
- Muted text: `text-slate-500` / `text-slate-400`

### Dark shell

- Canvas: `bg-gray-950` / `bg-slate-950`
- Panels: `bg-gray-900/95`, border `border-gray-800`
- Accent text: `text-sky-400`
- Muted: `text-gray-400` / `text-gray-500`

### Semantic alert ramp (ops / risk)

| Tier | Hex | Tailwind-ish |
|------|-----|----------------|
| Normal | `#0d9488` / `#22c55e` | teal / green |
| Watch | `#ca8a04` / `#eab308` | amber |
| Warning | `#ea580c` / `#f97316` | orange |
| Emergency | `#dc2626` / `#ef4444` | red |

### Domain layers (Flood Watch examples — swap per product)

| Layer | Palette idea |
|-------|----------------|
| Inundation probability | Deep navy → mid blue → light blue |
| Urban flash | Orange `#f97316` / purple `#86198f` (secondary hazard) |
| Susceptibility | Low orange `#c46210` → yellow `#fff600` → high blues `#2B6CB0` → `#0A3D62` |
| Hotspot heatmap | Blue → yellow → orange → red continuous ramp |

---

## 4. Layout patterns

### App chrome

```
┌─────────────────────────────────────────────┐
│ Header: brand · search · mode tabs · theme  │
│ Optional: alerts strip                      │
├──────────┬──────────────────────┬───────────┤
│ Side /   │  Map or main stage   │ Console / │
│ lists    │  (flex-1, min-h-0)   │ detail    │
│ (rem)    │                      │ (22–24rem)│
└──────────┴──────────────────────┴───────────┘
│ Disclaimer / footer                         │
```

- Root: `h-[100dvh] flex flex-col overflow-hidden`
- Mobile: map on top; bottom sheet `h-[min(48vh,26rem)]` rounded-t-2xl
- Desktop: side panels fixed width; map fills remainder

### PropInsight header recipe

Source of truth: nigeria-flood-webapp `PublicHeader.jsx` / `SearchBar.jsx` (not vendored here).
PropInsight mirrors that chrome in `apps/web/src/components/AppHeader.tsx` + `SearchBar.tsx`.

| Slot | Content |
|------|---------|
| Brand | Sky icon badge + compact `font-display text-sm sm:text-lg` + muted subtitle (`FCT pilot · location scorecard`, `lg+`) |
| Search | Mid-column `max-w-md` SearchBar (bordered shell, search/clear icons, `shadow-lg`, `focus-within:border-sky-500/70`) |
| Locate | Icon-only `h-10 w-10` square (`aria-label="Use my location"`), not a text CTA |
| Modes | Analyse / Compare Soon / Report Soon pill group |
| Theme | Icon toggle (sun/moon), not “Light”/“Dark” text |
| Shell | `backdrop-blur-md` + soft sky gradient wash |

**Desktop (sm+):** `[icon] Brand | Search [locate] | Live | modes | theme`.  
**Phone:** brand · modes · theme on row 1; search + locate on a **second row only** (`sm:hidden`).

### Mode tabs (Public / Expert / …)

- Pill group: `inline-flex rounded-lg border p-0.5`
- Active: solid `bg-sky-700 text-white`
- Disabled / soon: `opacity-45` + small “Soon” caption

### Panel header recipe

1. Accent kicker (uppercase tracking)
2. `font-display` title
3. One-line subtitle
4. Close / primary CTA aligned end

### Dense expert analytics

- Small uppercase section titles (`text-[10px] tracking-widest`)
- Compact rows `text-[11px]`, max-height scroll lists
- Avoid large card chrome in tables — hairline borders + hover only

---

## 5. Component recipes

### Primary button

```
rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-600
disabled:opacity-60
```

### Ghost / secondary

```
rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold
dark: border-slate-700 text-slate-300
```

### Status pill

```
rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase
+ tier-colored bg/border/text
```

### Form field

```
mt-1 w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2
light: border-slate-200 focus:ring-sky-200
dark:  border-slate-700 bg-slate-950 focus:ring-sky-800
```

### Toggle switch

- Track: off `bg-slate-300` / dark `bg-gray-600`; on `bg-sky-600`
- Thumb: white circle with translate

### Map popup

- Dark default surface `#0f172a`, border `#334155`, radius ~10px
- Light variant: `#f0f9ff` / slate text
- Eyebrow: tiny uppercase accent (`text-[8px] tracking-wide`)

---

## 6. Theme dual-mode pattern

Always branch on `theme === 'dark'`:

```jsx
const dark = theme === 'dark'
className={clsx(
  'rounded-xl border',
  dark ? 'border-gray-800 bg-gray-900/95 text-gray-100' : 'border-slate-200 bg-white/95 text-slate-900',
)}
```

Prefer **semantic pairs** (border / bg / text) rather than opacity-only swaps.

---

## 7. Motion & polish

- Live pulse: `animate-pulse` on a 1.5px teal dot
- Spinners: `border-2 border-slate-300 border-t-sky-600 animate-spin`
- Map flyTo: ~1200–1300ms
- Scrollbars: 4px thumb `#94a3b8`, transparent track
- Safe areas: `pt-[env(safe-area-inset-top)]` on header

---

## 8. Content & voice

- Public copy: plain language (“Flood watch”, “No flood alert”) — avoid ops jargon
- Expert copy: denser, actionable checklists
- Disclaimers: small muted footer; advisory ≠ legal/engineering sign-off
- Numbers: `tabular-nums` for gauges, %, distances

---

## 9. Starter checklist (new webapp)

1. Paste Google Fonts link + [`tokens.css`](tokens.css) into global CSS  
2. Extend Tailwind `fontFamily.sans` / `fontFamily.display` (see [`tailwind.theme.snippet.js`](tailwind.theme.snippet.js))  
3. Pick one accent family (Flood Watch → sky/teal; do not default to purple)  
4. Build: Header → mode shell → main stage → optional side console  
5. Define semantic status colors before feature colors  
6. Ship light + dark from day one with `clsx` pairs  
7. Mobile: bottom sheet over map; desktop: side rails  

---

## 10. File map (Flood Watch reference)

| Concern | Where in Flood Watch |
|---------|----------------------|
| Global CSS / map chrome | `frontend/src/index.css` |
| Fonts | `frontend/index.html`, `tailwind.config.js` |
| Risk / susceptibility colors | `frontend/src/lib/riskCopy.js` |
| Hotspot ramp | `frontend/src/lib/floodHotspotStyle.js` |
| Public header / brand | `frontend/src/components/PublicHeader.jsx` |
| Marketing-ish API page | `frontend/src/components/DevelopersPage.jsx` |
| Staff dense UI | `frontend/src/components/admin/AdminApp.jsx` |

---

## 11. Anti-patterns (do not copy)

- Flat purple hero or indigo glow CTAs by default  
- Card grid in the first viewport of a branded landing  
- Mixing 4+ accent hues without a primary  
- System UI font only for branded product pages  
- Showing raw API hosts as if they were API keys  

---

*Source product: Flood Watch · Geoinfotech / GGIS · template for sibling webapps.*
