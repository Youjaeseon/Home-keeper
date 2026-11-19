import { apiBaseUrl } from './env';
import { supabase } from './supabase';

type ErrorBody = {
  code?: string;
  message?: string;
  input_revision?: number;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly inputRevision?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export type RecordSummary = {
  record_id: string;
  input_revision: number;
};

export type RecordDetail = {
  record_id: string;
  location: string | null;
  symptoms: string | null;
  input_revision: number;
  questions: unknown[];
  messages: unknown[];
};

async function parseError(response: Response): Promise<never> {
  const text = await response.text();
  let body: ErrorBody = {};
  try {
    body = JSON.parse(text) as ErrorBody;
  } catch {
    // Non-JSON error body, for example a proxy or network error page.
  }
  throw new ApiError(
    response.status,
    body.code ?? 'http_error',
    body.message ?? `요청에 실패했어요 (${response.status}).`,
    body.input_revision,
  );
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    throw new ApiError(401, 'not_authenticated', '로그인이 필요해요.');
  }

  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${session.access_token}`);
  if (init.body !== undefined) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    await parseError(response);
  }
  return (await response.json()) as T;
}

export async function checkHealth(): Promise<string> {
  const response = await fetch(`${apiBaseUrl}/health`);
  if (!response.ok) {
    await parseError(response);
  }
  const body = (await response.json()) as { status?: string };
  return body.status ?? 'unknown';
}

export function createRecord(): Promise<RecordSummary> {
  return apiRequest<RecordSummary>('/records', { method: 'POST' });
}

export function getRecord(recordId: string): Promise<RecordDetail> {
  return apiRequest<RecordDetail>(`/records/${recordId}`);
}
