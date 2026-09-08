import { api } from './api';

export interface VpnStatus {
  is_connected: boolean;
  assigned_ip: string | null;
  bytes_received: number;
  bytes_sent: number;
  connected_since: string | null;
  last_seen_at: string | null;
  indicator: 'connected' | 'disconnected' | 'standby';
}

export interface VpnProfile {
  filename: string;
  config_data: string;
  client_ip: string;
}

export async function getVpnStatus(): Promise<VpnStatus> {
  return api.get<VpnStatus>('/api/v1/vpn/status');
}

export async function getVpnProfile(): Promise<VpnProfile> {
  return api.get<VpnProfile>('/api/v1/vpn/profile');
}

export async function downloadVpnConfig(): Promise<void> {
  const blob = await api.download('/api/v1/vpn/download');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'mirrage.ovpn';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function downloadSignalConfig(): Promise<void> {
  const profile = await getVpnProfile();
  const blob = new Blob([profile.config_data], { type: 'application/x-openvpn-profile' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = profile.filename || 'mirrage-signal.ovpn';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
