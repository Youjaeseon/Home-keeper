/**
 * 앱 전역 상태.
 * - 인증: Supabase Auth 세션(자동 갱신·복원) + GET/PUT /me/profile
 * - 그 밖의 데이터는 아래 각 항목 주석을 따릅니다.
 */
import type { Session } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

import { Platform } from 'react-native';

import { matchRegion, toApiHousing, toUser } from '@/lib/adapters';
import {
  acceptQuoteProposal,
  ApiError,
  cancelQuoteRequest,
  chatSocketUrl,
  createChatRoom,
  createDraft,
  createQuoteRequest,
  getChatMessages,
  getChatRooms,
  getDraftTemplate,
  getMyProfile,
  getProviderDetail,
  getQuoteRequestDetail,
  getQuoteRequests,
  getRecord,
  getRecords,
  getRegions,
  markChatRoomRead,
  messageOf,
  newClientMessageId,
  saveMyProfile,
  sendChatMessage,
  submitQuoteProposal,
  type ChatMessage,
  type QuoteRequestDetail,
  type Region,
} from '@/lib/api';
import { supabase } from '@/lib/supabase';
import { splitLocation, toAnalysisResult, toDefect } from '@/services/analyze';
import type { Account, AnalysisResult, ChatThread, Estimate, Housing, Message, Photo, Proposal, User } from '@/types';
import { uid } from '@/utils';

/** 프로필 등록 화면에 넘길 가입 입력값 (프로필 저장 실패 시 같은 계정으로 재시도) */
export type PendingProfile = { nickname: string; region: string; housing: Housing; notice?: string };

type Store = {
  /** 세션 복원이 끝났는지 */
  ready: boolean;
  session: Session | null;
  user: User | null;
  /** 세션은 있지만 GET /me/profile이 404인 상태 → 프로필 등록 화면 */
  needsProfile: boolean;
  pendingProfile: PendingProfile | null;
  /** GET /regions (로그인 후) */
  regions: Region[];
  signup: (account: Account) => Promise<string | null>;
  login: (loginId: string, password: string) => Promise<string | null>;
  loginAsGuest: () => Promise<string | null>;
  logout: () => Promise<void>;
  /** 프로필 최초 등록·재시도 (PUT /me/profile) */
  saveProfile: (input: { nickname: string; regionId: string; housing: Housing }) => Promise<string | null>;
  /** 닉네임·지역·거주형태 수정 (PUT /me/profile). 지역은 표시 이름으로 받습니다. */
  updateUser: (patch: Partial<Pick<User, 'nickname' | 'region' | 'housing'>>) => Promise<string | null>;
  /** 로컬에서 고른 사진 (분석 요청 전, 기기 안에만 있음) */
  photos: Photo[];
  /** 내 분석 기록 (GET /records + GET /records/{id}) */
  analyses: AnalysisResult[];
  /** 채팅 목록 (GET /chat/rooms) */
  threads: ChatThread[];
  /** 불러온 채팅방 메시지 (GET /chat/rooms/{id}/messages + WebSocket) */
  messages: Message[];
  /** 견적 요청서 (GET /quote-requests). 화면 이름은 '견적 요청서' */
  estimates: Estimate[];
  /** 업체 제안서 (GET /quote-requests/{id}의 proposals). 화면 이름은 '업체 제안서' */
  proposals: Proposal[];
  addPhoto: (uri: string) => Photo;
  removePhoto: (id: string) => void;
  saveAnalysis: (result: AnalysisResult) => void;
  refreshAnalyses: () => Promise<void>;
  /** 결과 화면 진입 시 최신 상세(새 Signed URL)를 다시 받습니다. */
  loadAnalysis: (id: string) => Promise<string | null>;
  refreshThreads: () => Promise<void>;
  /** 업체와의 채팅방을 열거나 만듭니다(POST /chat/rooms). 분석 기록을 함께 공유할 수 있습니다. */
  openRoom: (input: { vendorId: string; roomId?: string; analysisId?: string }) => Promise<{ roomId?: string; error?: string }>;
  loadMessages: (roomId: string) => Promise<string | null>;
  sendMessage: (roomId: string, vendorId: string, text: string) => Promise<string | null>;
  refreshQuotes: () => Promise<void>;
  /** 유저 → 주변 업체: 견적 요청서 전송 (POST /quote-requests) */
  sendEstimate: (analysis: AnalysisResult, memo: string) => Promise<string | null>;
  /** 업체 → 유저: 업체 제안서 전송 (POST /quote-requests/{id}/proposals) */
  sendProposal: (estimateId: string, price: number, memo: string) => Promise<string | null>;
  /** 내 화면에서만 숨긴 항목 id (서버 삭제 API가 없는 항목) */
  hidden: string[];
  removeAnalysis: (id: string) => void;
  removeEstimate: (id: string) => Promise<string | null>;
  removeProposal: (id: string) => void;
  /** 수락한 업체 제안서: 견적 요청서 id → 업체 제안서 id (서버 accepted_proposal_id) */
  accepted: Record<string, string>;
  acceptProposal: (estimateId: string, proposalId: string) => Promise<string | null>;
};

