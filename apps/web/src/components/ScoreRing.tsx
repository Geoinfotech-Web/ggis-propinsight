import clsx from "clsx";

type Props = {
  score: number | null;
  size?: "sm" | "md" | "lg";
  color?: string;
  label?: string;
  className?: string;
};

const SIZES = {
  sm: { shell: "h-14 w-14", inner: "inset-[6px]", text: "text-lg" },
  md: { shell: "h-20 w-20", inner: "inset-[8px]", text: "text-2xl" },
  lg: { shell: "h-24 w-24", inner: "inset-[9px]", text: "text-3xl" },
} as const;

export function ScoreRing({
  score,
  size = "md",
  color = "#0d9488",
  label = "Score",
  className,
}: Props) {
  const styles = SIZES[size];
  const value = score == null ? 0 : Math.min(100, Math.max(0, score));
  return (
    <div
      className={clsx("relative shrink-0 rounded-full", styles.shell, className)}
      style={{
        background: `conic-gradient(${color} ${value * 3.6}deg, #dbe3ec 0deg)`,
      }}
      role="img"
      aria-label={`${label}: ${score == null ? "unavailable" : `${Math.round(score)} out of 100`}`}
    >
      <div
        className={clsx(
          "absolute flex items-center justify-center rounded-full bg-white font-display font-semibold tabular-nums text-slate-900 dark:bg-gray-900 dark:text-gray-100",
          styles.inner,
          styles.text,
        )}
      >
        {score == null ? "—" : Math.round(score)}
      </div>
    </div>
  );
}
