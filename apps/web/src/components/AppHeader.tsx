import { useEffect, useRef, useState, type ReactNode } from "react";
import clsx from "clsx";
import type { Theme } from "../theme";
import { IconBrandMark, IconEdit, IconExternalLink, IconMoon, IconReport, IconSun } from "./Icons";

type Props = {
  theme: Theme;
  onToggleTheme: () => void;
  reportTitle: string;
  onReportTitleChange: (title: string) => void;
  reportGuideAvailable?: boolean;
  onOpenReportGuide: () => void;
  reportAvailable?: boolean;
  reportGenerating?: boolean;
  shareGenerating?: boolean;
  onGenerateReport: () => void;
  onShareReport: () => void;
  mobileToolbar?: ReactNode;
};

export function AppHeader({
  theme,
  onToggleTheme,
  reportTitle,
  onReportTitleChange,
  reportGuideAvailable = false,
  onOpenReportGuide,
  reportAvailable = false,
  reportGenerating = false,
  shareGenerating = false,
  onGenerateReport,
  onShareReport,
  mobileToolbar,
}: Props) {
  const dark = theme === "dark";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(reportTitle);
  const originalRef = useRef(reportTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) setDraft(reportTitle);
  }, [editing, reportTitle]);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const beginEditing = () => {
    originalRef.current = reportTitle;
    setDraft(reportTitle);
    setEditing(true);
  };

  const commit = () => {
    const next = draft.trim();
    onReportTitleChange(next || originalRef.current || "Untitled 1");
    setEditing(false);
  };

  const cancel = () => {
    setDraft(originalRef.current);
    setEditing(false);
  };

  return (
    <header className={clsx(
      "relative z-30 shrink-0 border-b pt-[env(safe-area-inset-top)] backdrop-blur-xl",
      dark ? "border-gray-800 bg-gray-950/95 text-gray-100" : "border-slate-200/80 bg-white/95 text-slate-900",
    )}>
      <div className="flex min-h-[4.5rem] items-center gap-3 px-4 py-2 sm:px-6">
        <div className="flex min-w-0 shrink-0 items-center gap-2.5 sm:w-64">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center text-teal-500">
            <IconBrandMark size={42} />
          </div>
          <div className="min-w-0">
            <h1 className="truncate font-display text-lg font-bold tracking-tight sm:text-xl">PropInsight</h1>
            <p className={clsx("hidden truncate text-[11px] sm:block", dark ? "text-gray-400" : "text-slate-400")}>
              FCT pilot · location scorecard
            </p>
          </div>
        </div>

        <div className="hidden min-w-0 flex-1 items-center md:flex">
          {editing ? (
            <input
              ref={inputRef}
              value={draft}
              maxLength={80}
              onChange={(event) => setDraft(event.target.value)}
              onBlur={commit}
              onKeyDown={(event) => {
                if (event.key === "Enter") commit();
                if (event.key === "Escape") cancel();
              }}
              aria-label="Report title"
              className={clsx(
                "h-11 w-full max-w-xs rounded-2xl border px-4 text-base outline-none transition focus:border-sky-500",
                dark ? "border-gray-700 bg-gray-900 text-gray-100" : "border-slate-200 bg-white text-slate-800 shadow-sm",
              )}
            />
          ) : (
            <button
              type="button"
              onClick={beginEditing}
              className={clsx(
                "group flex h-11 min-w-0 max-w-xs items-center gap-3 rounded-2xl border px-4 text-left transition",
                dark ? "border-gray-800 bg-gray-900/80 hover:border-gray-700" : "border-transparent bg-white hover:border-slate-200 hover:shadow-sm",
              )}
              aria-label={`Edit report title: ${reportTitle}`}
            >
              <span className="min-w-0 flex-1 truncate text-base font-medium">{reportTitle}</span>
              <IconEdit size={17} className={clsx("shrink-0", dark ? "text-gray-500 group-hover:text-gray-300" : "text-slate-400 group-hover:text-slate-600")} />
            </button>
          )}
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
          <button type="button" onClick={onOpenReportGuide} disabled={!reportGuideAvailable} className={clsx(
            "hidden h-10 items-center justify-center rounded-xl border px-4 text-sm font-semibold transition sm:inline-flex",
            dark ? "border-gray-700 text-gray-200 hover:bg-gray-800" : "border-slate-200 text-slate-600 hover:bg-slate-50",
            !reportGuideAvailable && "cursor-not-allowed opacity-45",
          )}>Report guide</button>
          <button type="button" onClick={onShareReport} disabled={!reportAvailable || shareGenerating || reportGenerating} className={clsx(
            "inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-semibold transition sm:px-4",
            dark ? "border-gray-700 text-gray-200 hover:bg-gray-800" : "border-slate-200 text-slate-600 hover:bg-slate-50",
            (!reportAvailable || shareGenerating || reportGenerating) && "cursor-not-allowed opacity-45",
          )} aria-label="Share report">
            <IconExternalLink size={16} />
            <span className="hidden lg:inline">{shareGenerating ? "Preparing…" : "Share Report"}</span>
          </button>
          <button type="button" onClick={onGenerateReport} disabled={!reportAvailable || reportGenerating || shareGenerating} className={clsx(
            "inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#087df1] px-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 sm:px-5",
            (!reportAvailable || reportGenerating || shareGenerating) && "cursor-not-allowed opacity-45",
          )} aria-label="Generate PDF report">
            <IconReport size={16} />
            <span className="hidden lg:inline">{reportGenerating ? "Generating…" : "Generate report"}</span>
          </button>
          <button type="button" onClick={onToggleTheme} className={clsx(
            "inline-flex h-10 w-10 items-center justify-center rounded-xl border transition",
            dark ? "border-gray-700 text-gray-300 hover:bg-gray-800" : "border-slate-200 text-slate-500 hover:bg-slate-50",
          )} aria-label="Toggle theme" title="Toggle theme">
            {dark ? <IconSun size={16} /> : <IconMoon size={16} />}
          </button>
        </div>
      </div>
      {mobileToolbar && <div className="border-t border-inherit px-3 py-2 lg:hidden">{mobileToolbar}</div>}
    </header>
  );
}
