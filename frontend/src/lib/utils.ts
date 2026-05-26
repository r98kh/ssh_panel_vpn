export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fa-IR", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("fa-IR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

export function classNames(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function statusColor(status: string): string {
  switch (status) {
    case "active":
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    case "suspended":
      return "bg-amber-500/20 text-amber-400 border-amber-500/30";
    case "expired":
      return "bg-red-500/20 text-red-400 border-red-500/30";
    case "deleted":
      return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    case "maintenance":
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    case "full":
      return "bg-orange-500/20 text-orange-400 border-orange-500/30";
    case "down":
      return "bg-red-500/20 text-red-400 border-red-500/30";
    default:
      return "bg-gray-500/20 text-gray-400 border-gray-500/30";
  }
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "فعال",
    suspended: "معلق",
    expired: "منقضی",
    deleted: "حذف شده",
    maintenance: "تعمیرات",
    full: "پر",
    down: "آفلاین",
  };
  return labels[status] || status;
}

export function actionLabel(action: string): string {
  const labels: Record<string, string> = {
    create: "ایجاد",
    delete: "حذف",
    suspend: "تعلیق",
    activate: "فعال‌سازی",
    extend: "تمدید",
    expire: "انقضا",
    password_reset: "بازنشانی رمز",
    rebalance: "توزیع مجدد",
  };
  return labels[action] || action;
}
