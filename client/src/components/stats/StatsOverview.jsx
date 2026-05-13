import { FileText, HardDrive, Database, Cpu } from "lucide-react";

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

const CARDS = [
  {
    key: "totalFiles",
    label: "Total ficheros",
    icon: FileText,
    color: "bg-indigo-50 text-indigo-600",
    fmt: (v) => v?.toLocaleString("es-ES") ?? "0",
  },
  {
    key: "totalSize",
    label: "Tamaño total",
    icon: HardDrive,
    color: "bg-emerald-50 text-emerald-600",
    fmt: formatSize,
  },
  {
    key: "activeSources",
    label: "Fuentes activas",
    icon: Database,
    color: "bg-amber-50 text-amber-600",
    fmt: (v) => v ?? "0",
  },
  {
    key: "byCategory",
    label: "Ingestibles por IA",
    icon: Cpu,
    color: "bg-purple-50 text-purple-600",
    fmt: (cats) => {
      if (!Array.isArray(cats)) return "0";
      const total = cats.reduce((acc, c) => acc + (c.ingestible || 0), 0);
      return total.toLocaleString("es-ES");
    },
  },
];

export default function StatsOverview({ summary }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map(({ key, label, icon: Icon, color, fmt }) => (
        <div key={key} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <div className={`inline-flex p-2.5 rounded-xl ${color} mb-3`}>
            <Icon size={20} />
          </div>
          <div className="text-2xl font-bold text-slate-800">
            {summary ? fmt(summary[key]) : "—"}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">{label}</div>
        </div>
      ))}
    </div>
  );
}
