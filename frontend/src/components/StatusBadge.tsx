import { statusColor, statusLabel } from "../lib/utils";

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusColor(status)}`}
    >
      {statusLabel(status)}
    </span>
  );
}
