/**
 * 앱 전역 상태 (MVP용 in-memory). 새로고침하면 초기화됩니다.
 * 실제 회원·데이터 저장은 back-end 연결 시 교체합니다.
 */
import { createContext, useContext, useState, type ReactNode } from 'react';

import { getVendor } from '@/data/vendors';
import type { Account, AnalysisResult, Estimate, Message, Photo, Proposal, User } from '@/types';
import { uid } from '@/utils';

type Store = {
  user: User | null;
  photos: Photo[];
  analyses: AnalysisResult[];
  messages: Message[];
  estimates: Estimate[];
  proposals: Proposal[];
  signup: (account: Account) => string | null;
  login: (loginId: string, password: string) => string | null;
  loginAsGuest: () => void;
  logout: () => void;
  updateUser: (patch: Partial<User>) => void;
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

const GUEST: User = { nickname: '게스트', loginId: 'guest', role: '유저', region: '서울', housing: '월세' };

export function AppProvider({ children }: { children: ReactNode }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [analyses, setAnalyses] = useState<AnalysisResult[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [estimates, setEstimates] = useState<Estimate[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [hiddenKeys, setHiddenKeys] = useState<string[]>([]);
  const [acceptedKeys, setAcceptedKeys] = useState<Record<string, string>>({});
  const me = user?.loginId ?? '';
  const hide = (id: string) => setHiddenKeys((prev) => [...prev, `${me}:${id}`]);

  const store: Store = {
    user,
    photos,
    analyses,
    messages,
    estimates,
    proposals,
    hidden: hiddenKeys.filter((k) => k.startsWith(`${me}:`)).map((k) => k.slice(me.length + 1)),
    signup(account) {
      if (accounts.some((a) => a.loginId === account.loginId)) return '이미 사용 중인 ID입니다.';
      setAccounts((prev) => [...prev, account]);
      const { password: _pw, ...profile } = account;
      setUser(profile);
      return null;
    },
    login(loginId, password) {
      const found = accounts.find((a) => a.loginId === loginId && a.password === password);
      if (!found) return 'ID 또는 PW가 맞지 않습니다. 처음이라면 회원가입을 해 주세요.';
      const { password: _pw, ...profile } = found;
      setUser(profile);
      return null;
    },
    loginAsGuest() {
      setUser(GUEST);
    },
    logout() {
      setUser(null);
    },
    updateUser(patch) {
      setUser((prev) => (prev ? { ...prev, ...patch } : prev));
      if (user) {
        setAccounts((prev) => prev.map((a) => (a.loginId === user.loginId ? { ...a, ...patch } : a)));
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
