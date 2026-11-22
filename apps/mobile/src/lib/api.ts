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
  provider_id: string | null;
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

export type WorkType = {
  work_type_id: string;
  name: string;
};

export type ProviderSummary = {
  provider_id: string;
  name: string;
  phone: string | null;
  rating: number;
  review_count: number;
  description: string | null;
  specialty_work_types: WorkType[];
  chat_available: boolean;
  is_sample: boolean;
};

export type ProviderDetail = {
  provider_id: string;
  name: string;
  phone: string | null;
  rating: number;
  review_count: number;
  description: string | null;
  address: string | null;
  business_hours: string | null;
  career_years: number | null;
  chat_available: boolean;
  regions: Region[];
  work_types: WorkType[];
  is_sample: false;
};

export type ProviderSearchResponse = {
  providers: ProviderSummary[];
  is_sample: boolean;
};

export type SignedPhoto = {
  role: 'overview' | 'closeup';
  url: string;
  expires_at: string;
  width: number;
  height: number;
};

export type QuoteProposal = {
  proposal_id: string;
  created_at: string;
  provider: ProviderSummary;
  min_price: number;
  max_price: number;
  memo: string;
  status: 'pending' | 'accepted' | 'rejected';
};

export type QuoteRequestSummary = {
  request_id: string;
  record_id: string;
  region_id: string;
  region_name: string;
  work_type_id: string;
  work_type_name: string;
  address: string | null;
  location: string;
  material: string | null;
  memo: string | null;
  photos: SignedPhoto[];
  severity_score: number | null;
  severity_level: SeverityLevel | null;
  suspected_types: string[];
  status: 'open' | 'accepted' | 'cancelled';
  accepted_proposal_id: string | null;
  proposal_count: number;
  my_proposal_id: string | null;
  my_proposal_status: 'pending' | 'accepted' | 'rejected' | null;
  created_at: string;
};

export type QuoteRequestDetail = QuoteRequestSummary & {
  proposals: QuoteProposal[];
};

export type QuoteRequestInput = {
  record_id: string;
  region_id?: string | null;
  work_type_id?: string | null;
  address?: string | null;
  memo?: string | null;
};

export type QuoteProposalInput = {
  min_price: number;
  max_price: number;
  memo: string;
};

export type DraftTemplate = {
  kind: 'landlord' | 'provider';
  text: string;
  input_revision: number;
  diagnosis_generation: number | null;
};

