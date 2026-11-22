import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  Camera,
  ChevronRight,
  CircleCheck,
  FileText,
  House,
  MessageCircle,
  Phone,
  RefreshCcw,
  Search,
  Send,
  ShieldCheck,
  Wrench,
} from 'lucide-react-native';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { DefectPhoto } from '@/components/defect-photo';
import { RiskLegend, RiskPhotoRing } from '@/components/risk-gauge';
import { Banner, Button, Card, CardHeader, Chip, Field, Notice, Screen, Txt } from '@/components/ui';
import { C, R, riskColor, riskLabel, STROKE } from '@/constants/theme';
import { messageOf, regenerateDiagnosis } from '@/lib/api';
import { fetchVendors } from '@/services/vendors';
import type { Vendor } from '@/types';
import { useApp } from '@/store/app-store';
import { showAlert } from '@/lib/alert';

const ACTION_LABEL = {
  self_care: '직접 관리',
  inspection: '점검 받기',
  provider_consult: '업체 상담',
} as const;

/** 스케치 7: 분석 결과 — 손상 위치 원, 심각도, 원인, 해결방안, 재발방지, 업체 A~D */
export default function AnalyzeResultScreen() {
  const { analysisId } = useLocalSearchParams<{ analysisId: string }>();
  const { analyses, user, estimates, sendEstimate, loadAnalysis, makeLandlordDraft } = useApp();
  const [memo, setMemo] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [vendorList, setVendorList] = useState<{ vendors: Vendor[]; isSample: boolean }>({ vendors: [], isSample: false });
  const [sending, setSending] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const r = analyses.find((a) => a.id === analysisId);
  const workTypeId = r?.workTypeId;

  // 화면에 들어올 때마다 최신 결과(새 사진 Signed URL 포함)를 다시 받습니다.
  useEffect(() => {
    if (!analysisId) return;
    loadAnalysis(analysisId).then((err) => {
      setLoadError(err);
      setLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId]);

  useEffect(() => {
    if (!user?.regionId || loading) return;
    fetchVendors(user.regionId, workTypeId)
      .then(setVendorList)
      .catch(() => setVendorList({ vendors: [], isSample: false }));
  }, [user?.regionId, workTypeId, loading]);

  if (!r || (loading && !r.cause)) {
    if (loading) {
      return (
        <Screen>
          <ActivityIndicator />
        </Screen>
      );
    }
    return (
      <Screen>
        <Txt variant="h2">{loadError ?? '분석 결과를 찾을 수 없습니다.'}</Txt>
        <Button title="사진 분석으로" onPress={() => router.replace('/analyze')} />
      </Screen>
    );
  }

  // 같은 입력으로 진단을 다시 만듭니다(POST /records/{id}/diagnosis?regenerate=true). (GAP-029)
  const onRegenerate = async () => {
    setRegenerating(true);
    try {
      await regenerateDiagnosis(r.id, true);
      const err = await loadAnalysis(r.id);
      if (err) showAlert('새 진단을 불러오지 못했습니다', err);
    } catch (e) {
      showAlert('진단을 다시 만들지 못했습니다', messageOf(e));
    } finally {
      setRegenerating(false);
    }
  };
  const regenerateButton = (
    <Button title="진단 다시 만들기" icon={RefreshCcw} variant="soft" onPress={onRegenerate} loading={regenerating} />
  );

  if (r.needsRetake) {
    return (
      <Screen>
        <DefectPhoto uri={r.photoUri} size={200} />
        <Banner
          title={r.guide.title}
          subtitle="사진·입력만으로는 근거가 부족해 판단을 보류했어요."

          icon={RefreshCcw}
        />
        <Card>
          <Txt variant="body">{r.cause}</Txt>
          <Txt variant="body">{r.guide.body}</Txt>
        </Card>
        <Button title="다시 촬영하기" icon={Camera} onPress={() => router.replace('/analyze')} />
        {regenerateButton}
      </Screen>
    );
  }

  const color = riskColor(r.risk);
  // 이 하자가 전문 분야인 업체를 '추천'으로 표시하고 위에 둡니다.
  // 진단이 추천한 작업 종류가 특화 분야인 업체를 '추천'으로 표시합니다. (서버가 이미 별점순 정렬)
  const fits = (v: Vendor) => !!r.workTypeId && v.specialtyIds.includes(r.workTypeId);
  const vendors = [...vendorList.vendors].sort((a, b) => Number(fits(b)) - Number(fits(a)));
  const sent = estimates.some((e) => e.analysisId === r.id && e.status !== 'cancelled' && user?.role !== '업체');

  const onSendEstimate = async () => {
    setSending(true);
    const err = await sendEstimate(r, memo.trim());
    setSending(false);
    if (err) showAlert('견적 요청서를 보내지 못했습니다', err);
  };

  return (
    <Screen>
      {/* 원형 사진 + 테두리 심각도 링 (사진 위 손상 위치 원은 표시하지 않음) */}
      <RiskPhotoRing uri={r.photoUri} risk={r.risk} />

      {/* 심각도 글씨 정리 */}
      <Card style={{ alignItems: 'center', gap: 12 }}>
        <View style={{ flexDirection: 'row', gap: 6 }}>
          <Chip label={r.defect} active />
          <Chip label={r.location} />
          {!!r.position && <Chip label={r.position} />}
        </View>
        <View style={s.riskRow}>
          <Txt variant="label" muted>
            심각도
          </Txt>
          <Txt variant="display" color={color} style={{ fontSize: 34, lineHeight: 40 }}>
            {r.risk}%
          </Txt>
          <View style={[s.riskBadge, { backgroundColor: color }]}>
            <Txt variant="label" color={C.onPrimary}>
              {riskLabel(r.risk)}
            </Txt>
          </View>
        </View>
        <RiskLegend />
        {!!r.recommendedAction && (
          <Txt variant="sub" color={C.text}>
            권장 대응: {ACTION_LABEL[r.recommendedAction]}
          </Txt>
        )}
        {!!r.estimationNotice && (
          <Txt variant="caption" muted style={{ textAlign: 'center' }}>
            {r.estimationNotice}
          </Txt>
        )}
        {regenerateButton}
      </Card>

      <Card>
        <CardHeader icon={Search} title="원인" />
        <Txt variant="body">{r.cause}</Txt>
      </Card>

      <Card>
        <CardHeader icon={Wrench} title="해결 방안" />
        {r.solutions.map((t, i) => (
          <View key={i} style={s.listRow}>
            <View style={s.num}>
              <Txt variant="caption" color={C.primary}>
                {i + 1}
              </Txt>
            </View>
            <Txt variant="body" style={{ flex: 1 }}>
              {t}
            </Txt>
          </View>
        ))}
      </Card>

      <Card>
        <CardHeader icon={ShieldCheck} title="재발 방지" />
        {r.prevention.map((t, i) => (
          <View key={i} style={s.listRow}>
            <CircleCheck size={18} color={C.primary} strokeWidth={STROKE} style={{ marginTop: 2 }} />
            <Txt variant="body" style={{ flex: 1 }}>
              {t}
            </Txt>
          </View>
        ))}
      </Card>

      {/* 거주형태별 대응 안내 */}
      <View style={s.guide}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={s.guideIcon}>
            <House size={18} color={C.text} strokeWidth={STROKE} />
          </View>
          <Txt variant="h2" style={{ flex: 1 }}>
            {r.guide.title}
          </Txt>
        </View>
        {r.guide.body !== '' && (
          <Txt variant="sub" color={C.text}>
            {r.guide.body}
          </Txt>
        )}
        {r.guide.steps?.map((st, i) => (
          <View key={i} style={s.listRow}>
            <View style={[s.num, { backgroundColor: C.accentCircle }]}>
              <Txt variant="caption" color={C.primary}>
                {i + 1}
              </Txt>
            </View>
            <View style={{ flex: 1, gap: 3 }}>
              <Txt variant="bodyStrong">{st.title}</Txt>
              <Txt variant="sub" color={C.text}>
                {st.desc}
              </Txt>
            </View>
          </View>
        ))}
        {/* 세입자에게만 집주인 문자를 만들 수 있게 합니다. 누를 때만 모델을 부릅니다. */}
        {!r.guide.message && ['월세', '전세', '반전세'].includes(r.housing) && user?.role !== '업체' && (
          <Button
            title="집주인에게 보낼 문자 만들기"
            icon={MessageCircle}
            variant="soft"
            loading={drafting}
            onPress={async () => {
              setDrafting(true);
              const err = await makeLandlordDraft(r.id);
              setDrafting(false);
              if (err) showAlert('문자를 만들지 못했습니다', err);
            }}
          />
        )}
        {r.guide.message && (
          <View style={s.message}>
            <Txt variant="label" color={C.primary}>
              집주인에게 보낼 문자
            </Txt>
            <Txt variant="body" selectable>
              {r.guide.message}
            </Txt>
          </View>
        )}
        <Txt variant="caption" color={C.text} style={{ opacity: 0.7 }}>
          참고용 안내이며 법률 자문이 아닙니다.
        </Txt>
      </View>

      {/* 업체는 필요할 때만 */}
      <View style={{ gap: 12, marginTop: 8 }}>
        <Txt variant="title">직접 해결이 어렵다면</Txt>
        {/* 견적 요청서: 주변 업체 회원에게 한 번에 보내기 (유저 회원만) */}
        {user?.role !== '업체' && (
          <Card>
            <CardHeader icon={FileText} title="견적 요청서" />
            <View style={s.quote}>
              <Image source={{ uri: r.photoUri }} style={s.quotePhoto} contentFit="cover" />
              <View style={{ flex: 1, gap: 6 }}>
                <QuoteRow label="AI 심각도" value={`${r.defect} · ${r.risk}% (${riskLabel(r.risk)})`} />
                <QuoteRow label="장소" value={r.location} />
                {!!r.position && <QuoteRow label="위치" value={r.position} />}
              </View>
            </View>
            {sent ? (
              <>
                <Notice icon={CircleCheck}>주변 업체에 견적 요청서를 보냈어요. 업체 제안서가 오면 채팅의 업체 제안서 탭에서 볼 수 있어요.</Notice>
                <Button
                  title="받은 업체 제안서 보기"
                  variant="outline"
                  onPress={() => router.push({ pathname: '/dm', params: { tab: 'quotes' } })}
                />
              </>
            ) : (
              <>
                <Field
                  label="추가 메모"
                  value={memo}
                  onChangeText={setMemo}
                  placeholder="예: 평일 저녁 방문 가능해요"
                  multiline
                  style={{ minHeight: 76, paddingTop: 14, textAlignVertical: 'top' }}
                />
                <Button title="주변 업체에 전송" icon={Send} onPress={onSendEstimate} loading={sending} />
              </>
            )}
          </Card>
        )}
        {vendors.map((v) => {
          const fit = fits(v);
          return (
            <Pressable
              key={v.id}
              accessibilityRole="button"
              accessibilityLabel={`${v.name}에 문의하기`}
              onPress={() =>
                v.chatAvailable
                  ? router.push({ pathname: '/dm/[vendorId]', params: { vendorId: v.id, analysisId: r.id, name: v.name } })
                  : showAlert('앱 채팅을 지원하지 않는 업체예요', v.isSample ? '시연용 샘플 업체입니다.' : `전화(${v.phone})로 문의해 주세요.`)
              }
              style={({ pressed }) => pressed && { opacity: 0.85 }}>
              <Card style={[s.vendor, fit && s.vendorFit]}>
                <View style={s.vendorBadge}>
                  <Txt variant="title">{v.label}</Txt>
                </View>
                <View style={{ flex: 1, gap: 4 }}>
                  {fit && (
                    <View style={s.rank}>
                      <Txt variant="caption" color={C.onPrimary}>
                        추천
                      </Txt>
                    </View>
                  )}
                  <Txt variant="h2">{v.name}</Txt>
                  <Txt variant="sub" muted>
                    {v.description}
                  </Txt>
                  <View style={s.chips}>
                    {v.specialties.map((sp, i) => (
                      <Chip key={sp} label={sp} active={v.specialtyIds[i] === r.workTypeId} />
                    ))}
                  </View>
                  <View style={s.phone}>
                    <Phone size={13} color={C.sub} strokeWidth={STROKE} />
                    <Txt variant="caption" muted>
                      {v.phone}
                    </Txt>
                  </View>
                </View>
                <ChevronRight size={20} color={C.faint} strokeWidth={STROKE} />
              </Card>
            </Pressable>
          );
        })}
        <Notice icon={MessageCircle}>
          {vendorList.isSample
            ? '이 지역에 등록된 업체가 없어 시연용 샘플 업체를 보여 드려요. 샘플 업체와는 채팅할 수 없어요.'
            : '업체를 누르면 분석 결과를 첨부해 견적을 문의할 수 있어요.'}
        </Notice>
      </View>
    </Screen>
  );
}

function QuoteRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      <Txt variant="caption" muted style={{ width: 62 }}>
        {label}
      </Txt>
      <Txt variant="sub" color={C.text} style={{ flex: 1 }}>
        {value}
      </Txt>
    </View>
  );
}

const s = StyleSheet.create({
  guide: { backgroundColor: C.accent, borderRadius: R.card, padding: 22, gap: 12 },
  guideIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: C.accentCircle,
    alignItems: 'center',
    justifyContent: 'center',
  },
  message: { backgroundColor: C.card, borderRadius: 20, padding: 16, gap: 6 },
  quote: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  quotePhoto: { width: 84, height: 84, borderRadius: 20, backgroundColor: C.accent },
  listRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  riskRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  riskBadge: { borderRadius: 999, paddingHorizontal: 12, paddingVertical: 4 },
  num: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: C.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  vendor: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 18, borderWidth: 2, borderColor: C.card },
  vendorFit: { borderColor: C.primary },
  vendorBadge: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: C.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rank: {
    alignSelf: 'flex-start',
    backgroundColor: C.primary,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
  phone: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
});