const AppContext = createContext<Store | null>(null);

function authError(message: string): string {
  if (/invalid login credentials/i.test(message)) return 'ID(이메일) 또는 PW가 맞지 않습니다. 처음이라면 회원가입을 해 주세요.';
  if (/already registered/i.test(message)) return '이미 가입된 이메일입니다. 로그인해 주세요.';
  if (/password should be at least/i.test(message)) return 'PW는 6자 이상으로 정해 주세요.';
  if (/anonymous sign-ins are disabled/i.test(message))
    return '로그인 없이 둘러보기가 서버에서 꺼져 있습니다. 회원가입 후 이용해 주세요.';
  if (/email not confirmed/i.test(message)) return '이메일 인증을 마친 뒤 로그인해 주세요.';
  return message;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [needsProfile, setNeedsProfile] = useState(false);
  const [pendingProfile, setPendingProfile] = useState<PendingProfile | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [analyses, setAnalyses] = useState<AnalysisResult[]>([]);
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [estimates, setEstimates] = useState<Estimate[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [hiddenKeys, setHiddenKeys] = useState<string[]>([]);
  const loadedFor = useRef<string | null>(null);

  /** 세션이 생기면 지역 목록과 프로필을 불러옵니다. 프로필 404 → 등록 화면. */
  const loadProfile = useCallback(async (next: Session): Promise<string | null> => {
    try {
      const regionList = await getRegions();
      setRegions(regionList);
      try {
        const profile = await getMyProfile();
        const nextUser = toUser(profile, next.user.email ?? '', regionList);
        if (profile.provider_id) {
          // 업체 계정: 업체 소개는 GET /providers/{id}에서 가져옵니다(표시 전용).
          const detail = await getProviderDetail(profile.provider_id).catch(() => null);
          nextUser.intro = detail?.description ?? undefined;
        }
        setUser(nextUser);
        setNeedsProfile(false);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setUser(null);
          setNeedsProfile(true);
        } else throw e;
      }
      return null;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        await supabase.auth.signOut();
        return '로그인이 만료되었습니다. 다시 로그인해 주세요.';
      }
      return messageOf(e);
    }
  }, []);

  // 세션 복원·구독
  useEffect(() => {
    let alive = true;
    supabase.auth.getSession().then(async ({ data }) => {
      if (!alive) return;
      setSession(data.session);
      if (data.session) {
        loadedFor.current = data.session.user.id;
        await loadProfile(data.session);
      }
      if (alive) setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      if (!next) {
        loadedFor.current = null;
        setUser(null);
        setNeedsProfile(false);
        setPendingProfile(null);
        setRegions([]);
        setPhotos([]);
        setAnalyses([]);
        setThreads([]);
        setMessages([]);
        setEstimates([]);
        setProposals([]);
      }
    });
    return () => {
      alive = false;
      sub.subscription.unsubscribe();
    };
  }, [loadProfile]);

  const afterSignIn = async (next: Session) => {
    loadedFor.current = next.user.id;
    return loadProfile(next);
  };

  const me = session?.user.id ?? '';
  const hide = (id: string) => setHiddenKeys((prev) => [...prev, `${me}:${id}`]);
  const isProvider = user?.role === '업체';
  const housing = user?.housing ?? '기타';
  const analysesRef = useRef(analyses);
  useEffect(() => {
    analysesRef.current = analyses;
  }, [analyses]);
  const loadedRooms = useRef(new Set<string>());

  const toMessage = useCallback(
    (m: ChatMessage, vendorId: string): Message => ({
      id: m.message_id,
      roomId: m.room_id,
      vendorId,
      from: m.sender_id === me ? 'me' : 'vendor',
      text: m.content,
      at: Date.parse(m.created_at),
    }),
    [me],
  );

  const mergeMessages = useCallback((incoming: Message[]) => {
    setMessages((prev) => {
      const map = new Map(prev.map((m) => [m.id, m]));
      for (const m of incoming) map.set(m.id, m);
      return [...map.values()].sort((x, y) => x.at - y.at);
    });
  }, []);

  const refreshAnalyses = useCallback(async () => {
    const items = await getRecords();
    setAnalyses((prev) => {
      const known = new Map(prev.map((a) => [a.id, a]));
      return items
        .filter((r) => r.severity_level !== null)
        .map((r) => {
          const old = known.get(r.record_id);
          const undetermined = r.severity_level === 'undetermined';
          const { location, position } = splitLocation(r.location);
          const created = Date.parse(r.created_at);
          const summary: AnalysisResult = {
            id: r.record_id,
            photoId: r.record_id,
            photoUri: old?.photoUri ?? '',
            location,
            position,
            occurredAt: new Date(created).toLocaleDateString('ko-KR'),
            housing,
            defect: toDefect(r.suspected_types, undetermined),
            risk: r.severity_score ?? 0,
            region: null,
            cause: '',
            solutions: [],
            prevention: [],
            guide: { title: '', body: '' },
            needsRetake: undetermined,
            createdAt: created,
          };
          return old && old.cause ? { ...old, defect: summary.defect, risk: summary.risk } : summary;
        });
    });
  }, [housing]);

  const refreshThreads = useCallback(async () => {
    const rooms = await getChatRooms();
    setThreads(
      rooms.map((r) => ({
        roomId: r.room_id,
        vendorId: r.provider_id,
        name: r.counterpart_name,
        last: r.last_message_preview,
        unread: r.unread_count,
      })),
    );
  }, []);

  const loadMessages = useCallback(
    async (roomId: string) => {
      try {
        const room = threads.find((t) => t.roomId === roomId);
        const all: Message[] = [];
        for (let offset = 0; ; offset += 100) {
          const page = await getChatMessages(roomId, { limit: 100, offset });
          all.push(...page.messages.map((m) => toMessage(m, room?.vendorId ?? '')));
          if (!page.has_more) break;
        }
        loadedRooms.current.add(roomId);
        mergeMessages(all);
        await markChatRoomRead(roomId).catch(() => null);
        setThreads((prev) => prev.map((t) => (t.roomId === roomId ? { ...t, unread: 0 } : t)));
        return null;
      } catch (e) {
        return messageOf(e);
      }
    },
    [threads, toMessage, mergeMessages],
  );

  const refreshQuotes = useCallback(async () => {
    const list = await getQuoteRequests();
    const details = await Promise.all(
      list.map((q) => getQuoteRequestDetail(q.request_id).catch(() => ({ ...q, proposals: [] }) as QuoteRequestDetail)),
    );
    setEstimates(
      details.map((q) => ({
        id: q.request_id,
        // 요청인 목록은 모두 내 요청서, 업체 목록은 모두 다른 사람 요청서입니다.
        userId: isProvider ? `requester:${q.request_id}` : me,
        // TODO(integration-gap): GAP-016 업체에게 요청인 닉네임을 주지 않아 지역만 표시합니다.
        userNickname: isProvider ? '요청인' : (user?.nickname ?? ''),
        region: q.region_name,
        analysisId: q.record_id,
        photoUri: q.photos[0]?.url ?? '',
        defect: q.suspected_types[0] ?? q.work_type_name,
        risk: q.severity_score ?? 0,
        location: splitLocation(q.location).location,
        position: splitLocation(q.location).position || q.work_type_name,
        memo: q.memo ?? '',
        createdAt: Date.parse(q.created_at),
        status: q.status,
        acceptedProposalId: q.accepted_proposal_id,
      })),
    );
    setProposals(
      details.flatMap((q) =>
        q.proposals.map((p) => ({
          id: p.proposal_id,
          estimateId: q.request_id,
          vendorId: isProvider ? me : p.provider.provider_id,
          vendorName: p.provider.name,
          vendorIntro: p.provider.description ?? '',
          // TODO(integration-gap): GAP-017 업체 제안서 응답에 업체 지역이 없습니다.
          vendorRegion: '',
          price: Math.round(p.min_price / 10000),
          priceMax: Math.round(p.max_price / 10000),
          memo: p.memo,
          createdAt: Date.parse(p.created_at),
        })),
      ),
    );
  }, [isProvider, me, user?.nickname]);

  // 로그인 후 목록 불러오기
  useEffect(() => {
    if (!user) return;
    // 서버 데이터 동기화(비동기 fetch 후 setState)이므로 의도된 effect입니다.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshAnalyses().catch(() => null);
    void refreshThreads().catch(() => null);
    void refreshQuotes().catch(() => null);
  }, [user, refreshAnalyses, refreshThreads, refreshQuotes]);

  // 실시간 채팅 WebSocket: 끊기면 재연결하고, 재연결 뒤에는 REST로 이력을 다시 맞춥니다.
  const roomsRef = useRef({ loadMessages, refreshThreads, toMessage, mergeMessages, threads });
  useEffect(() => {
    roomsRef.current = { loadMessages, refreshThreads, toMessage, mergeMessages, threads };
  }, [loadMessages, refreshThreads, toMessage, mergeMessages, threads]);
  useEffect(() => {
    if (!user || !session) return;
    let ws: WebSocket | null = null;
    let closed = false;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const connect = async () => {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token || closed) return;
      // 네이티브는 Authorization 헤더, 웹 브라우저는 헤더를 못 붙여 access_token 쿼리를 씁니다.
      ws =
        Platform.OS === 'web'
          ? new WebSocket(`${chatSocketUrl()}?access_token=${encodeURIComponent(token)}`)
          : new (WebSocket as unknown as new (u: string, p: undefined, o: object) => WebSocket)(chatSocketUrl(), undefined, {
              headers: { Authorization: `Bearer ${token}` },
            });
      ws.onmessage = (ev) => {
        let event: { type?: string; room_id?: string; message?: ChatMessage };
        try {
          event = JSON.parse(String(ev.data));
        } catch {
          return;
        }
        const r = roomsRef.current;
        if (event.type === 'ready') {
          if (retry > 0) for (const id of loadedRooms.current) void r.loadMessages(id);
          retry = 0;
          return;
        }
        if (event.type === 'message' && event.message) {
          const room = r.threads.find((t) => t.roomId === event.room_id);
          if (loadedRooms.current.has(event.message.room_id)) r.mergeMessages([r.toMessage(event.message, room?.vendorId ?? '')]);
          void r.refreshThreads().catch(() => null);
        }
      };
      ws.onclose = () => {
        if (closed) return;
        retry += 1;
        timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry));
      };
    };
    void connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [user, session]);

  const landlordDraft = async (recordId: string): Promise<string | null> => {
    try {
      return (await createDraft(recordId, 'landlord')).text;
    } catch (e) {
      // 모델 실패(502/503/504)면 모델 없이 만든 기본 양식으로 대체합니다.
      if (e instanceof ApiError && [502, 503, 504].includes(e.status)) {
        return (await getDraftTemplate(recordId, 'landlord').catch(() => null))?.text ?? null;
      }
      return null;
    }
  };

  const store: Store = {
    ready,
    session,
    user,
    needsProfile,
    pendingProfile,
    regions,
    photos,
    analyses: analyses.filter((a) => !hiddenKeys.includes(`${me}:${a.id}`)),
    threads,
    messages,
    estimates,
    proposals,
    hidden: hiddenKeys.filter((k) => k.startsWith(`${me}:`)).map((k) => k.slice(me.length + 1)),
    async signup(account) {
      if (account.role === '업체') {
        // TODO(integration-gap): GAP-003 백엔드는 가입 시 역할을 항상 requester로 정하므로 앱에서 업체 계정을 만들 수 없습니다.
        return '업체 계정은 운영팀이 사전 등록한 계정으로만 로그인할 수 있어요. 유저로 가입해 주세요.';
      }
      const { data, error } = await supabase.auth.signUp({ email: account.loginId, password: account.password });
      if (error) return authError(error.message);
      if (!data.session) return '가입 확인 메일을 보냈어요. 이메일 인증을 마친 뒤 로그인해 주세요.';
      const err = await afterSignIn(data.session);
      if (err) return err;
      const regionList = await getRegions().catch(() => [] as Region[]);
      const region = matchRegion(account.region, regionList);
      if (!region) {
        setPendingProfile({
          nickname: account.nickname,
          region: account.region,
          housing: account.housing,
          notice: `'${account.region}'은(는) 아직 서비스 지역이 아니에요. 서버에 등록된 지역에서 다시 골라 주세요.`,
        });
        setNeedsProfile(true);
        return null;
      }
      try {
        const profile = await saveMyProfile({
          nickname: account.nickname,
          region_id: region.region_id,
          address: null,
          housing_type: toApiHousing(account.housing),
        });
        setUser(toUser(profile, data.session.user.email ?? account.loginId, regionList));
        setNeedsProfile(false);
        return null;
      } catch (e) {
        // 계정은 이미 만들어졌으므로 다시 가입하지 않고 프로필 저장만 재시도합니다.
        setPendingProfile({ nickname: account.nickname, region: account.region, housing: account.housing, notice: messageOf(e) });
        setNeedsProfile(true);
        return null;
      }
    },
    async login(loginId, password) {
      const { data, error } = await supabase.auth.signInWithPassword({ email: loginId, password });
      if (error) return authError(error.message);
      return afterSignIn(data.session);
    },
    async loginAsGuest() {
      // TODO(integration-gap): GAP-001 Supabase 익명 로그인이 켜져 있어야 동작합니다.
      const { data, error } = await supabase.auth.signInAnonymously();
      if (error || !data.session) return authError(error?.message ?? '둘러보기를 시작하지 못했습니다.');
      return afterSignIn(data.session);
    },
    async logout() {
      await supabase.auth.signOut();
    },
    async saveProfile({ nickname, regionId, housing }) {
      if (!session) return '로그인이 필요해요.';
      try {
        const profile = await saveMyProfile({
          nickname: nickname.trim(),
          region_id: regionId,
          address: null,
          housing_type: toApiHousing(housing),
        });
        setUser(toUser(profile, session.user.email ?? '', regions));
        setNeedsProfile(false);
        setPendingProfile(null);
        return null;
      } catch (e) {
        return messageOf(e);
      }
    },
    async updateUser(patch) {
      if (!user || !session) return '로그인이 필요해요.';
      const next = { ...user, ...patch };
      const region = regions.find((r) => r.display_name === next.region);
      if (!region) return '지역을 다시 선택해 주세요.';
      if (!next.nickname.trim()) return '닉네임을 입력해 주세요.';
      setUser({ ...next, regionId: region.region_id });
      try {
        const profile = await saveMyProfile({
          nickname: next.nickname.trim(),
          region_id: region.region_id,
          address: user.address,
          housing_type: toApiHousing(next.housing),
        });
        setUser(toUser(profile, session.user.email ?? '', regions));
        return null;
      } catch (e) {
        setUser(user);
        return messageOf(e);
      }
    },
    addPhoto(uri) {
      const photo = { id: uid(), uri, createdAt: Date.now() };
      setPhotos((prev) => [photo, ...prev]);
      return photo;
    },
    removePhoto(id) {
      setPhotos((prev) => prev.filter((p) => p.id !== id));
    },
    saveAnalysis(result) {
      setAnalyses((prev) => [result, ...prev.filter((a) => a.id !== result.id)]);
    },
    refreshAnalyses,
    async loadAnalysis(id) {
      try {
        const detail = await getRecord(id);
        const old = analysesRef.current.find((a) => a.id === id);
        // 자가 거주자는 임대인 요청문을 만들지 않습니다.
        const tenant = housing !== '자가' && housing !== '기타' && !isProvider;
        const draft = tenant && detail.diagnosis ? await landlordDraft(id) : null;
        const result = toAnalysisResult(detail, {
          housing,
          occurredAt: old?.occurredAt ?? new Date().toLocaleDateString('ko-KR'),
          createdAt: old?.createdAt ?? Date.now(),
          photoUri: old?.photoUri,
          landlordDraft: draft,
        });
        if (!result) return '아직 진단 결과가 없는 기록입니다.';
        setAnalyses((prev) => (prev.some((a) => a.id === id) ? prev.map((a) => (a.id === id ? result : a)) : [result, ...prev]));
        return null;
      } catch (e) {
        return messageOf(e);
      }
    },
    refreshThreads,
    async openRoom({ vendorId, roomId, analysisId }) {
      if (roomId && !analysisId) return { roomId };
      try {
        const room = await createChatRoom({ provider_id: vendorId, record_id: analysisId ?? null });
        await refreshThreads().catch(() => null);
        return { roomId: room.room_id };
      } catch (e) {
        // 샘플 업체는 404, 계정이 연결되지 않은 업체는 422입니다.
        if (e instanceof ApiError && (e.status === 404 || e.status === 422))
          return { error: '이 업체는 아직 앱 채팅을 지원하지 않아요. 전화로 문의해 주세요.' };
        return { error: messageOf(e) };
      }
    },
    loadMessages,
    async sendMessage(roomId, vendorId, text) {
      try {
        const saved = await sendChatMessage(roomId, { client_message_id: newClientMessageId(), content: text });
        loadedRooms.current.add(roomId);
        mergeMessages([toMessage(saved, vendorId)]);
        return null;
      } catch (e) {
        return messageOf(e);
      }
    },
    refreshQuotes,
    async sendEstimate(analysis, memo) {
      try {
        await createQuoteRequest({ record_id: analysis.id, memo: memo || null });
        await refreshQuotes();
        return null;
      } catch (e) {
        if (e instanceof ApiError && e.code === 'request_already_open') return '이 분석 결과로 이미 진행 중인 견적 요청서가 있어요.';
        if (e instanceof ApiError && e.code === 'diagnosis_required') return '진단 결과가 바뀌었어요. 분석을 다시 확인해 주세요.';
        return messageOf(e);
      }
    },
    async sendProposal(estimateId, price, memo) {
      if (!memo.trim()) return '제안 메모를 입력해 주세요. (작업 범위·방문 가능 일정 등)';
      try {
        await submitQuoteProposal(estimateId, { min_price: price * 10000, max_price: price * 10000, memo: memo.trim() });
        await refreshQuotes();
        return null;
      } catch (e) {
        if (e instanceof ApiError && e.code === 'proposal_already_exists') return '이미 이 견적 요청서에 업체 제안서를 보냈어요.';
        if (e instanceof ApiError && e.code === 'request_not_open') return '이미 마감된 견적 요청서예요.';
        return messageOf(e);
      }
    },
    accepted: Object.fromEntries(
      estimates.filter((e) => e.acceptedProposalId).map((e) => [e.id, e.acceptedProposalId as string]),
    ),
    async acceptProposal(estimateId, proposalId) {
      try {
        await acceptQuoteProposal(estimateId, proposalId);
        await refreshQuotes();
        return null;
      } catch (e) {
        if (e instanceof ApiError && e.code === 'request_not_open') return '이미 마감되었거나 취소된 견적 요청서예요.';
        return messageOf(e);
      }
    },
    removeAnalysis(id) {
      // TODO(integration-gap): GAP-015 기록 삭제 API가 없어 내 화면에서만 숨깁니다.
      hide(id);
    },
    async removeEstimate(id) {
      const mine = estimates.find((e) => e.id === id && e.userId === me);
      if (mine && mine.status === 'open') {
        try {
          await cancelQuoteRequest(id);
          await refreshQuotes();
          return null;
        } catch (e) {
          return messageOf(e);
        }
      }
      hide(id);
      return null;
    },
    removeProposal(id) {
      // TODO(integration-gap): GAP-015 업체 제안서 삭제·철회 API가 없어 내 화면에서만 숨깁니다.
      hide(id);
    },
  };

  return <AppContext.Provider value={store}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
