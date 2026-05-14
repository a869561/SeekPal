import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useTheme } from "../context/ThemeContext.jsx";
import { applyFontSize } from "../components/settings/FontSizeSelector.jsx";
import { getSettings } from "../api/settings.js";

export function useSettingsSync() {
  const { setTheme } = useTheme();
  const { i18n } = useTranslation();

  useEffect(() => {
    getSettings().then((res) => {
      const s = res.data.data;
      if (s.theme) {
        localStorage.setItem("seekpal_theme", s.theme);
        setTheme(s.theme);
      }
      if (s.fontSize) {
        localStorage.setItem("seekpal_fontsize", s.fontSize);
        applyFontSize(s.fontSize);
      }
      if (s.language) {
        localStorage.setItem("seekpal_lang", s.language);
        i18n.changeLanguage(s.language);
      }
    }).catch(() => {});
  }, []);
}
