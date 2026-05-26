import { useParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import {
  Shield,
  Server,
  Calendar,
  Clock,
  Wifi,
  HardDrive,
  MapPin,
  Copy,
  CheckCircle,
  AlertTriangle,
  XCircle,
} from "lucide-react";
import { getPublicStatus } from "../api/endpoints";
import type { PublicAccountStatus } from "../lib/types";
import { useFetch } from "../hooks/useFetch";
import ProgressBar from "../components/ProgressBar";
import Spinner from "../components/Spinner";
import { formatDate, statusLabel } from "../lib/utils";
import { useState } from "react";

export default function UserStatusPage() {
  const { token } = useParams<{ token: string }>();
  const { data, loading, error } = useFetch(() => getPublicStatus(token!), [token]);
  const [copied, setCopied] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="w-10 h-10" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center px-4">
        <XCircle className="w-16 h-16 text-red-500 mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">اکانت یافت نشد</h2>
        <p className="text-gray-500">لینک نامعتبر است یا اکانت حذف شده است.</p>
      </div>
    );
  }

  const a: PublicAccountStatus = data;
  const sshUri = `ssh://${a.username}@${a.server_ip}:${a.server_ssh_port}`;
  const sshCommand = `ssh -D 1080 ${a.username}@${a.server_ip} -p ${a.server_ssh_port}`;
  const bandwidthPercent =
    a.bandwidth_limit_gb > 0 ? (a.bandwidth_used_gb / a.bandwidth_limit_gb) * 100 : 0;

  const StatusIcon = a.status === "active" ? CheckCircle : a.status === "expired" ? XCircle : AlertTriangle;
  const statusColorClass =
    a.status === "active" ? "text-emerald-400" : a.status === "expired" ? "text-red-400" : "text-amber-400";
  const statusBgClass =
    a.status === "active"
      ? "bg-emerald-500/10 border-emerald-500/30"
      : a.status === "expired"
        ? "bg-red-500/10 border-red-500/30"
        : "bg-amber-500/10 border-amber-500/30";

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Status Header */}
      <div className={`rounded-2xl border p-6 mb-6 text-center ${statusBgClass}`}>
        <StatusIcon className={`w-12 h-12 mx-auto mb-3 ${statusColorClass}`} />
        <h1 className="text-2xl font-bold text-white mb-1" dir="ltr">{a.username}</h1>
        <p className={`text-lg font-medium ${statusColorClass}`}>{statusLabel(a.status)}</p>
        {a.status === "active" && (
          <p className="text-gray-400 text-sm mt-2">
            {a.days_remaining} روز باقی‌مانده
          </p>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Account Info */}
        <div className="card">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-indigo-400" />
            اطلاعات اکانت
          </h2>
          <div className="space-y-3 text-sm">
            <InfoItem icon={<Server className="w-4 h-4" />} label="سرور" value={a.server_ip} />
            <InfoItem icon={<HardDrive className="w-4 h-4" />} label="پورت" value={String(a.server_ssh_port)} />
            {a.server_location && <InfoItem icon={<MapPin className="w-4 h-4" />} label="موقعیت" value={a.server_location} />}
            <InfoItem icon={<Wifi className="w-4 h-4" />} label="اتصال همزمان" value={String(a.max_connections)} />
            <InfoItem icon={<Calendar className="w-4 h-4" />} label="انقضا" value={formatDate(a.expire_date)} />
            <InfoItem icon={<Clock className="w-4 h-4" />} label="پلن" value={a.plan_name || "—"} />
          </div>

          {a.bandwidth_limit_gb > 0 && (
            <div className="mt-4">
              <ProgressBar
                value={bandwidthPercent}
                label={`حجم مصرفی: ${a.bandwidth_used_gb < 1 ? (a.bandwidth_used_gb * 1024).toFixed(1) + ' MB' : a.bandwidth_used_gb.toFixed(2) + ' GB'} / ${a.bandwidth_limit_gb} GB`}
              />
            </div>
          )}
          {a.bandwidth_limit_gb === 0 && (
            <div className="mt-4 text-sm text-gray-500 flex items-center gap-2">
              <HardDrive className="w-4 h-4" />
              حجم نامحدود
            </div>
          )}
        </div>

        {/* QR Code */}
        <div className="card flex flex-col items-center">
          <h2 className="text-lg font-semibold text-white mb-4 self-start">QR Code اتصال</h2>
          <div className="bg-white p-4 rounded-xl mb-4">
            <QRCodeSVG value={sshUri} size={180} level="M" />
          </div>
          <p className="text-xs text-gray-500 text-center">
            QR Code را اسکن کنید یا دستور زیر را اجرا کنید
          </p>
        </div>
      </div>

      {/* Connection Command */}
      <div className="card mt-6">
        <h2 className="text-lg font-semibold text-white mb-3">دستور اتصال</h2>
        <p className="text-sm text-gray-500 mb-3">
          دستور زیر را در ترمینال اجرا کنید تا از طریق SOCKS5 پروکسی به VPN متصل شوید:
        </p>
        <div className="flex items-center gap-2 bg-gray-800 rounded-lg p-3">
          <code className="text-sm text-cyan-400 flex-1 break-all" dir="ltr">{sshCommand}</code>
          <button
            onClick={() => copy(sshCommand)}
            className="text-gray-400 hover:text-white shrink-0 p-1"
          >
            {copied ? <CheckCircle className="w-5 h-5 text-emerald-400" /> : <Copy className="w-5 h-5" />}
          </button>
        </div>
        <div className="mt-4 bg-gray-800/50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
          <p>پس از اجرای دستور بالا, پروکسی SOCKS5 روی <code dir="ltr" className="text-gray-400">localhost:1080</code> فعال می‌شود.</p>
          <p>در مرورگر یا سیستم عامل خود, آدرس پروکسی را روی <code dir="ltr" className="text-gray-400">socks5://127.0.0.1:1080</code> تنظیم کنید.</p>
        </div>
      </div>
    </div>
  );
}

function InfoItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-800/50">
      <div className="flex items-center gap-2 text-gray-500">
        {icon}
        <span>{label}</span>
      </div>
      <span className="text-gray-200 font-medium" dir="ltr">{value}</span>
    </div>
  );
}
