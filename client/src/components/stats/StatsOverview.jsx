import { useTranslation } from "react-i18next";
import { FileText, HardDrive, Database, BookOpen } from "lucide-react";

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export default function StatsOverview({ summary }) {
  const { t } = useTranslation();

  const CARDS = [
    {
      key: "totalFiles",
      label: t("stats.totalFiles"),
      icon: FileText,
      color: "bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400",
      fmt: (v) => v?.toLocaleString() ?? "0",
    },
    {
      key: "totalSize",
      label: t("stats.totalSize"),
      icon: HardDrive,
      color: "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400",
      fmt: formatSize,
    },
    {
      key: "activeSources",
      label: t("stats.activeSources"),
      icon: Database,
      color: "bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400",
      fmt: (v) => v ?? "0",
    },
    {
      key: "byCategory",
      label: t("stats.documents"),
      icon: BookOpen,
      color: "bg-purple-50 dark:bg-purple-950 text-purple-600 dark:text-purple-400",
      fmt: (cats) => {
        if (!Array.isArray(cats)) return "0";
        return cats
          .filter((c) => c._id === "text" || c._id === "document")
          .reduce((acc, c) => acc + (c.count || 0), 0)
          .toLocaleString();
      },
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map(({ key, label, icon: Icon, color, fmt }) => (
        <div key={key} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-5 shadow-sm flex items-center gap-4">
          <div className={`flex-shrink-0 inline-flex p-3 rounded-xl ${color}`}>
            <Icon size={22} />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-800 dark:text-slate-100 leading-none">
              {summary ? fmt(summary[key]) : "—"}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
