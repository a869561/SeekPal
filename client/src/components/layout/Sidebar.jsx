import { NavLink, useNavigate } from "react-router-dom";
import { Folder, BarChart2, Settings, Search, LogOut } from "lucide-react";

const NAV = [
  { to: "/sources", icon: Folder, label: "Fuentes" },
  { to: "/stats", icon: BarChart2, label: "Estadísticas" },
  { to: "/settings", icon: Settings, label: "Ajustes" },
];

export default function Sidebar() {
  const navigate = useNavigate();

  function logout() {
    localStorage.removeItem("seekpal_token");
    navigate("/login");
  }

  return (
    <aside className="w-60 flex-shrink-0 bg-slate-900 flex flex-col h-full">
      {/* Logo */}
      <div className="px-6 py-6 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center shadow-sm">
            <Search size={16} className="text-white" />
          </div>
          <span className="text-white font-semibold text-lg tracking-tight">SeekPal</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Logout */}
      <div className="px-3 py-4 border-t border-slate-700/50">
        <button
          onClick={logout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
        >
          <LogOut size={18} />
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
