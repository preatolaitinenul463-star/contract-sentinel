// In development, call backend directly to avoid Next.js proxy header issues.
// In production, use "/api" to go through the reverse proxy.
const API_BASE =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000/api"
    : process.env.NEXT_PUBLIC_API_BASE || "/api";

interface ApiOptions extends RequestInit {
  token?: string;
}

let _isRefreshing = false;

/**
 * Handle 401 errors - try to refresh token first, then redirect to login.
 */
function handleAuthError() {
  // Clear auth state
  try {
    const stored = localStorage.getItem("auth-storage");
    if (stored) {
      const state = JSON.parse(stored);
      state.state = { user: null, token: null, isAuthenticated: false };
      localStorage.setItem("auth-storage", JSON.stringify(state));
    }
  } catch {}

  // Redirect to login (avoid redirect loops)
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/auth")) {
    window.location.href = "/auth/login";
  }
}

async function tryRefreshToken(currentToken: string): Promise<string | null> {
  if (_isRefreshing) return null;
  _isRefreshing = true;
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${currentToken}`,
      },
    });
    if (response.ok) {
      const data = await response.json();
      // Update stored token
      try {
        const stored = localStorage.getItem("auth-storage");
        if (stored) {
          const state = JSON.parse(stored);
          state.state.token = data.access_token;
          localStorage.setItem("auth-storage", JSON.stringify(state));
        }
      } catch {}
      return data.access_token;
    }
    return null;
  } catch {
    return null;
  } finally {
    _isRefreshing = false;
  }
}

async function apiRequest<T>(
  endpoint: string,
  options: ApiOptions = {}
): Promise<T> {
  const { token, ...fetchOptions } = options;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  let response = await fetch(`${API_BASE}${endpoint}`, {
    ...fetchOptions,
    headers,
  });

  // On 401, try to refresh the token once
  if (response.status === 401 && token) {
    const newToken = await tryRefreshToken(token);
    if (newToken) {
      (headers as Record<string, string>)["Authorization"] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE}${endpoint}`, {
        ...fetchOptions,
        headers,
      });
    }
    if (response.status === 401) {
      handleAuthError();
    }
  }

  if (!response.ok) {
    // Retry on network/server errors (5xx), not client errors (4xx)
    if (response.status >= 500 && !endpoint.includes("/auth/")) {
      for (let retry = 0; retry < 2; retry++) {
        await new Promise((r) => setTimeout(r, 1000 * (retry + 1)));
        try {
          response = await fetch(`${API_BASE}${endpoint}`, {
            ...fetchOptions,
            headers,
          });
          if (response.ok) break;
        } catch {
          // continue retrying
        }
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "请求失败" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Auth API
export const authApi = {
  register: (data: { email: string; password: string; full_name?: string }) =>
    apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    apiRequest<{ access_token: string; token_type: string; expires_in: number }>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  me: (token: string) =>
    apiRequest("/auth/me", { token }),
};

// Contract API
export const contractApi = {
  upload: async (
    file: File,
    metadata: {
      contract_type?: string;
      jurisdiction?: string;
      party_role?: string;
    },
    token: string
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (metadata.contract_type) {
      formData.append("contract_type", metadata.contract_type);
    }
    if (metadata.jurisdiction) {
      formData.append("jurisdiction", metadata.jurisdiction);
    }
    if (metadata.party_role) {
      formData.append("party_role", metadata.party_role);
    }

    const response = await fetch(`${API_BASE}/contracts/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 401) handleAuthError();
      const error = await response.json().catch(() => ({ detail: "上传失败" }));
      throw new Error(error.detail);
    }

    return response.json();
  },

  list: (token: string, page = 1, pageSize = 20) =>
    apiRequest(`/contracts?page=${page}&page_size=${pageSize}`, { token }),

  get: (id: number, token: string) =>
    apiRequest(`/contracts/${id}`, { token }),

  delete: (id: number, token: string) =>
    apiRequest(`/contracts/${id}`, { method: "DELETE", token }),
};

// Review API
export const reviewApi = {
  start: (contractId: number, token: string) =>
    apiRequest<{ task_id: number; status: string }>("/review/start", {
      method: "POST",
      body: JSON.stringify({ contract_id: contractId }),
      token,
    }),

  /**
   * Stream review progress using fetch + ReadableStream (no token in URL).
   * Use Authorization header instead of EventSource with token in query string.
   */
  streamProgress: (contractId: number, token: string) => {
    return fetch(`${API_BASE}/review/stream/${contractId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  },

  getResult: (contractId: number, token: string) =>
    apiRequest(`/review/${contractId}`, { token }),

  exportReport: (reviewId: number, format: "docx" | "pdf" = "docx") => {
    window.open(`${API_BASE}/review/export/${reviewId}?format=${format}`, "_blank");
  },
};

// Compare API
export const compareApi = {
  compare: (contractAId: number, contractBId: number, token: string) =>
    apiRequest("/compare", {
      method: "POST",
      body: JSON.stringify({
        contract_a_id: contractAId,
        contract_b_id: contractBId,
      }),
      token,
    }),

  getResult: (id: number, token: string) =>
    apiRequest(`/compare/${id}`, { token }),

  uploadAndCompare: async (fileA: File, fileB: File) => {
    const formData = new FormData();
    formData.append("file_a", fileA);
    formData.append("file_b", fileB);

    return fetch(`${API_BASE}/compare/upload-and-compare`, {
      method: "POST",
      body: formData,
    });
  },
};

// Assistant API
export const assistantApi = {
  chat: (message: string, sessionId?: number, token?: string) =>
    apiRequest("/assistant/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
      token,
    }),

  getSessions: (token: string) =>
    apiRequest("/assistant/sessions", { token }),

  getSession: (id: number, token: string) =>
    apiRequest(`/assistant/sessions/${id}`, { token }),
};
