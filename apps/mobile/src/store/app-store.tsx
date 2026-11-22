/**
 * 앱 전역 상태.
 * - 인증: Supabase Auth 세션(자동 갱신·복원) + GET/PUT /me/profile
 * - 그 밖의 데이터는 아래 각 항목 주석을 따릅니다.
 */
import type { Session } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

import { matchRegion, toApiHousing, toUser } from '@/lib/adapters';
import { ApiError, getMyProfile, getRegions, messageOf, saveMyProfile, type Region } from '@/lib/api';
import { supabase } from '@/lib/supabase';
import { getVendor } from '@/data/vendors';
import type { Account, AnalysisResult, Estimate, Housing, Message, Photo, Proposal, User } from '@/types';
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
  /** 외부 AI 분석 동의 여부. 익명(둘러보기) 세션은 동의하지 않은 것으로 봅니다. */
  analysisConsent: boolean;
  signup: (account: Account) => Promise<string | null>;
  login: (loginId: string, password: string) => Promise<string | null>;
  loginAsGuest: () => Promise<string | null>;
  logout: () => Promise<void>;
  /** 프로필 최초 등록·재시도 (PUT /me/profile) */
  saveProfile: (input: { nickname: string; regionId: string; housing: Housing }) => Promise<string | null>;
  /** 닉네임·지역·거주형태 수정 (PUT /me/profile). 지역은 표시 이름으로 받습니다. */
  updateUser: (patch: Partial<Pick<User, 'nickname' | 'region' | 'housing'>>) => Promise<string | null>;
  photos: Photo[];
  analyses: AnalysisResult[];
  messages: Message[];
  estimates: Estimate[];
  proposals: Proposal[];
  addPhoto: (uri: string) => Photo;
  removePhoto: (id: string) => void;
  saveAnalysis: (result: AnalysisResult) => void;
  sendMessage: (vendorId: string, text: string) => void;
  /** 유저 → 주변 업체: 견적서 전송 */
  sendEstimate: (analysis: AnalysisResult, memo: string) => void;
  /** 업체 → 유저: 제안서 전송 */
  sendProposal: (estimateId: string, price: number, memo: string) => void;
  /** 지운(숨긴) 견적서·제안서 id. 예시나 남이 보낸 항목은 내 화면에서만 숨깁니다. */
  hidden: string[];
  removeAnalysis: (id: string) => void;
  removeEstimate: (id: string) => void;
  removeProposal: (id: string) => void;
  /** 내가 수락한 제안서: 견적서 id → 제안서 id */
  accepted: Record<string, string>;
  acceptProposal: (estimateId: string, proposalId: string) => void;
  /** 수락 취소: 수락 전 상태로 되돌립니다. */
  cancelAccept: (estimateId: string) => void;
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
  const [messages, setMessages] = useState<Message[]>([]);
  const [estimates, setEstimates] = useState<Estimate[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [hiddenKeys, setHiddenKeys] = useState<string[]>([]);
  const [acceptedKeys, setAcceptedKeys] = useState<Record<string, string>>({});
  const loadedFor = useRef<string | null>(null);

  /** 세션이 생기면 지역 목록과 프로필을 불러옵니다. 프로필 404 → 등록 화면. */
  const loadProfile = useCallback(async (next: Session): Promise<string | null> => {
    try {
      const regionList = await getRegions();
      setRegions(regionList);
      try {
        const profile = await getMyProfile();
        setUser(toUser(profile, next.user.email ?? '', regionList));
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

  const me = user?.loginId ?? '';
  const hide = (id: string) => setHiddenKeys((prev) => [...prev, `${me}:${id}`]);

  const store: Store = {
    ready,
    session,
    user,
    needsProfile,
    pendingProfile,
    regions,
    analysisConsent: !!session && !session.user.is_anonymous,
    photos,
    analyses,
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
      setAnalyses((prev) => [result, ...prev]);
    },
    sendMessage(vendorId, text) {
      const mine: Message = { id: uid(), vendorId, from: 'me', text, at: Date.now() };
      setMessages((prev) => [...prev, mine]);
      // 가상 업체 자동 응답 (시뮬레이션)
      setTimeout(() => {
        const vendor = getVendor(vendorId);
        const reply: Message = {
          id: uid(),
          vendorId,
          from: 'vendor',
          text: `${vendor?.name ?? '업체'}입니다. 문의 감사합니다. 사진을 확인한 뒤 예상 견적과 방문 가능 일정을 안내해 드릴게요.\n※ 가상 업체 자동 응답입니다.`,
          at: Date.now(),
        };
        setMessages((prev) => [...prev, reply]);
      }, 1200);
    },
    sendEstimate(analysis, memo) {
      if (!user) return;
      const estimate: Estimate = {
        id: uid(),
        userId: user.loginId,
        userNickname: user.nickname,
        region: user.region,
        analysisId: analysis.id,
        photoUri: analysis.photoUri,
        defect: analysis.defect,
        risk: analysis.risk,
        location: analysis.location,
        position: analysis.position,
        memo,
        createdAt: Date.now(),
      };
      setEstimates((prev) => [estimate, ...prev]);
    },
    sendProposal(estimateId, price, memo) {
      if (!user) return;
      const proposal: Proposal = {
        id: uid(),
        estimateId,
        vendorId: user.loginId,
        vendorName: user.nickname,
        vendorIntro: user.intro ?? '',
        vendorRegion: user.region,
        price,
        memo,
        createdAt: Date.now(),
      };
      setProposals((prev) => [proposal, ...prev]);
    },
    accepted: Object.fromEntries(
      Object.entries(acceptedKeys)
        .filter(([k]) => k.startsWith(`${me}:`))
        .map(([k, v]) => [k.slice(me.length + 1), v]),
    ),
    acceptProposal(estimateId, proposalId) {
      setAcceptedKeys((prev) => ({ ...prev, [`${me}:${estimateId}`]: proposalId }));
    },
    cancelAccept(estimateId) {
      setAcceptedKeys((prev) => {
        const next = { ...prev };
        delete next[`${me}:${estimateId}`];
        return next;
      });
    },
    removeAnalysis(id) {
      setAnalyses((prev) => prev.filter((a) => a.id !== id));
    },
    removeEstimate(id) {
      // 내가 보낸 견적서는 받은 제안서와 함께 완전히 지우고, 그 밖(예시·받은 견적서)은 내 화면에서만 숨깁니다.
      if (estimates.some((e) => e.id === id && e.userId === me)) {
        setEstimates((prev) => prev.filter((e) => e.id !== id));
        setProposals((prev) => prev.filter((p) => p.estimateId !== id));
      } else hide(id);
    },
    removeProposal(id) {
      // 내가 보낸 제안서는 완전히 지우고, 받은 제안서(예시 포함)는 내 화면에서만 숨깁니다.
      if (proposals.some((p) => p.id === id && p.vendorId === me)) {
        setProposals((prev) => prev.filter((p) => p.id !== id));
      } else hide(id);
    },
  };

  return <AppContext.Provider value={store}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
