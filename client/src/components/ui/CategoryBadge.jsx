/**
 * Badge de categoría de fichero. ÚNICA fuente de verdad del color por categoría
 * en la UI (los mismos tokens --cat-* alimentan también el gráfico de tipos).
 * Las clases son literales completas para que Tailwind las detecte.
 */
const TONE = {
  text:     "bg-cat-text-soft text-cat-text",
  document: "bg-cat-document-soft text-cat-document",
  image:    "bg-cat-image-soft text-cat-image",
  audio:    "bg-cat-audio-soft text-cat-audio",
  video:    "bg-cat-video-soft text-cat-video",
  other:    "bg-cat-other-soft text-cat-other",
};

export default function CategoryBadge({ category, children, className = "" }) {
  const tone = TONE[category] ?? TONE.other;
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${tone} ${className}`}>
      {children}
    </span>
  );
}
