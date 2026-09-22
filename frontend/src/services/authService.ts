import { api } from './api';

export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface LoginRequest {
  username_or_email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export async function login(data: LoginRequest): Promise<AuthResponse> {
  const result = await api.post<AuthResponse>('/api/v1/auth/login', data);
  localStorage.setItem('mirrage-token', result.access_token);
  return result;
}

export async function register(data: RegisterRequest): Promise<User> {
  return api.post<User>('/api/v1/auth/register', data);
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

export async function devLogin(): Promise<AuthResponse> {
  const result = await api.post<AuthResponse>('/api/v1/auth/dev-login');
  localStorage.setItem('mirrage-token', result.access_token);
  return result;
}

export interface OtpResponse {
  message: string;
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
