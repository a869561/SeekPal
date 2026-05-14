import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Folder, BarChart2, Settings, LogOut, ChevronLeft, ChevronRight } from "lucide-react";

const NAV = [
  { to: "/stats",    icon: BarChart2, label: "Estadísticas" },
  { to: "/sources",  icon: Folder,    label: "Fuentes" },
  { to: "/settings", icon: Settings,  label: "Ajustes" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("seekpal_sidebar") === "collapsed"
  );

  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("seekpal_sidebar", next ? "collapsed" : "expanded");
  }

  function logout() {
    localStorage.removeItem("seekpal_token");
    navigate("/login");
  }

  return (
    <aside
      className={`flex-shrink-0 bg-slate-900 dark:bg-slate-950 flex flex-col h-full transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Logo */}
      <div className="flex justify-center items-center px-4 py-5 border-b border-slate-700/50">
        <img
          src="/logo-icon.png"
          alt="SeekPal"
          className={`transition-all duration-200 ${collapsed ? "h-8" : "h-12"}`}
        />
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                collapsed ? "justify-center" : ""
              } ${
                isActive
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`
            }
          >
            <Icon size={18} className="flex-shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer: toggle + logout */}
      <div className="px-2 py-3 border-t border-slate-700/50 space-y-1">
        <button
          onClick={toggle}
          title={collapsed ? "Expandir menú" : "Colapsar menú"}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-all ${
            collapsed ? "justify-center" : ""
          }`}
        >
          {collapsed ? <ChevronRight size={18} className="flex-shrink-0" /> : <ChevronLeft size={18} className="flex-shrink-0" />}
          {!collapsed && <span>Contraer menú</span>}
        </button>
        <button
          onClick={logout}
          title={collapsed ? "Cerrar sesión" : undefined}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-all ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <LogOut size={18} className="flex-shrink-0" />
          {!collapsed && <span>Cerrar sesión</span>}
        </button>
      </div>
    </aside>
  );
}