export type ChatRoom = {
  room_id: string;
  requester_id: string;
  provider_id: string;
  provider_name: string;
  latest_record_id: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProviderQuery = {
  regionId: string;
  workTypeId?: string | null;
};

export type RecordListItem = {
  record_id: string;
  location: string | null;
  material: string | null;
  symptoms: string | null;
  region_id: string | null;
  region_name: string | null;
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
  source: 'llm' | 'sample';
};

export type VisionObservation = {
  suspected_types: string[];
  summary: string;
  approximate_location: string | null;
  unreadable_reason: string | null;
};

export type AnalyzePhoto = {
  role: 'overview' | 'closeup';
  status: 'not_analyzed' | 'analyzed' | 'failed';
  source: 'sample' | 'yolo' | 'yolo_sam' | 'vision_llm';
  detections: unknown[];
  vision_observation: VisionObservation | null;
};

export type PhotoAnalysis = {
  applied: boolean;
  notice: string | null;
  photos: AnalyzePhoto[];
  source: 'sample' | 'yolo' | 'yolo_sam' | 'vision_llm' | 'yolo_vision_llm';
};

export type AnalyzeResponse = {
  record_id: string;
  input_revision: number;
  diagnosis_generation: number;
  region_id: string | null;
  photo_analysis: PhotoAnalysis;
  diagnosis: DiagnosisResult;
  source: 'sample' | 'yolo' | 'yolo_sam' | 'vision_llm' | 'yolo_vision_llm';
};

export type DiagnosisResponse = {
  record_id: string;
  input_revision: number;
  diagnosis_generation: number;
  diagnosis: DiagnosisResult;
  source: 'llm' | 'sample';
};

export type RecordDetail = {
  record_id: string;
  location: string | null;
  material: string | null;
  symptoms: string | null;
  region_id: string | null;
  region_name: string | null;
  photo_observations: PhotoAnalysis | null;
  photos: SignedPhoto[];
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
  region_id: string | null;
  externalAnalysisConsent: boolean;
};

export type DeadlineKind = 'fixed' | 'always_open' | 'unknown';
export type SupportProgramSource = 'seed' | 'gov24_api';

export type SupportProgramListItem = {
  id: string;
  title: string;
  summary: string;
  organization_name: string;
  region_scope: 'national' | 'local';
  region_name: string;
  target_housing_types: HousingType[];
  deadline_text: string | null;
  deadline_date: string | null;
  deadline_kind: DeadlineKind;
  is_closed: boolean;
  detail_url: string;
  source: SupportProgramSource;
  source_attribution: string;
  source_checked_at: string;
  updated_at: string;
  housing_type_matched: boolean;
};

export type SupportProgramDetail = Omit<SupportProgramListItem, 'housing_type_matched'> & {
  support_target: string;
  support_content: string;
  selection_criteria: string | null;
  apply_method: string | null;
  synced_at: string | null;
};

export type SupportProgramListResponse = {
  items: SupportProgramListItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type SupportProgramQuery = {
  status?: 'all' | 'active';
  limit?: number;
  offset?: number;
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
  if (input.region_id) {
    form.append('region_id', input.region_id);
  }

  return apiRequest<AnalyzeResponse>(`/records/${recordId}/analyze`, {
    method: 'POST',
    body: form,
  });
}

export function regenerateDiagnosis(
  recordId: string,
  regenerate = false,
): Promise<DiagnosisResponse> {
  const query = regenerate ? '?regenerate=true' : '';
  return apiRequest<DiagnosisResponse>(`/records/${recordId}/diagnosis${query}`, {
    method: 'POST',
  });
}

export function getSupportPrograms({
  status = 'all',
  limit = 5,
  offset = 0,
}: SupportProgramQuery = {}): Promise<SupportProgramListResponse> {
  const params = new URLSearchParams({
    status,
    limit: String(limit),
    offset: String(offset),
  });
  return apiRequest<SupportProgramListResponse>(`/support-programs?${params}`);
}

export function getSupportProgram(programId: string): Promise<SupportProgramDetail> {
  return apiRequest<SupportProgramDetail>(`/support-programs/${programId}`);
}

export function getWorkTypes(): Promise<WorkType[]> {
  return apiRequest<WorkType[]>('/work-types');
}

export function getProviders({
  regionId,
  workTypeId,
}: ProviderQuery): Promise<ProviderSearchResponse> {
  const params = new URLSearchParams({ region_id: regionId });
  if (workTypeId) {
    params.set('work_type_id', workTypeId);
  }
  return apiRequest<ProviderSearchResponse>(`/providers?${params}`);
}

export function getProviderDetail(providerId: string): Promise<ProviderDetail> {
  return apiRequest<ProviderDetail>(`/providers/${providerId}`);
}

export type DraftKind = 'landlord' | 'provider';

export type DraftResponse = {
  kind: DraftKind;
  text: string;
  input_revision: number;
  diagnosis_generation: number;
};

export function createDraft(recordId: string, kind: DraftKind): Promise<DraftResponse> {
  return apiRequest<DraftResponse>(`/records/${recordId}/drafts/${kind}`, { method: 'POST' });
}

export function getDraftTemplate(
  recordId: string,
  kind: DraftKind = 'provider',
): Promise<DraftTemplate> {
  return apiRequest<DraftTemplate>(`/records/${recordId}/drafts/${kind}/template`);
}

export function createQuoteRequest(
  input: QuoteRequestInput,
): Promise<QuoteRequestDetail> {
  return apiRequest<QuoteRequestDetail>('/quote-requests', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function getQuoteRequests(): Promise<QuoteRequestSummary[]> {
  return apiRequest<QuoteRequestSummary[]>('/quote-requests');
}

export function getQuoteRequestDetail(requestId: string): Promise<QuoteRequestDetail> {
  return apiRequest<QuoteRequestDetail>(`/quote-requests/${requestId}`);
}

export function submitQuoteProposal(
  requestId: string,
  input: QuoteProposalInput,
): Promise<QuoteProposal> {
  return apiRequest<QuoteProposal>(`/quote-requests/${requestId}/proposals`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function acceptQuoteProposal(
  requestId: string,
  proposalId: string,
): Promise<QuoteRequestDetail> {
  return apiRequest<QuoteRequestDetail>(
    `/quote-requests/${requestId}/proposals/${proposalId}/accept`,
    { method: 'POST' },
  );
}

export function cancelQuoteRequest(requestId: string): Promise<QuoteRequestDetail> {
  return apiRequest<QuoteRequestDetail>(`/quote-requests/${requestId}/cancel`, {
    method: 'POST',
  });
}

export function createChatRoom(input: {
  provider_id: string;
  record_id?: string | null;
}): Promise<ChatRoom> {
  return apiRequest<ChatRoom>('/chat/rooms', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export type ChatRoomListItem = ChatRoom & {
  counterpart_name: string;
  last_message_preview: string | null;
  unread_count: number;
};

export type ChatMessage = {
  message_id: string;
  room_id: string;
  sender_id: string;
  sender_role: 'requester' | 'provider';
  message_type: 'text' | 'record_summary';
  record_id: string | null;
  content: string;
  payload: unknown;
  client_message_id: string;
  created_at: string;
};

export type ChatMessageListResponse = {
  messages: ChatMessage[];
  limit: number;
  offset: number;
  has_more: boolean;
};

export type ChatReadReceipt = {
  room_id: string;
  last_read_at: string;
  unread_count: number;
};

export function getChatRooms(): Promise<ChatRoomListItem[]> {
  return apiRequest<ChatRoomListItem[]>('/chat/rooms');
}

export function getChatMessages(
  roomId: string,
  { limit = 100, offset = 0 }: { limit?: number; offset?: number } = {},
): Promise<ChatMessageListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiRequest<ChatMessageListResponse>(`/chat/rooms/${roomId}/messages?${params}`);
}

export function sendChatMessage(
  roomId: string,
  input: { client_message_id: string; content: string },
): Promise<ChatMessage> {
  return apiRequest<ChatMessage>(`/chat/rooms/${roomId}/messages`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function markChatRoomRead(roomId: string): Promise<ChatReadReceipt> {
  return apiRequest<ChatReadReceipt>(`/chat/rooms/${roomId}/read`, { method: 'POST' });
}

/** 실시간 채팅 WebSocket 주소 (http → ws). 토큰은 연결할 때 붙입니다. */
export function chatSocketUrl(): string {
  return `${apiBaseUrl.replace(/^http/, 'ws')}/chat/ws`;
}

/** 클라이언트 메시지 멱등성 UUID (v4 형식) */
export function newClientMessageId(): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (c?.randomUUID) return c.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return (ch === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}
