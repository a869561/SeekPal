import { useTranslation } from "react-i18next";
import ThemeSelector from "../components/settings/ThemeSelector.jsx";
import FontSizeSelector from "../components/settings/FontSizeSelector.jsx";
import LanguageSelector from "../components/settings/LanguageSelector.jsx";
import ChangePassword from "../components/settings/ChangePassword.jsx";
import HardwareCard from "../components/settings/HardwareCard.jsx";
import RagSettingsCard from "../components/settings/RagSettingsCard.jsx";

export default function SettingsPage() {
  const { t } = useTranslation();

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{t("settings.title")}</h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">{t("settings.subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1">
            {t("settings.appearance")}
          </h2>
          <ThemeSelector />
          <FontSizeSelector />
          <LanguageSelector />

          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1 pt-2">
            {t("settings.rag")}
          </h2>
          <RagSettingsCard />
        </div>

        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1">
            {t("settings.security")}
          </h2>
          <ChangePassword />

          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1 pt-2">
            {t("settings.hardware")}
          </h2>
          <HardwareCard />
        </div>
      </div>
    </div>
  );
}
