import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Server,
  CreditCard,
  Users,
  Activity,
  ScrollText,
  LogOut,
  Shield,
  ChevronRight,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { classNames } from "../lib/utils";

const links = [
  { to: "/", icon: LayoutDashboard, label: "داشبورد" },
  { to: "/servers", icon: Server, label: "سرورها" },
  { to: "/plans", icon: CreditCard, label: "پلن‌ها" },
  { to: "/accounts", icon: Users, label: "اکانت‌ها" },
  { to: "/sessions", icon: Activity, label: "سشن‌ها" },
  { to: "/logs", icon: ScrollText, label: "لاگ‌ها" },
];

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({ collapsed, onToggle }: Props) {
  const { logout } = useAuth();

  return (
    <aside
      className={classNames(
        "fixed top-0 right-0 h-screen bg-gray-900 border-l border-gray-800 flex flex-col transition-all duration-300 z-40",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex items-center gap-3 px-4 h-16 border-b border-gray-800">
        <Shield className="w-8 h-8 text-indigo-400 shrink-0" />
        {!collapsed && (
          <span className="text-lg font-bold text-white whitespace-nowrap">VPN Panel</span>
        )}
        <button
          onClick={onToggle}
          className={classNames(
            "mr-auto text-gray-400 hover:text-white transition-transform",
            collapsed && "rotate-180",
          )}
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === "/"}
            className={({ isActive }) =>
              classNames(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-600/20 text-indigo-400"
                  : "text-gray-400 hover:text-white hover:bg-gray-800",
              )
            }
          >
            <link.icon className="w-5 h-5 shrink-0" />
            {!collapsed && <span>{link.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-gray-800 p-2">
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-gray-800 w-full transition-colors"
        >
          <LogOut className="w-5 h-5 shrink-0" />
          {!collapsed && <span>خروج</span>}
        </button>
      </div>
    </aside>
  );
}
