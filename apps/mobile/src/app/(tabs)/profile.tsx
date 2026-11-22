import { router } from 'expo-router';
import { ChevronRight, Clock, LogOut } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { RegionSelect } from '@/components/region-select';
import { Select } from '@/components/select';
import { AppBar, Button, Card, CardHeader, Chip, DeleteButton, Field, Screen, Txt } from '@/components/ui';
import { C, STROKE } from '@/constants/theme';
import { HOUSINGS } from '@/data/options';
import { confirmAlert, showAlert } from '@/lib/alert';
import { useApp } from '@/store/app-store';

/** 스케치 3: 사용자 정보 — 회원 유형(유저/업체), 별명, 거주지역, 거주형태 */
export default function ProfileScreen() {
  const { user, regions, updateUser, logout, analyses, removeAnalysis } = useApp();
  const [nickname, setNickname] = useState(user?.nickname ?? '');
  const [savedNickname, setSavedNickname] = useState(user?.nickname ?? '');
  const [error, setError] = useState<string | null>(null);
  // 서버에 저장된 닉네임이 바뀌면 입력칸도 맞춥니다.
  if ((user?.nickname ?? '') !== savedNickname) {
    setSavedNickname(user?.nickname ?? '');
    setNickname(user?.nickname ?? '');
  }
  if (!user) return null;

  const save = async (patch: Parameters<typeof updateUser>[0]) => setError(await updateUser(patch));

  const vendor = user.role === '업체';

  return (
    <Screen safeTop>
      <AppBar title="프로필" />

      <View style={s.profile}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Txt variant="title">{user.nickname}</Txt>
          <Chip label={user.role} active={vendor} />
        </View>
        <Txt variant="sub" muted>
          {vendor ? `${user.region} · 견적 요청서를 받는 업체` : `${user.region} · ${user.housing}`}
        </Txt>
      </View>

      <Card>
        {/* 회원 유형은 서버가 정합니다(가입 시 유저, 업체는 사전 등록). TODO(integration-gap): GAP-003 */}
        <Field label="회원 유형" value={user.role} editable={false} />
        <Field
          label={vendor ? '업체명' : '별명'}
          value={nickname}
          onChangeText={setNickname}
          onEndEditing={() => nickname.trim() !== user.nickname && save({ nickname })}
          onSubmitEditing={() => nickname.trim() !== user.nickname && save({ nickname })}
        />
        <RegionSelect
          label={vendor ? '활동지역' : '거주지역'}
          regions={regions}
          value={user.region}
          onChange={(region) => save({ region })}
        />
        {vendor ? (
          // TODO(integration-gap): GAP-010 업체 소개 수정 API가 없어 표시만 합니다.
          <Field label="업체 소개" value={user.intro ?? ''} editable={false} placeholder="업체 소개는 운영팀이 등록합니다" />
        ) : (
          <Select label="거주형태" value={user.housing} options={HOUSINGS} onChange={(housing) => save({ housing })} />
        )}
        {error && (
          <Txt variant="sub" color={C.danger}>
            {error}
          </Txt>
        )}
      </Card>

      {analyses.length > 0 && (
        <Card style={{ gap: 4 }}>
          <CardHeader icon={Clock} title="내 분석 기록" />
          {analyses.map((a) => (
            // 웹에서 <button> 안에 <button>이 들어가지 않도록 삭제 버튼은 행 버튼 밖에 둡니다.
            <View key={a.id} style={s.historyRow}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${a.location} 분석 결과 보기`}
                onPress={() => router.push({ pathname: '/analyze/result', params: { analysisId: a.id } })}
                style={({ pressed }) => [s.historyMain, pressed && { opacity: 0.7 }]}>
                <View style={{ flex: 1 }}>
                  <Txt variant="bodyStrong">
                    {a.location} · {a.defect}
                  </Txt>
                  <Txt variant="caption" muted>
                    {a.occurredAt}
                    {a.needsRetake ? ' · 재촬영 필요' : ` · 심각도 ${a.risk}%`}
                  </Txt>
                </View>
              </Pressable>
              <DeleteButton
                label="분석 기록"
                onDelete={() =>
                  void confirmAlert(
                    '분석 기록을 지울까요?',
                    '사진과 이 기록으로 보낸 견적 요청서·받은 업체 제안서도 함께 지워지고 되돌릴 수 없어요.',
                    '삭제',
                  ).then(async (ok) => {
                    if (!ok) return;
                    const err = await removeAnalysis(a.id);
                    if (err) showAlert('삭제하지 못했어요', err);
                  })
                }
              />
              <ChevronRight size={18} color={C.faint} strokeWidth={STROKE} />
            </View>
          ))}
        </Card>
      )}

      <Button
        title="로그아웃"
        variant="outline"
        icon={LogOut}
        style={{ marginTop: 8 }}
        onPress={async () => {
          await logout();
          router.replace('/');
        }}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  profile: { gap: 6, paddingVertical: 12 },
  historyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: 58,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  historyMain: { flex: 1, flexDirection: 'row', alignItems: 'center', alignSelf: 'stretch' },
});
