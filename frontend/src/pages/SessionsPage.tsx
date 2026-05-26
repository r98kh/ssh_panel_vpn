import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { getSessions } from "../api/endpoints";
import type { ActiveSession, PaginatedResponse } from "../lib/types";
import { formatDateTime } from "../lib/utils";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";

export default function SessionsPage() {
  const [data, setData] = useState<PaginatedResponse<ActiveSession> | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = () => {
    getSessions()
      .then((r) => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Spinner className="w-10 h-10" /></div>;

  const sessions = data?.results || [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">سشن‌های فعال</h1>
        <p className="text-gray-500 text-sm mt-1">{sessions.length} سشن · بروزرسانی خودکار هر ۱۵ ثانیه</p>
      </div>

      {sessions.length === 0 ? (
        <EmptyState icon={<Activity className="w-12 h-12" />} title="سشن فعالی وجود ندارد" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500">
                <th className="text-right py-3 px-3 font-medium">کاربر</th>
                <th className="text-right py-3 px-3 font-medium">سرور</th>
                <th className="text-right py-3 px-3 font-medium">PID</th>
                <th className="text-right py-3 px-3 font-medium">IP کلاینت</th>
                <th className="text-right py-3 px-3 font-medium">زمان اتصال</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-900/50">
                  <td className="py-3 px-3 text-indigo-400 font-medium" dir="ltr">{s.username}</td>
                  <td className="py-3 px-3 text-gray-400" dir="ltr">{s.server_ip}</td>
                  <td className="py-3 px-3 text-gray-400" dir="ltr">{s.pid}</td>
                  <td className="py-3 px-3 text-gray-400" dir="ltr">{s.client_ip || "—"}</td>
                  <td className="py-3 px-3 text-gray-500 text-xs">{formatDateTime(s.connected_since)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
