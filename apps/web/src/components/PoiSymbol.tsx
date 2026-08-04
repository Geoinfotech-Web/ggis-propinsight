import { POI_SYMBOL_PATHS } from "../lib/amenitiesMap";

type Props = {
  category: string;
  color: string;
  size?: number;
};

export function PoiSymbol({ category, color, size = 20 }: Props) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full border border-white shadow-sm"
      style={{ width: size, height: size, backgroundColor: color, color: "white" }}
      aria-hidden
    >
      <svg
        width={Math.max(11, size - 7)}
        height={Math.max(11, size - 7)}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {(POI_SYMBOL_PATHS[category] ?? POI_SYMBOL_PATHS.market).map((path, index) => (
          <path key={`${category}-${index}`} d={path} />
        ))}
      </svg>
    </span>
  );
}
