import { useTranslation } from "react-i18next";
import { FileText, HardDrive, Database, Clock } from "lucide-react";
import StatCard from "../ui/StatCard.jsx";
import { relativeTime, absoluteDateTime } from "../../utils/relativeTime.js";

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export default function StatsOverview({ summary }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "es";

  const CARDS = [
    {
      key: "totalFiles",
      label: t("stats.totalFiles"),
      icon: FileText,
      fmt: (v) => v?.toLocaleString() ?? "0",
    },
    {
      key: "totalSize",
      label: t("stats.totalSize"),
      icon: HardDrive,
      fmt: formatSize,
    },
    {
      key: "activeSources",
      label: t("stats.activeSources"),
      icon: Database,
      fmt: (v) => v ?? "0",
    },
    {
      key: "lastIndexed",
      label: t("stats.lastIndexed"),
      icon: Clock,
      fmt: (v) => (v ? relativeTime(v, locale) : t("stats.never")),
      titleFmt: (v) => (v ? absoluteDateTime(v, locale) : t("stats.never")),
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map(({ key, label, icon, fmt, titleFmt }, i) => (
        <StatCard
          key={key}
          index={i}
          icon={icon}
          label={label}
          value={summary ? fmt(summary[key]) : "—"}
          title={summary && titleFmt ? titleFmt(summary[key]) : undefined}
        />
      ))}
    </div>
  );
}
