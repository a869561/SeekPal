import { useTranslation } from "react-i18next";
import { FileText, Image, Music, Film, File, ChevronLeft, ChevronRight } from "lucide-react";
import CategoryBadge from "../ui/CategoryBadge.jsx";
import LoadingSpinner from "../ui/LoadingSpinner.jsx";
import { relevancePct } from "../../utils/relevance.js";

function formatSize(b) {
  if (b == null) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

const CAT_STYLE = {
  text:     { icon: FileText, iconCls: "text-cat-text",     bg: "bg-cat-text-soft"     },
  document: { icon: FileText, iconCls: "text-cat-document", bg: "bg-cat-document-soft" },
  image:    { icon: Image,    iconCls: "text-cat-image",    bg: "bg-cat-image-soft"    },
  audio:    { icon: Music,    iconCls: "text-cat-audio",    bg: "bg-cat-audio-soft"    },
  video:    { icon: Film,     iconCls: "text-cat-video",    bg: "bg-cat-video-soft"    },
  other:    { icon: File,     iconCls: "text-cat-other",    bg: "bg-cat-other-soft"    },
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
  const hasRelevance = file._relevanceScore != null;

  return (
    <div className="flex items-start gap-4 p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:border-brand/40 transition-colors">
      <div className={`flex-shrink-0 p-2.5 rounded-lg ${s.bg}`}>
        <Icon size={20} className={s.iconCls} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-slate-800 dark:text-slate-100 truncate">{file.name}</span>
          <CategoryBadge category={file.category} className="flex-shrink-0">
            {t(`files.categories.${file.category}`, { defaultValue: file.category })}
          </CategoryBadge>
          {hasRelevance && (
            <span
              className="text-xs text-slate-400 dark:text-slate-500 ml-auto flex-shrink-0 tabular-nums"
              title={t("search.relevance")}
            >
              {relevancePct(file._relevanceScore)}%
            </span>
          )}
        </div>
        <div className="text-xs text-slate-400 dark:text-slate-500 font-mono truncate mt-0.5">{file.path}</div>
        <div className="flex items-center gap-2 mt-1 text-xs text-slate-500 dark:text-slate-400">
          {formatSize(file.size) && <span>{formatSize(file.size)}</span>}
          <MetaSnippet file={file} />
        </div>
        {/* Fragmento del contenido relevante (solo en búsqueda semántica) */}
        {hasRelevance && file._snippet && (
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed bg-slate-50 dark:bg-slate-700/40 rounded-md px-2.5 py-1.5">
            {file._snippet}
          </p>
        )}
      </div>
    </div>
  );
}

export default function ClassicResults({ results, loading, submitted, page, setPage }) {
  const { t } = useTranslation();

  // Carga inicial (aún no hay resultados): círculo de carga centrado,
  // el mismo componente que usa el modo pregunta.
  if (loading && !results) {
    return <LoadingSpinner label={t("search.searching")} />;
  }

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
