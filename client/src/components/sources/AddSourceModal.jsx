import { useState } from "react";
import { X, FolderOpen } from "lucide-react";

export default function AddSourceModal({ onClose, onAdd }) {
  const [name, setName] = useState("");
  const [dirPath, setDirPath] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await onAdd({ name: name.trim(), path: dirPath.trim() });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <FolderOpen size={20} className="text-indigo-500" />
            <h2 className="font-semibold text-slate-800">Añadir directorio</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Nombre</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mis documentos"
              required
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm transition"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Ruta del directorio</label>
            <input
              type="text"
              value={dirPath}
              onChange={(e) => setDirPath(e.target.value)}
              placeholder="C:\Users\usuario\Documentos"
              required
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
            />
            <p className="text-xs text-slate-400 mt-1.5">Ruta absoluta al directorio local</p>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 px-4 rounded-xl border border-slate-200 text-slate-600 font-medium text-sm hover:bg-slate-50 transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm disabled:opacity-50 transition"
            >
              {loading ? "Añadiendo…" : "Añadir fuente"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
