import { api } from './api';

export interface Challenge {
  id: string;
  slug: string;
  title: string;
  category: string;
  description: string;
  points: number;
  hint: string;
  is_solved: boolean;
}

export interface FlagSubmitRequest {
  challenge_slug: string;
  flag: string;
}

export interface FlagSubmitResponse {
  is_correct: boolean;
  message: string;
  points_awarded: number;
  already_solved: boolean;
}

export async function getChallenges(): Promise<Challenge[]> {
  return api.get<Challenge[]>('/api/v1/challenges/');
}

export async function submitFlag(data: FlagSubmitRequest): Promise<FlagSubmitResponse> {
  return api.post<FlagSubmitResponse>('/api/v1/challenges/submit', data);
}
