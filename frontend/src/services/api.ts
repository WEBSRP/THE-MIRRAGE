const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface ApiError {
  error: boolean;
  code: string;
  message: string;
}

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getHeaders(): HeadersInit {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('mirrage-token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      let message = 'Network error';
      if (data) {
        message = data.detail || data.message || `Request failed with status ${res.status}`;
      }
      throw { error: true, code: res.status.toString(), message } as ApiError;
    }
    return res.json();
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      let message = 'Network error';
      if (data) {
        message = data.detail || data.message || `Request failed with status ${res.status}`;
      }
      throw { error: true, code: res.status.toString(), message } as ApiError;
    }
    return res.json();
  }

  async download(path: string): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Download failed');
    return res.blob();
  }
}

export const api = new ApiClient(API_BASE);
