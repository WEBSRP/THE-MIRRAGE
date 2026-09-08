import { api } from './api';

export interface ActivityLog {
  id: string;
  event_type: string;
  summary: string;
  payload: Record<string, unknown>;
  source_ip: string | null;
  timestamp: string;
}

export async function getActivity(limit = 50, offset = 0): Promise<ActivityLog[]> {
  return api.get<ActivityLog[]>(`/api/v1/activity/?limit=${limit}&offset=${offset}`);
}
