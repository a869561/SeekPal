import { useTranslation } from "react-i18next";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { useTheme } from "../../context/ThemeContext.jsx";

const COLORS = {
  text:     "#6366f1",
  document: "#f59e0b",
  image:    "#10b981",
  audio:    "#ec4899",
  video:    "#3b82f6",
  other:    "#94a3b8",
};

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export default function FileTypeChart({ data }) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const tickColor    = isDark ? "#94a3b8" : "#64748b";
  const tooltipStyle = isDark
    ? { backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }
    : { backgroundColor: "#fff",    border: "1px solid #e2e8f0", borderRadius: 8 };
  const tooltipTextStyle = { color: isDark ? "#f1f5f9" : "#475569" };
  const cursorStyle      = { fill: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)" };

  const catLabel = (id) => t(`files.categories.${id}`, { defaultValue: id });

  if (!data?.length) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-8 text-center shadow-sm">
        <p className="text-slate-400 dark:text-slate-500 text-sm">{t("stats.noData")}</p>
      </div>
    );
  }

  const pieData = data.map((d) => ({ name: catLabel(d._id), value: d.count, color: COLORS[d._id] || "#94a3b8" }));
  const barData = data.map((d) => ({ name: catLabel(d._id), size: d.size, color: COLORS[d._id] || "#94a3b8" }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
        <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-4 text-sm">{t("stats.byCategory")}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3} dataKey="value" animationBegin={0} animationDuration={800} stroke="none">
              {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Pie>
            <Tooltip formatter={(v) => `${v} ${t("stats.filesUnit")}`} contentStyle={tooltipStyle} itemStyle={tooltipTextStyle} separator=": " />
            <Legend iconType="circle" iconSize={8} formatter={(v) => <span style={{ color: tickColor }}>{v}</span>} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
        <h3 className="font-semibold text-slate-700 dark:text-slate-200 mb-4 text-sm">{t("stats.bySize")}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={barData} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: tickColor }} />
            <YAxis tickFormatter={formatSize} tick={{ fontSize: 10, fill: tickColor }} width={60} />
            <Tooltip formatter={(v) => [formatSize(v), t("stats.sizeLabel")]} contentStyle={tooltipStyle} itemStyle={tooltipTextStyle} cursor={cursorStyle} separator=": " />
            <Bar dataKey="size" radius={[4, 4, 0, 0]} animationBegin={0} animationDuration={800}>
              {barData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
