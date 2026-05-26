import { useParams, Link } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import {
  ArrowRight,
  Copy,
  ExternalLink,
  Server,
  Calendar,
  Wifi,
  HardDrive,
  Clock,
} from "lucide-react";
import { getAccount, getSessions, getLogs } from "../api/endpoints";
import type { SSHAccount, ActiveSession, AuditLog } from "../lib/types";
import { useFetch } from "../hooks/useFetch";
import { useToast } from "../context/ToastContext";
import StatusBadge from "../components/StatusBadge";
import ProgressBar from "../components/ProgressBar";
import Spinner from "../components/Spinner";
import { formatDate, formatDateTime, actionLabel } from "../lib/utils";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const { data: account, loading } = useFetch(() => getAccount(Number(id)), [id]);
  const { data: sessionsData } = useFetch(() => getSessions({ account__server: "" }), [id]);
  const { data: logsData } = useFetch(() => getLogs({ page: 1 }), [id]);

  if (loading || !account) {
    return <div className="flex justify-center py-20"><Spinner className="w-10 h-10" /></div>;
  }

  const a: SSHAccount = account;

  const accountSessions: ActiveSession[] = (sessionsData?.results || []).filter(
    (s: ActiveSession) => s.username === a.username,
  );
  const accountLogs: AuditLog[] = (logsData?.results || []).filter(
    (l: AuditLog) => l.account_username === a.username,
  );

  const sshUri = a.password_display
    ? `ssh://${a.username}:${a.password_display}@${a.server_ip}:${a.server_ssh_port}#${a.username}`
    : `ssh://${a.username}@${a.server_ip}:${a.server_ssh_port}#${a.username}`;
  const statusUrl = `${window.location.origin}/status/${a.access_token}`;
  const sshConfig = `Host vpn-${a.username}\n    HostName ${a.server_ip}\n    Port ${a.server_ssh_port}\n    User ${a.username}`;

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast("success", "کپی شد");
  };

  const bandwidthPercent =
    a.bandwidth_limit_gb > 0 ? (a.bandwidth_used_gb / a.bandwidth_limit_gb) * 100 : 0;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link to="/accounts" className="text-gray-400 hover:text-white">
          <ArrowRight className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white" dir="ltr">{a.username}</h1>
          <p className="text-gray-500 text-sm">جزئیات اکانت</p>
        </div>
        <div className="mr-auto">
          <StatusBadge status={a.status} />
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">اطلاعات اکانت</h2>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <InfoRow icon={<Server className="w-4 h-4" />} label="سرور" value={`${a.server_name} (${a.server_ip})`} />
              <InfoRow icon={<HardDrive className="w-4 h-4" />} label="پورت SSH" value={String(a.server_ssh_port)} />
              <InfoRow icon={<Calendar className="w-4 h-4" />} label="انقضا" value={formatDate(a.expire_date)} />
              <InfoRow icon={<Clock className="w-4 h-4" />} label="روز مانده" value={`${a.days_remaining} روز`} />
              <InfoRow icon={<Wifi className="w-4 h-4" />} label="اتصال همزمان" value={String(a.max_connections)} />
              <InfoRow
                icon={<HardDrive className="w-4 h-4" />}
                label="پلن"
                value={a.plan_name || "—"}
              />
            </div>

            {a.bandwidth_limit_gb > 0 && (
              <div className="mt-4">
                <ProgressBar
                  value={bandwidthPercent}
                  label={`حجم مصرفی: ${a.bandwidth_used_gb.toFixed(1)} / ${a.bandwidth_limit_gb} GB`}
                />
              </div>
            )}

            {a.password_display && (
              <div className="mt-4 bg-emerald-900/20 border border-emerald-800 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-emerald-400">رمز عبور:</span>
                  <div className="flex items-center gap-2">
                    <code className="text-emerald-300" dir="ltr">{a.password_display}</code>
                    <button onClick={() => copy(a.password_display)} className="text-gray-400 hover:text-white">
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {a.note && (
              <div className="mt-4 text-sm text-gray-500">
                <span className="text-gray-400">یادداشت: </span>{a.note}
              </div>
            )}
          </div>

          {/* SSH Config */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-white">تنظیمات SSH</h2>
              <button onClick={() => copy(sshConfig)} className="btn-secondary btn-sm flex items-center gap-1">
                <Copy className="w-3.5 h-3.5" /> کپی
              </button>
            </div>
            <pre className="bg-gray-800 rounded-lg p-4 text-sm text-green-400 overflow-x-auto" dir="ltr">
              {sshConfig}
            </pre>
          </div>

          {/* Sessions */}
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">سشن‌های فعال ({accountSessions.length})</h2>
            {accountSessions.length === 0 ? (
              <p className="text-gray-500 text-sm">سشن فعالی وجود ندارد</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-right py-2 font-medium">PID</th>
                    <th className="text-right py-2 font-medium">IP کلاینت</th>
                    <th className="text-right py-2 font-medium">زمان اتصال</th>
                  </tr>
                </thead>
                <tbody>
                  {accountSessions.map((s) => (
                    <tr key={s.id} className="border-b border-gray-800/50">
                      <td className="py-2 text-gray-400" dir="ltr">{s.pid}</td>
                      <td className="py-2 text-gray-400" dir="ltr">{s.client_ip || "—"}</td>
                      <td className="py-2 text-gray-400 text-xs">{formatDateTime(s.connected_since)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Audit Log */}
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">تاریخچه</h2>
            {accountLogs.length === 0 ? (
              <p className="text-gray-500 text-sm">بدون تاریخچه</p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {accountLogs.map((l) => (
                  <div key={l.id} className="flex items-center justify-between text-sm border-b border-gray-800/50 pb-2">
                    <div>
                      <span className="text-gray-300">{actionLabel(l.action)}</span>
                      {l.detail && <span className="text-gray-600 mr-2">{l.detail}</span>}
                    </div>
                    <span className="text-gray-600 text-xs" dir="ltr">{formatDateTime(l.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar: QR + Links */}
        <div className="space-y-6">
          <div className="card flex flex-col items-center">
            <h2 className="text-lg font-semibold text-white mb-4 self-start">QR Code اتصال</h2>
            <div className="bg-white p-4 rounded-xl mb-4">
              <QRCodeSVG value={sshUri} size={200} level="M" />
            </div>
            <p className="text-xs text-gray-500 text-center mb-2">با اسکن این کد به VPN متصل شوید</p>
            <code className="text-xs text-gray-600 bg-gray-800 px-3 py-1.5 rounded-lg" dir="ltr">
              {sshUri}
            </code>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-3">لینک وضعیت کاربر</h2>
            <p className="text-xs text-gray-500 mb-3">
              این لینک را به کاربر بدهید تا وضعیت اکانت خود را ببیند.
            </p>
            <div className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2">
              <input
                className="bg-transparent text-xs text-indigo-400 flex-1 outline-none"
                value={statusUrl}
                readOnly
                dir="ltr"
              />
              <button onClick={() => copy(statusUrl)} className="text-gray-400 hover:text-white shrink-0">
                <Copy className="w-4 h-4" />
              </button>
              <a href={statusUrl} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white shrink-0">
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-3">دستور اتصال سریع</h2>
            <div className="bg-gray-800 rounded-lg p-3">
              <code className="text-sm text-cyan-400 break-all" dir="ltr">
                ssh -D 1080 {a.username}@{a.server_ip} -p {a.server_ssh_port}
              </code>
            </div>
            <button
              onClick={() => copy(`ssh -D 1080 ${a.username}@${a.server_ip} -p ${a.server_ssh_port}`)}
              className="btn-secondary btn-sm w-full mt-2 flex items-center justify-center gap-1"
            >
              <Copy className="w-3.5 h-3.5" /> کپی دستور
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="text-gray-500">{icon}</div>
      <div>
        <div className="text-gray-500 text-xs">{label}</div>
        <div className="text-gray-200" dir="ltr">{value}</div>
      </div>
    </div>
  );
}
