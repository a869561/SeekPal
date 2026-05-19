import { useTranslation } from "react-i18next";
import { FileText, Image, Music, Film, File, ChevronLeft, ChevronRight } from "lucide-react";

function formatSize(b) {
  if (b == null) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

const CAT_STYLE = {
  text:     { icon: FileText, iconCls: "text-indigo-500",  bg: "bg-indigo-50 dark:bg-indigo-950",   badge: "bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400"    },
  document: { icon: FileText, iconCls: "text-amber-500",   bg: "bg-amber-50 dark:bg-amber-950",    badge: "bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400"        },
  image:    { icon: Image,    iconCls: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950", badge: "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400" },
  audio:    { icon: Music,    iconCls: "text-pink-500",    bg: "bg-pink-50 dark:bg-pink-950",       badge: "bg-pink-50 dark:bg-pink-950 text-pink-600 dark:text-pink-400"             },
  video:    { icon: Film,     iconCls: "text-blue-500",    bg: "bg-blue-50 dark:bg-blue-950",       badge: "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"             },
  other:    { icon: File,     iconCls: "text-slate-400",   bg: "bg-slate-100 dark:bg-slate-800",    badge: "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"        },
};

function MetaSnippet({ file }) {
  const m = file.metadata || {};
  const parts = [];
  if (file.category === "text" || file.category === "document") {
    if (m.wordCount != null) parts.push(`${m.wordCount.toLocaleString()} palabras`);
  } else if (file.category === "image") {
    if (m.width && m.height) parts.push(`${m.width}×${m.height}${m.ppi ? ` · ${m.ppi} ppi` : ""}`);
  } else if (file.category === "audio") {
    if (m.duration != null) {
      const min = Math.floor(m.duration / 60);
      const sec = m.duration % 60;
      parts.push(`${min}:${String(sec).padStart(2, "0")}${m.bitrate ? ` · ${m.bitrate} kbps` : ""}`);
    }
  } else if (file.category === "video") {
    if (m.duration != null) {
      const min = Math.floor(m.duration / 60);
      const sec = m.duration % 60;
      parts.push(`${min}:${String(sec).padStart(2, "0")}${m.width ? ` · ${m.width}×${m.height}` : ""}`);
    }
  }
  if (!parts.length) return null;
  return <span>{parts.join(" · ")}</span>;
}

function FileResultCard({ file }) {
  const { t } = useTranslation();
  const s = CAT_STYLE[file.category] || CAT_STYLE.other;
  const Icon = s.icon;

  return (
    <div className="flex items-start gap-4 p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:border-indigo-300 dark:hover:border-indigo-600 transition-colors">
      <div className={`flex-shrink-0 p-2.5 rounded-lg ${s.bg}`}>
        <Icon size={20} className={s.iconCls} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-slate-800 dark:text-slate-100 truncate">{file.name}</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${s.badge}`}>
            {t(`files.categories.${file.category}`, { defaultValue: file.category })}
          </span>
        </div>
        <div className="text-xs text-slate-400 dark:text-slate-500 font-mono truncate mt-0.5">{file.path}</div>
        <div className="flex items-center gap-2 mt-1 text-xs text-slate-500 dark:text-slate-400">
          {formatSize(file.size) && <span>{formatSize(file.size)}</span>}
          <MetaSnippet file={file} />
        </div>
      </div>
    </div>
  );
}

export default function ClassicResults({ results, loading, submitted, page, setPage }) {
  const { t } = useTranslation();
  return (
    <div className={`space-y-2 transition-opacity duration-150 ${loading ? "opacity-50" : "opacity-100"}`}>
      {results?.files?.length === 0 ? (
        <div className="text-center py-12 text-slate-400 dark:text-slate-500 text-sm">
          {t("search.empty", { query: submitted })}
        </div>
      ) : (
        results?.files?.map((f) => <FileResultCard key={f._id} file={f} />)
      )}

      {results && results.pages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button onClick={() => setPage((p) => p - 1)} disabled={page === 1}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition">
            <ChevronLeft size={16} className="text-slate-600 dark:text-slate-300" />
          </button>
          <span className="text-sm text-slate-500 dark:text-slate-400">
            {t("files.page", { page, pages: results.pages })}
          </span>
          <button onClick={() => setPage((p) => p + 1)} disabled={page === results.pages}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition">
            <ChevronRight size={16} className="text-slate-600 dark:text-slate-300" />
          </button>
        </div>
      )}
    </div>
  );
}
