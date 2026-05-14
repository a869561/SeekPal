import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { getFiles } from "../../api/stats.js";
import { getSources } from "../../api/sources.js";
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

function formatSize(b) {
  if (b == null) return "—";
  if (b < 1024) return `${b} Bytes`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

function MetaCell({ file, t }) {
  const m = file.metadata || {};
  if (file.category === "text" || file.category === "document") {
    return <span>{m.wordCount != null ? t("files.words", { count: m.wordCount.toLocaleString() }) : "—"}</span>;
  }
  if (file.category === "image") {
    return <span>{m.width && m.height ? `${m.width}×${m.height}${m.ppi ? ` · ${m.ppi} ppi` : ""}` : "—"}</span>;
  }
  if (file.category === "audio") {
    const min = Math.floor((m.duration || 0) / 60);
    const sec = (m.duration || 0) % 60;
    return <span>{m.duration != null ? `${min}:${String(sec).padStart(2, "0")}${m.bitrate ? ` · ${m.bitrate} kbps` : ""}` : "—"}</span>;
  }
  if (file.category === "video") {
    const min = Math.floor((m.duration || 0) / 60);
    const sec = (m.duration || 0) % 60;
    return <span>{m.duration != null ? `${min}:${String(sec).padStart(2, "0")}${m.width ? ` · ${m.width}×${m.height}` : ""}${m.fps ? ` · ${m.fps} fps` : ""}` : "—"}</span>;
  }
  return <span>—</span>;
}

const CAT_COLORS = {
  text:     "bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400",
  document: "bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400",
  image:    "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400",
  audio:    "bg-pink-50 dark:bg-pink-950 text-pink-600 dark:text-pink-400",
  video:    "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400",
  other:    "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400",
};

const CAT_KEYS = ["", "text", "document", "image", "audio", "video", "other"];

function SortIcon({ col, sortBy, sortDir }) {
  if (!col.sortable) return null;
  if (sortBy !== col.key) return <ChevronsUpDown size={13} className="opacity-30" />;
  return sortDir === "asc" ? <ChevronUp size={13} /> : <ChevronDown size={13} />;
}

function Pagination({ page, pages, onChange, t }) {
  if (pages <= 1) return null;
  const range = new Set([1, pages, page, page - 1, page - 2, page + 1, page + 2].filter((n) => n >= 1 && n <= pages));
  const nums = [...range].sort((a, b) => a - b);

  return (
    <div className="flex items-center justify-between px-6 py-3 border-t border-slate-100 dark:border-slate-700">
      <span className="text-xs text-slate-400 dark:text-slate-500">
        {t("files.page", { page, pages })}
      </span>
      <div className="flex items-center gap-1">
        <button onClick={() => onChange(page - 1)} disabled={page === 1}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition">
          <ChevronLeft size={16} className="text-slate-600 dark:text-slate-300" />
        </button>
        {nums.map((n, i) => {
          const gap = i > 0 && n - nums[i - 1] > 1;
          return (
            <span key={n} className="flex items-center gap-1">
              {gap && <span className="text-slate-300 dark:text-slate-600 text-xs px-0.5">…</span>}
              <button onClick={() => onChange(n)}
                className={`min-w-[28px] h-7 rounded-lg text-xs font-medium transition ${
                  n === page ? "bg-indigo-600 text-white" : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
                }`}>
                {n}
              </button>
            </span>
          );
        })}
        <button onClick={() => onChange(page + 1)} disabled={page === pages}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition">
          <ChevronRight size={16} className="text-slate-600 dark:text-slate-300" />
        </button>
      </div>
    </div>
  );
}

export default function FilesTable() {
  const { t } = useTranslation();
  const [files, setFiles]     = useState([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [pages, setPages]     = useState(1);
  const [category, setCategory] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy]   = useState("size");
  const [sortDir, setSortDir] = useState("desc");
  const tableRef = useRef(null);

  const COLUMNS = [
    { key: "name",       label: t("files.columns.name"),     sortable: true  },
    { key: "category",   label: t("files.columns.category"), sortable: false },
    { key: "size",       label: t("files.columns.size"),     sortable: true  },
    { key: "metadata",   label: t("files.columns.metadata"), sortable: false },
    { key: "modifiedAt", label: t("files.columns.modified"), sortable: true  },
  ];

  useEffect(() => {
    getSources().then((r) => setSources(r.data.data || []));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = { page, limit: 20, sortBy, sortDir };
    if (category) params.category = category;
    if (sourceId) params.sourceId = sourceId;
    getFiles(params)
      .then((r) => {
        setFiles(r.data.data.files);
        setTotal(r.data.data.total);
        setPages(r.data.data.pages);
      })
      .finally(() => setLoading(false));
  }, [page, category, sourceId, sortBy, sortDir]);

  function handleSort(col) {
    if (!col.sortable) return;
    if (sortBy === col.key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortBy(col.key); setSortDir("desc"); }
    setPage(1);
  }

  function handlePageChange(n) {
    setPage(n);
    tableRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const selectCls = "text-sm border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400";

  return (
    <div ref={tableRef} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-sm overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-100 dark:border-slate-700">
        <h3 className="font-semibold text-slate-700 dark:text-slate-200 text-sm mr-auto">
          {t("files.title")}
          {total > 0 && <span className="ml-1.5 text-slate-400 dark:text-slate-500 font-normal">({total.toLocaleString()})</span>}
          {loading && <span className="ml-2 inline-block w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin align-middle" />}
        </h3>
        <select value={sourceId} onChange={(e) => { setSourceId(e.target.value); setPage(1); }} className={selectCls}>
          <option value="">{t("files.allSources")}</option>
          {sources.map((s) => <option key={s._id} value={s._id}>{s.name}</option>)}
        </select>
        <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className={selectCls}>
          {CAT_KEYS.map((c) => (
            <option key={c} value={c}>{t(`files.categories.${c || "all"}`)}</option>
          ))}
        </select>
      </div>

      <div className={`overflow-x-auto transition-opacity duration-150 ${loading ? "opacity-50" : "opacity-100"}`}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              {COLUMNS.map((col) => (
                <th key={col.key} onClick={() => handleSort(col)}
                  className={`${col.key === "name" ? "px-6" : "px-4"} py-3 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider select-none ${
                    col.sortable ? "cursor-pointer hover:text-slate-600 dark:hover:text-slate-300 transition-colors" : ""
                  }`}>
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    <SortIcon col={col} sortBy={sortBy} sortDir={sortDir} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
            {files.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-slate-400 dark:text-slate-500 text-sm">{t("files.empty")}</td></tr>
            ) : files.map((f) => (
              <tr key={f._id} className="hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-[background-color]">
                <td className="px-6 py-3">
                  <div className="font-medium text-slate-700 dark:text-slate-200 truncate max-w-xs">{f.name}</div>
                  <div className="text-xs text-slate-400 dark:text-slate-500 truncate max-w-xs font-mono">{f.path}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${CAT_COLORS[f.category] || CAT_COLORS.other}`}>
                    {t(`files.categories.${f.category}`, { defaultValue: f.category })}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">{formatSize(f.size)}</td>
                <td className="px-4 py-3 text-slate-500 dark:text-slate-400"><MetaCell file={f} t={t} /></td>
                <td className="px-4 py-3 text-slate-400 dark:text-slate-500 text-xs whitespace-nowrap">
                  {f.modifiedAt ? new Date(f.modifiedAt).toLocaleDateString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pagination page={page} pages={pages} onChange={handlePageChange} t={t} />
    </div>
  );
}
