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

export function messageOf(error: unknown): string {
  if (error instanceof ApiError) {
    const revision =
      error.inputRevision === undefined
        ? ''
        : ` (input_revision ${error.inputRevision})`;
    return `${error.message}${revision}`;
  }
  return error instanceof Error ? error.message : String(error);
}

export type RecordSummary = {
  record_id: string;
  input_revision: number;
};

export type SeverityLevel = 'low' | 'medium' | 'high' | 'undetermined';
export type RecommendedAction = 'self_care' | 'inspection' | 'provider_consult';
export type HousingType =
  | 'monthly_rent'
  | 'jeonse'
  | 'semi_jeonse'
  | 'owned'
  | 'other';

export type Profile = {
  nickname: string;
  role: 'requester' | 'provider';
  region_id: string;
  address: string | null;
  housing_type: HousingType;
};

export type ProfileInput = {
  nickname: string;
  region_id: string;
  address: string | null;
  housing_type: HousingType;
};

export type Region = {
  region_id: string;
  name: string;
  display_name: string;
};

export type RecordListItem = {
  record_id: string;
  location: string | null;
  material: string | null;
  symptoms: string | null;
  suspected_types: string[];
  severity_score: number | null;
  severity_level: SeverityLevel | null;
  created_at: string;
  updated_at: string;
};

export type DiagnosisResult = {
  observations: string;
  suspected_types: string[];
  severity_score: number | null;
  severity_level: SeverityLevel;
  reason: string;
  causes: string[];
  estimation_notice: string;
  recommended_action: RecommendedAction;
  care_steps: string[];
  supplies: string[];
  prevention_tips: string[];
  unknowns: string[];
  work_type_id: string | null;
  work_type_reason: string;
  source: 'sample';
};

export type AnalyzePhoto = {
  role: 'overview' | 'closeup';
  status: 'not_analyzed' | 'analyzed';
  source: 'sample' | 'yolo' | 'yolo_sam';
  detections: unknown[];
};

export type PhotoAnalysis = {
  applied: boolean;
  notice: string | null;
  photos: AnalyzePhoto[];
  source: 'sample' | 'yolo' | 'yolo_sam';
};

export type AnalyzeResponse = {
  record_id: string;
  input_revision: number;
  diagnosis_generation: number;
  photo_analysis: PhotoAnalysis;
  diagnosis: DiagnosisResult;
  source: 'sample' | 'yolo' | 'yolo_sam';
};

export type RecordDetail = {
  record_id: string;
  location: string | null;
  material: string | null;
  symptoms: string | null;
  photo_observations: PhotoAnalysis | null;
  input_revision: number;
  questions: unknown[];
  messages: unknown[];
  diagnosis: {
    diagnosis: DiagnosisResult;
    input_revision: number | null;
    generation: number;
    is_current: boolean;
  } | null;
};

export type AnalyzePhotoInput = {
  uri: string;
  name: string;
  type: string;
  role: 'overview' | 'closeup';
};

export type AnalyzeInput = {
  photos: AnalyzePhotoInput[];
  location: string;
  material: string;
  symptoms: string;
  externalAnalysisConsent: boolean;
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
  if (init.body !== undefined && !(init.body instanceof FormData)) {
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

export function getRecords(): Promise<RecordListItem[]> {
  return apiRequest<RecordListItem[]>('/records');
}

export function getMyProfile(): Promise<Profile> {
  return apiRequest<Profile>('/me/profile');
}

export function saveMyProfile(input: ProfileInput): Promise<Profile> {
  return apiRequest<Profile>('/me/profile', {
    method: 'PUT',
    body: JSON.stringify(input),
  });
}

export function getRegions(): Promise<Region[]> {
  return apiRequest<Region[]>('/regions');
}

export function getRecord(recordId: string): Promise<RecordDetail> {
  return apiRequest<RecordDetail>(`/records/${recordId}`);
}

export function analyzeRecord(
  recordId: string,
  input: AnalyzeInput,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  for (const photo of input.photos) {
    form.append(
      'photos',
      {
        uri: photo.uri,
        name: photo.name,
        type: photo.type,
      } as unknown as Blob,
    );
  }
  for (const photo of input.photos) {
    form.append('photo_roles', photo.role);
  }
  form.append(
    'external_analysis_consent',
    input.externalAnalysisConsent ? 'true' : 'false',
  );
  form.append('location', input.location.trim());
  form.append('material', input.material.trim());
  if (input.symptoms.trim()) {
    form.append('symptoms', input.symptoms.trim());
  }

  return apiRequest<AnalyzeResponse>(`/records/${recordId}/analyze`, {
    method: 'POST',
    body: form,
  });
}
