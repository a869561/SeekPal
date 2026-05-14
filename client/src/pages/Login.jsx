import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth.js";
import { Eye, EyeOff } from "lucide-react";

export default function Login() {
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await login(password);
      localStorage.setItem("seekpal_token", res.data.data.accessToken);
      navigate("/stats");
    } catch {
      setError("Contraseña incorrecta");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="bg-slate-800/60 backdrop-blur-md border border-slate-700/50 rounded-3xl shadow-2xl overflow-hidden">
          {/* Logo */}
          <div className="px-8 pt-8 pb-4 text-center">
            <img src="/logo-icon.png" alt="SeekPal" className="h-28 mx-auto mb-3" />
            <h1 className="text-2xl font-bold text-white tracking-tight">SeekPal</h1>
            <p className="text-slate-400 text-sm mt-1">Buscador Inteligente de Repositorios</p>
          </div>

          {/* Divider */}
          <div className="mx-8 border-t border-slate-700/50 mb-6" />

          {/* Form */}
          <div className="px-8 pb-8">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Contraseña de acceso
                </label>
                <div className="relative">
                  <input
                    type={visible ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    autoFocus
                    className={`w-full px-4 py-3 pr-11 rounded-xl bg-slate-900/70 border text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:border-transparent transition
                      ${error ? "border-red-500 focus:ring-red-500" : "border-slate-600/50 focus:ring-indigo-500"}`}
                  />
                  <button
                    type="button"
                    onClick={() => setVisible((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition"
                  >
                    {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold transition shadow-lg shadow-indigo-500/20"
              >
                {loading ? "Accediendo..." : "Acceder"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
