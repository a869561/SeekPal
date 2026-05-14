import ThemeSelector from "../components/settings/ThemeSelector.jsx";
import FontSizeSelector from "../components/settings/FontSizeSelector.jsx";
import ChangePassword from "../components/settings/ChangePassword.jsx";

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Ajustes</h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">Configuración de la aplicación</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Appearance column */}
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1">Apariencia</h2>
          <ThemeSelector />
          <FontSizeSelector />
        </div>

        {/* Security column */}
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1">Seguridad</h2>
          <ChangePassword />
        </div>
      </div>
    </div>
  );
}
