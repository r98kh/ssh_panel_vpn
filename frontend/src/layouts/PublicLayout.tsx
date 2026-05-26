import { Outlet } from "react-router-dom";
import { Shield } from "lucide-react";

export default function PublicLayout() {
  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center gap-3">
          <Shield className="w-6 h-6 text-indigo-400" />
          <span className="font-bold text-white">SSH VPN Panel</span>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-gray-800 py-4 text-center text-xs text-gray-600">
        SSH VPN Management Panel
      </footer>
    </div>
  );
}
