import { api } from './api';

export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export async function getMe(): Promise<User> {
  return api.get<User>('/api/v1/auth/me');
}

export function logout(): void {
  localStorage.removeItem('mirrage-token');
}

export function getToken(): string | null {
  return localStorage.getItem('mirrage-token');
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export interface OtpResponse {
  message: string;
  resend_after_seconds: number;
}

export interface OtpTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  is_new_user: boolean;
  user: User;
}

export async function requestOtp(email: string): Promise<OtpResponse> {
  return api.post<OtpResponse>('/api/v1/auth/request-otp', { email });
}

export async function verifyOtp(email: string, otp: string): Promise<OtpTokenResponse> {
  const result = await api.post<OtpTokenResponse>('/api/v1/auth/verify-otp', { email, otp });
  localStorage.setItem('mirrage-token', result.access_token);
  return result;
}

export async function resendOtp(email: string): Promise<OtpResponse> {
  return api.post<OtpResponse>('/api/v1/auth/resend-otp', { email });
}
