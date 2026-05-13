import { useState, useEffect } from "react";
import { getFiles } from "../../api/stats.js";
import { getSources } from "../../api/sources.js";
import { ChevronLeft, ChevronRight } from "lucide-react";

const CATEGORIES = ["", "text", "document", "image", "audio", "video", "other"];
const CAT_LABELS = { "": "Todas", text: "Texto", document: "Documento", image: "Imagen", audio: "Audio", video: "Vídeo", other: "Otro" };

function formatSize(b) {
  if (!b) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

function MetaCell({ file }) {
  const m = file.metadata || {};
  if (file.category === "text" || file.category === "document") {
    return <span>{m.wordCount != null ? `${m.wordCount.toLocaleString()} palabras` : "—"}</span>;
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

const CAT_COLORS = { text: "bg-indigo-50 text-indigo-600", document: "bg-amber-50 text-amber-600", image: "bg-emerald-50 text-emerald-600", audio: "bg-pink-50 text-pink-600", video: "bg-blue-50 text-blue-600", other: "bg-slate-100 text-slate-500" };

export default function FilesTable() {
  const [files, setFiles] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [category, setCategory] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSources().then((r) => setSources(r.data.data || []));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = { page, limit: 20 };
    if (category) params.category = category;
    if (sourceId) params.sourceId = sourceId;

    getFiles(params)
      .then((r) => {
        setFiles(r.data.data.files);
        setTotal(r.data.data.total);
        setPages(r.data.data.pages);
      })
      .finally(() => setLoading(false));
  }, [page, category, sourceId]);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Filters */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-100">
        <h3 className="font-semibold text-slate-700 text-sm mr-auto">Ficheros indexados ({total.toLocaleString()})</h3>
        <select
          value={sourceId}
          onChange={(e) => { setSourceId(e.target.value); setPage(1); }}
          className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          <option value="">Todas las fuentes</option>
          {sources.map((s) => <option key={s._id} value={s._id}>{s.name}</option>)}
        </select>
        <select
          value={category}
          onChange={(e) => { setCategory(e.target.value); setPage(1); }}
          className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          {CATEGORIES.map((c) => <option key={c} value={c}>{CAT_LABELS[c]}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left">
              <th className="px-6 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Nombre</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Categoría</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Tamaño</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Metadatos</th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Modificado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {loading ? (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-sm">Cargando…</td></tr>
            ) : files.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-sm">Sin ficheros</td></tr>
            ) : files.map((f) => (
              <tr key={f._id} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-3">
                  <div className="font-medium text-slate-700 truncate max-w-xs">{f.name}</div>
                  <div className="text-xs text-slate-400 truncate max-w-xs font-mono">{f.path}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${CAT_COLORS[f.category] || "bg-slate-100 text-slate-500"}`}>
                    {CAT_LABELS[f.category] || f.category}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{formatSize(f.size)}</td>
                <td className="px-4 py-3 text-slate-500"><MetaCell file={f} /></td>
                <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                  {f.modifiedAt ? new Date(f.modifiedAt).toLocaleDateString("es-ES") : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between px-6 py-3 border-t border-slate-100">
          <span className="text-xs text-slate-400">Página {page} de {pages}</span>
          <div className="flex gap-1">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition">
              <ChevronLeft size={16} className="text-slate-600" />
            </button>
            <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page === pages} className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition">
              <ChevronRight size={16} className="text-slate-600" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
