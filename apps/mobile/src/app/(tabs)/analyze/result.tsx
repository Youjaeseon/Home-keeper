import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
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
import { Pressable, StyleSheet, View } from 'react-native';

import { DefectPhoto } from '@/components/defect-photo';
import { RiskLegend, RiskPhotoRing } from '@/components/risk-gauge';
import { Banner, Button, Card, CardHeader, Chip, Field, Notice, Screen, Txt } from '@/components/ui';
import { C, R, riskColor, riskLabel, STROKE } from '@/constants/theme';
import { VENDORS } from '@/data/vendors';
import { useApp } from '@/store/app-store';

/** 스케치 7: 분석 결과 — 손상 위치 원, 위험도, 원인, 해결방안, 재발방지, 업체 A~D */
export default function AnalyzeResultScreen() {
  const { analysisId } = useLocalSearchParams<{ analysisId: string }>();
  const { analyses, user, estimates, sendEstimate } = useApp();
  const [memo, setMemo] = useState('');
  const r = analyses.find((a) => a.id === analysisId);

  if (!r) {
    return (
      <Screen>
        <Txt variant="h2">분석 결과를 찾을 수 없습니다.</Txt>
        <Button title="사진 분석으로" onPress={() => router.replace('/analyze')} />
      </Screen>
    );
  }

  if (r.needsRetake) {
    return (
      <Screen>
        <DefectPhoto uri={r.photoUri} size={200} />
        <Banner
          title={r.guide.title}
          subtitle={`AI 신뢰도가 낮아(${Math.round(r.confidence * 100)}%) 결과를 확정하지 않았어요.`}
          icon={RefreshCcw}
        />
        <Card>
          <Txt variant="body">{r.cause}</Txt>
          <Txt variant="body">{r.guide.body}</Txt>
        </Card>
        <Button title="다시 촬영하기" icon={Camera} onPress={() => router.replace('/analyze')} />
      </Screen>
    );
  }

  const color = riskColor(r.risk);
  // 이 하자가 전문 분야인 업체를 '추천'으로 표시하고 위에 둡니다.
  const fits = (sp: readonly string[]) => sp.includes(r.defect);
  const vendors = [...VENDORS].sort((a, b) => Number(fits(b.specialties)) - Number(fits(a.specialties)));
  const sent = estimates.some((e) => e.analysisId === r.id && e.userId === user?.loginId);

  return (
    <Screen>
      {/* 원형 사진 + 테두리 위험도 링 (사진 위 손상 위치 원은 표시하지 않음) */}
      <RiskPhotoRing uri={r.photoUri} risk={r.risk} />

      {/* 위험도 글씨 정리 */}
      <Card style={{ alignItems: 'center', gap: 12 }}>
        <View style={{ flexDirection: 'row', gap: 6 }}>
          <Chip label={r.defect} active />
          <Chip label={r.location} />
          <Chip label={r.position} />
        </View>
        <View style={s.riskRow}>
          <Txt variant="label" muted>
            위험도
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
        <Txt variant="caption" muted>
          AI 신뢰도 {Math.round(r.confidence * 100)}%
        </Txt>
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
        {r.guide.message && (
          <View style={s.message}>
            <Txt variant="label" color={C.primary}>
              집주인에게 보낼 문자 예시
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
        {vendors.map((v) => {
          const fit = fits(v.specialties);
          return (
            <Pressable
              key={v.id}
              accessibilityRole="button"
              accessibilityLabel={`${v.name}에 문의하기`}
              onPress={() => router.push({ pathname: '/dm/[vendorId]', params: { vendorId: v.id, analysisId: r.id } })}
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
                    {v.specialties.map((sp) => (
                      <Chip key={sp} label={sp} active={sp === r.defect} />
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
        <Notice icon={MessageCircle}>업체를 누르면 분석 결과를 첨부해 견적을 문의할 수 있어요. (가상 업체)</Notice>
      </View>

      {/* 견적서: 주변 업체 회원에게 한 번에 보내기 (유저 회원만) */}
      {user?.role !== '업체' && (
        <Card>
          <CardHeader icon={FileText} title="견적서" />
          <View style={s.quote}>
            <Image source={{ uri: r.photoUri }} style={s.quotePhoto} contentFit="cover" />
            <View style={{ flex: 1, gap: 6 }}>
              <QuoteRow label="AI 위험도" value={`${r.defect} · ${r.risk}% (${riskLabel(r.risk)})`} />
              <QuoteRow label="장소" value={r.location} />
              <QuoteRow label="위치" value={r.position} />
            </View>
          </View>
          {sent ? (
            <>
              <Notice icon={CircleCheck}>주변 업체에 견적서를 보냈어요. 제안서가 오면 채팅의 제안서 탭에서 볼 수 있어요.</Notice>
              <Button
                title="받은 제안서 보기"
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
              <Button title="주변 업체에 전송" icon={Send} onPress={() => sendEstimate(r, memo.trim())} />
            </>
          )}
        </Card>
      )}
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
