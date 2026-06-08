import Card from "./Card.jsx";

/**
 * Tarjeta de métrica. Icono en morado de marca (identidad, no semántico),
 * valor en tabular-nums, label debajo. Acepta `index` para entrada escalonada.
 */
export default function StatCard({ icon: Icon, value, label, title, index = 0 }) {
  return (
    <Card
      className="p-5 flex items-center gap-4 reveal-up"
      style={{ "--stagger": index }}
      title={title}
    >
      <div className="flex-shrink-0 inline-flex p-3 rounded-xl bg-brand-soft text-brand">
        <Icon size={22} />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold text-slate-800 dark:text-slate-100 leading-none tabular-nums truncate">
          {value}
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">{label}</div>
      </div>
    </Card>
  );
}
