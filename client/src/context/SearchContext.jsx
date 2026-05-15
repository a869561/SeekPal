import { createContext, useContext, useState } from "react";

const SearchContext = createContext(null);

export function SearchProvider({ children }) {
  const [query,     setQuery]     = useState("");
  const [submitted, setSubmitted] = useState("");
  const [results,   setResults]   = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [page,      setPage]      = useState(1);
  const [category,  setCategory]  = useState("");
  const [sourceId,  setSourceId]  = useState("");
  const [recent,    setRecent]    = useState([]);

  return (
    <SearchContext.Provider value={{
      query, setQuery,
      submitted, setSubmitted,
      results, setResults,
      loading, setLoading,
      page, setPage,
      category, setCategory,
      sourceId, setSourceId,
      recent, setRecent,
    }}>
      {children}
    </SearchContext.Provider>
  );
}

export const useSearch = () => useContext(SearchContext);
