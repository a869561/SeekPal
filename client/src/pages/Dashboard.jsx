import { Outlet } from "react-router-dom";
import Sidebar from "../components/layout/Sidebar.jsx";

export default function Dashboard() {
  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
