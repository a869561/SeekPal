import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const COLORS = {
  text:     "#6366f1",
  document: "#f59e0b",
  image:    "#10b981",
  audio:    "#ec4899",
  video:    "#3b82f6",
  other:    "#94a3b8",
};

const LABELS = {
  text: "Texto", document: "Documento", image: "Imagen",
  audio: "Audio", video: "Vídeo", other: "Otro",
};

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export default function FileTypeChart({ data }) {
  if (!data?.length) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center shadow-sm">
        <p className="text-slate-400 text-sm">Sin datos. Ingesta algún directorio primero.</p>
      </div>
    );
  }

  const pieData = data.map((d) => ({
    name: LABELS[d._id] || d._id,
    value: d.count,
    color: COLORS[d._id] || "#94a3b8",
  }));

  const barData = data.map((d) => ({
    name: LABELS[d._id] || d._id,
    size: d.size,
    color: COLORS[d._id] || "#94a3b8",
  }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Pie — distribución por cantidad */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <h3 className="font-semibold text-slate-700 mb-4 text-sm">Ficheros por categoría</h3>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3} dataKey="value">
              {pieData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip formatter={(v) => [`${v} ficheros`, ""]} />
            <Legend iconType="circle" iconSize={8} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Bar — distribución por tamaño */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
        <h3 className="font-semibold text-slate-700 mb-4 text-sm">Tamaño por categoría</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={barData} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={formatSize} tick={{ fontSize: 10 }} width={60} />
            <Tooltip formatter={(v) => [formatSize(v), "Tamaño"]} />
            <Bar dataKey="size" radius={[4, 4, 0, 0]}>
              {barData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
