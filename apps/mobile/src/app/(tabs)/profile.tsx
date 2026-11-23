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
  const { user, regions, updateUser, logout, analyses, removeAnalysis, refreshAnalyses } = useApp();
  const [nickname, setNickname] = useState(user?.nickname ?? '');
  const [savedNickname, setSavedNickname] = useState(user?.nickname ?? '');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // 거주지역·거주형태도 고른 값을 잠시 들고 있다가 '저장'을 누를 때 함께 저장합니다.
  const [region, setRegion] = useState(user?.region ?? '');
  const [housing, setHousing] = useState(user?.housing ?? '월세');
  const [savedKey, setSavedKey] = useState(`${user?.region}|${user?.housing}`);
  // 서버에 저장된 값이 바뀌면 입력칸도 맞춥니다.
  if ((user?.nickname ?? '') !== savedNickname) {
    setSavedNickname(user?.nickname ?? '');
    setNickname(user?.nickname ?? '');
  }
  if (`${user?.region}|${user?.housing}` !== savedKey) {
    setSavedKey(`${user?.region}|${user?.housing}`);
    setRegion(user?.region ?? '');
    setHousing(user?.housing ?? '월세');
  }
  if (!user) return null;

  // 별명·거주지역·거주형태는 정보 칸 아래 '저장' 버튼(또는 키보드 완료)으로 한 번에 서버에 저장합니다. 별명 최대 8글자.
  const NICK_MAX = 8;
  const trimmed = nickname.trim();
  const changed = trimmed !== user.nickname || region !== user.region || housing !== user.housing;
  const saveNickname = async () => {
    if (!changed || saving) return;
    if (!trimmed) return setError('별명을 입력해 주세요.');
    if (trimmed.length > NICK_MAX) return setError(`별명은 최대 ${NICK_MAX}글자까지 쓸 수 있어요.`);
    setSaving(true);
    const err = await updateUser({ nickname: trimmed, region, housing });
    setSaving(false);
    setError(err);
    if (!err) showAlert('저장했어요', '프로필이 저장됐어요.');
  };

  const vendor = user.role === '업체';

  return (
    <Screen safeTop onRefresh={refreshAnalyses}>
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
          maxLength={NICK_MAX}
          onSubmitEditing={() => void saveNickname()}
        />
        <RegionSelect
          label={vendor ? '활동지역' : '거주지역'}
          regions={regions}
          value={region}
          onChange={setRegion}
        />
        {vendor ? (
          // TODO(integration-gap): GAP-010 업체 소개 수정 API가 없어 표시만 합니다.
          <Field label="업체 소개" value={user.intro ?? ''} editable={false} placeholder="업체 소개는 운영팀이 등록합니다" />
        ) : (
          <Select label="거주형태" value={housing} options={HOUSINGS} onChange={setHousing} />
        )}
        {error && (
          <Txt variant="sub" color={C.danger}>
            {error}
          </Txt>
        )}
        {/* 별명·거주지역·거주형태를 이 버튼으로 서버에 저장합니다(바꾼 것이 있을 때만 눌림). */}
        <Button title="저장" onPress={() => void saveNickname()} disabled={!changed} loading={saving} />
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
