import { useState, useEffect } from "react";
import { getSummary } from "../api/stats.js";
import StatsOverview from "../components/stats/StatsOverview.jsx";
import FileTypeChart from "../components/stats/FileTypeChart.jsx";
import FilesTable from "../components/stats/FilesTable.jsx";
import toast from "react-hot-toast";

export default function StatsPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSummary()
      .then((r) => setSummary(r.data.data))
      .catch(() => toast.error("Error cargando estadísticas"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Estadísticas</h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">Resumen de ficheros indexados</p>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-40">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="space-y-8">
          <StatsOverview summary={summary} />
          <FileTypeChart data={summary?.byCategory || []} />
          <FilesTable />
        </div>
      )}
    </div>
  );
}
