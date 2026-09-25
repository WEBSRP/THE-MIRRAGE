import { api } from './api';

export interface SessionResponse {
  session_id: string;
  mirage_ip: string;
  status: 'pending' | 'initializing' | 'provisioning' | 'ready' | 'stopping' | 'terminated' | 'expired' | 'error';
  mirage_port?: number;
  player_vpn_ip?: string;
  expires_at?: string;
  time_remaining_seconds?: number;
  message?: string;
}

export interface SessionStatusResponse {
  session_id: string;
  status: string;
  mirage_ip: string;
  mirage_port: number;
  player_vpn_ip: string;
  created_at: string;
  ready_at: string | null;
  expires_at: string;
  last_active_at: string;
  time_remaining_seconds: number;
  is_ready: boolean;
}

export interface SlotInfo {
  total_slots: number;
  active_slots: number;
  available_slots: number;
  is_slot_available: boolean;
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function createSession(): Promise<SessionResponse> {
  return api.post<SessionResponse>('/api/v1/session/start');
}

export async function getSessionStatus(sessionId?: string): Promise<SessionStatusResponse> {
  const query = sessionId ? `?session_id=${sessionId}` : '';
  return api.get<SessionStatusResponse>(`/api/v1/session/status${query}`);
}

export async function terminateSession(sessionId?: string): Promise<SessionResponse> {
  const query = sessionId ? `?session_id=${sessionId}` : '';
  return api.post<SessionResponse>(`/api/v1/session/stop${query}`);
}

export async function getSlotInfo(): Promise<SlotInfo> {
  return api.get<SlotInfo>('/api/v1/session/slots');
}

export const startSession = createSession;
export const stopSession = terminateSession;
