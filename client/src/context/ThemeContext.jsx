import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext(null);

function getResolved(theme) {
  if (theme === "auto") return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  return theme;
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => localStorage.getItem("seekpal_theme") || "auto");
  const [resolvedTheme, setResolvedTheme] = useState(() => getResolved(localStorage.getItem("seekpal_theme") || "auto"));

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
  }, [resolvedTheme]);

  useEffect(() => {
    if (theme !== "auto") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e) => setResolvedTheme(e.matches ? "dark" : "light");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  function setTheme(t) {
    localStorage.setItem("seekpal_theme", t);
    setThemeState(t);
    setResolvedTheme(getResolved(t));
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
