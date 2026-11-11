export class ApiError extends Error {
  constructor(public code: string, message: string) { super(message); }
}

export async function api<T>(path: string, options: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method: options.method ?? "GET", credentials: "same-origin", cache: "no-store",
      ...(options.body !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(options.body) } : {}),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("NETWORK_ERROR", "연결을 확인해 주세요. 변경한 답안이 저장되지 않았을 수 있습니다.");
  }
  if (!response.headers.get("content-type")?.includes("application/json")) {
    if (response.ok || response.status === 401 || response.status === 403) {
      throw new ApiError("ACCESS_CONFIRMATION_REQUIRED", "접속 확인이 필요합니다. 화면을 새로고침한 뒤 다시 확인해 주세요.");
    }
    throw new ApiError("SERVICE_UNAVAILABLE", "문제은행에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }
  let data;
  try { data = await response.json(); }
  catch { throw new ApiError("INVALID_RESPONSE", "응답을 확인하지 못했습니다. 현재 상태를 다시 불러와 주세요."); }
  if (!response.ok) throw new ApiError(data.error?.code ?? "REQUEST_FAILED", data.error?.message ?? "요청을 처리하지 못했습니다. 다시 확인해 주세요.");
  return data as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "요청을 처리하지 못했습니다. 다시 확인해 주세요.";
}

export const keys = {
  catalog: ["catalog"] as const,
  active: ["active-sessions"] as const,
  session: (id: string) => ["session", id] as const,
  item: (session: string, item: string) => ["item", session, item] as const,
  result: (id: string) => ["result", id] as const,
};

export function questionLabel(key: string) {
  const match = /^S([12])-Q(\d+)$/.exec(key);
  return match ? `${match[1]}과목 ${Number(match[2])}번` : key;
}
