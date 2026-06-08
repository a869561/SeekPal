/**
 * Placeholder de carga con barrido (shimmer). Sustituye spinners genéricos.
 */
export default function Skeleton({ className = "", rounded = "rounded-lg" }) {
  return <div className={`skeleton ${rounded} ${className}`} />;
}
