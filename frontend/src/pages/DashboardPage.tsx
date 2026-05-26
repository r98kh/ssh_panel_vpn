import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Users,
  Server,
  Activity,
  AlertTriangle,
  UserCheck,
  UserX,
  Clock,
  Plus,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getDashboard } from "../api/endpoints";
import type { DashboardData } from "../lib/types";
import { actionLabel, formatDateTime } from "../lib/utils";
import Spinner from "../components/Spinner";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = () => {
    getDashboard()
      .then((r) => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner className="w-10 h-10" />
      </div>
    );
  }

  if (!data) return null;

  const statCards = [
    { label: "کل اکانت‌ها", value: data.accounts.total, icon: Users, color: "text-blue-400", bg: "bg-blue-500/10" },
    { label: "فعال", value: data.accounts.active, icon: UserCheck, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "منقضی", value: data.accounts.expired, icon: Clock, color: "text-red-400", bg: "bg-red-500/10" },
    { label: "معلق", value: data.accounts.suspended, icon: UserX, color: "text-amber-400", bg: "bg-amber-500/10" },
    { label: "سشن‌های فعال", value: data.active_sessions, icon: Activity, color: "text-cyan-400", bg: "bg-cyan-500/10" },
    { label: "سرورهای آنلاین", value: `${data.servers.online}/${data.servers.total}`, icon: Server, color: "text-indigo-400", bg: "bg-indigo-500/10" },
  ];

  const chartData = [
    { name: "فعال", value: data.accounts.active, color: "#10b981" },
    { name: "منقضی", value: data.accounts.expired, color: "#ef4444" },
    { name: "معلق", value: data.accounts.suspended, color: "#f59e0b" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">داشبورد</h1>
          <p className="text-gray-500 text-sm mt-1">نمای کلی سیستم</p>
        </div>
        <Link to="/accounts" className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          اکانت جدید
        </Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        {statCards.map((card) => (
          <div key={card.label} className="card flex flex-col items-center text-center py-5">
            <div className={`w-10 h-10 rounded-lg ${card.bg} flex items-center justify-center mb-3`}>
              <card.icon className={`w-5 h-5 ${card.color}`} />
            </div>
            <div className="text-2xl font-bold text-white">{card.value}</div>
            <div className="text-xs text-gray-500 mt-1">{card.label}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">وضعیت اکانت‌ها</h2>
          <div className="h-64" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barCategoryGap="30%">
                <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                <YAxis stroke="#6b7280" fontSize={12} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
                  labelStyle={{ color: "#fff" }}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4">آخرین فعالیت‌ها</h2>
          {data.servers.down > 0 && (
            <div className="flex items-center gap-2 bg-red-900/20 border border-red-800 text-red-400 px-3 py-2 rounded-lg text-sm mb-4">
              <AlertTriangle className="w-4 h-4" />
              {data.servers.down} سرور آفلاین
            </div>
          )}
          <div className="space-y-3 max-h-56 overflow-y-auto">
            {data.recent_logs.length === 0 ? (
              <p className="text-gray-500 text-sm">بدون فعالیت</p>
            ) : (
              data.recent_logs.map((log) => (
                <div key={log.id} className="flex items-center justify-between text-sm border-b border-gray-800 pb-2">
                  <div>
                    <span className="text-gray-300">{actionLabel(log.action)}</span>
                    {log.account_username && (
                      <span className="text-indigo-400 mr-2">{log.account_username}</span>
                    )}
                  </div>
                  <span className="text-gray-600 text-xs" dir="ltr">{formatDateTime(log.created_at)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
