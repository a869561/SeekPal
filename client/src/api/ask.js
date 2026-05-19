/**
 * SSE-over-POST client for the /api/ask endpoint.
 * Uses fetch + ReadableStream because EventSource doesn't support POST.
 */

export async function askStream(body, { onCitations, onToken, onDone, onError, signal } = {}) {
  const token = localStorage.getItem("seekpal_token");

  let res;
  try {
    res = await fetch("/api/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err.name !== "AbortError") onError?.({ code: "network_error", message: err.message });
    return;
  }

  if (!res.ok) {
    onError?.({ code: "http_error", message: `HTTP ${res.status}` });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === "retrieved") onCitations?.(event.citations);
          else if (event.type === "token") onToken?.(event.text);
          else if (event.type === "done") onDone?.();
          else if (event.type === "error") onError?.(event);
        } catch {
          // ignore malformed SSE data
        }
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") onError?.({ code: "stream_error", message: err.message });
  } finally {
    reader.releaseLock();
  }
}
