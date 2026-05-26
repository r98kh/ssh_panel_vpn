import { classNames } from "../lib/utils";

interface Props {
  value: number;
  label?: string;
  showPercent?: boolean;
  size?: "sm" | "md";
}

export default function ProgressBar({ value, label, showPercent = true, size = "md" }: Props) {
  const clamped = Math.min(100, Math.max(0, value));
  const color =
    clamped > 90 ? "bg-red-500" : clamped > 70 ? "bg-amber-500" : "bg-emerald-500";

  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>{label}</span>
          {showPercent && <span>{clamped.toFixed(1)}%</span>}
        </div>
      )}
      <div
        className={classNames(
          "w-full bg-gray-700 rounded-full overflow-hidden",
          size === "sm" ? "h-1.5" : "h-2.5",
        )}
      >
        <div
          className={`${color} h-full rounded-full transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
