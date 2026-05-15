import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Search, Folder, BarChart2, Settings, LogOut, ChevronLeft, ChevronRight } from "lucide-react";

export default function Sidebar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("seekpal_sidebar") === "collapsed"
  );

  const NAV = [
    { to: "/search",   icon: Search,    label: t("nav.search") },
    { to: "/stats",    icon: BarChart2, label: t("nav.stats") },
    { to: "/sources",  icon: Folder,    label: t("nav.sources") },
    { to: "/settings", icon: Settings,  label: t("nav.settings") },
  ];

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
      className={`flex-shrink-0 bg-gradient-to-b from-slate-900 via-indigo-950 to-slate-900 flex flex-col h-full transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Logo */}
      <div className="flex justify-center items-center px-4 py-5 border-b border-slate-700/50">
        <img
          src="/logo-icon.png"
          alt="SeekPal"
          className={`transition-all duration-200 object-contain ${collapsed ? "h-12 w-12" : "h-24"}`}
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
                  : "text-slate-400 hover:text-white hover:bg-white/10"
              }`
            }
          >
            <Icon size={18} className="flex-shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Toggle — above the divider */}
      <div className="px-2 py-2">
        <button
          onClick={toggle}
          title={collapsed ? t("nav.expand") : t("nav.collapse")}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-white/10 transition-all ${
            collapsed ? "justify-center" : ""
          }`}
        >
          {collapsed
            ? <ChevronRight size={18} className="flex-shrink-0" />
            : <ChevronLeft  size={18} className="flex-shrink-0" />}
          {!collapsed && <span>{t("nav.collapse")}</span>}
        </button>
      </div>

      {/* Logout — below the divider */}
      <div className="px-2 py-3 border-t border-slate-700/50">
        <button
          onClick={logout}
          title={collapsed ? t("nav.logout") : undefined}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-white/10 transition-all ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <LogOut size={18} className="flex-shrink-0" />
          {!collapsed && <span>{t("nav.logout")}</span>}
        </button>
      </div>
    </aside>
  );
}
