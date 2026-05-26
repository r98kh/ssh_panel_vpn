import { useState } from "react";
import { ScrollText } from "lucide-react";
import { getLogs } from "../api/endpoints";
import { useFetch } from "../hooks/useFetch";
import { formatDateTime, actionLabel } from "../lib/utils";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";

const ACTION_COLORS: Record<string, string> = {
  create: "bg-emerald-500/20 text-emerald-400",
  delete: "bg-red-500/20 text-red-400",
  suspend: "bg-amber-500/20 text-amber-400",
  activate: "bg-blue-500/20 text-blue-400",
  extend: "bg-indigo-500/20 text-indigo-400",
  expire: "bg-gray-500/20 text-gray-400",
  password_reset: "bg-purple-500/20 text-purple-400",
  rebalance: "bg-cyan-500/20 text-cyan-400",
};

export default function LogsPage() {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const { data, loading } = useFetch(
    () => getLogs({ page, action: actionFilter || undefined } as any),
    [page, actionFilter],
  );

  if (loading && !data) return <div className="flex justify-center py-20"><Spinner className="w-10 h-10" /></div>;

  const logs = data?.results || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">لاگ‌ها</h1>
          <p className="text-gray-500 text-sm mt-1">{data?.count || 0} رکورد</p>
        </div>
        <select
          className="input w-44"
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
        >
          <option value="">همه عملیات‌ها</option>
          <option value="create">ایجاد</option>
          <option value="delete">حذف</option>
          <option value="suspend">تعلیق</option>
          <option value="activate">فعال‌سازی</option>
          <option value="extend">تمدید</option>
          <option value="expire">انقضا</option>
          <option value="password_reset">بازنشانی رمز</option>
        </select>
      </div>

      {logs.length === 0 ? (
        <EmptyState icon={<ScrollText className="w-12 h-12" />} title="لاگی یافت نشد" />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500">
                  <th className="text-right py-3 px-3 font-medium">عملیات</th>
                  <th className="text-right py-3 px-3 font-medium">اکانت</th>
                  <th className="text-right py-3 px-3 font-medium">ادمین</th>
                  <th className="text-right py-3 px-3 font-medium">جزئیات</th>
                  <th className="text-right py-3 px-3 font-medium">زمان</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-b border-gray-800/50 hover:bg-gray-900/50">
                    <td className="py-3 px-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ACTION_COLORS[l.action] || "bg-gray-700 text-gray-400"}`}>
                        {actionLabel(l.action)}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-indigo-400" dir="ltr">{l.account_username || "—"}</td>
                    <td className="py-3 px-3 text-gray-400" dir="ltr">{l.admin_username || "system"}</td>
                    <td className="py-3 px-3 text-gray-500 text-xs max-w-xs truncate">{l.detail || "—"}</td>
                    <td className="py-3 px-3 text-gray-600 text-xs whitespace-nowrap">{formatDateTime(l.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {(data?.count || 0) > 25 && (
            <div className="flex justify-center gap-2 mt-4">
              <button className="btn-secondary btn-sm" disabled={!data?.previous} onClick={() => setPage((p) => p - 1)}>قبلی</button>
              <span className="text-gray-500 text-sm py-1.5">صفحه {page}</span>
              <button className="btn-secondary btn-sm" disabled={!data?.next} onClick={() => setPage((p) => p + 1)}>بعدی</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
