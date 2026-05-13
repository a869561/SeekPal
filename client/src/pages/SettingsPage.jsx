import ChangePassword from "../components/settings/ChangePassword.jsx";

export default function SettingsPage() {
  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Ajustes</h1>
        <p className="text-slate-500 text-sm mt-1">Configuración de la aplicación</p>
      </div>
      <div className="max-w-md">
        <ChangePassword />
      </div>
    </div>
  );
}
