import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { RegionSelect } from '@/components/region-select';
import { Select } from '@/components/select';
import { Button, Card, Field, Hero, Screen, Txt } from '@/components/ui';
import { C } from '@/constants/theme';
import { HOUSINGS, REGIONS } from '@/data/options';
import { regionName } from '@/lib/adapters';
import { getPublicRegions, type Region } from '@/lib/api';
import { useApp } from '@/store/app-store';
import type { Housing, Role } from '@/types';

const ROLES: { role: Role; desc: string }[] = [
  { role: '유저', desc: '하자를 진단하고 견적을 요청해요' },
  { role: '업체', desc: '지역의 견적 요청서를 받고 제안서를 보내요' },
];

/**
 * 스케치 2: 회원가입 (회원 유형, 닉네임/업체명, ID, PW, 지역, 거주형태 또는 업체 연락처·소개)
 * - 업체로 가입하면 업체 정보와 활동 지역이 등록되고, 그 지역의 견적 요청서를 모두 받습니다. (GAP-003, Hyeok 결정)
 * - 외부 AI 사진 전송 동의는 가입 때가 아니라 분석 요청마다 받습니다. (GAP-011)
 */
export default function SignupScreen() {
  const { signup } = useApp();
  const [role, setRole] = useState<Role>('유저');
  const vendor = role === '업체';
  const [nickname, setNickname] = useState('');
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [intro, setIntro] = useState('');
  // 지역 목록은 공개 API(GET /regions)에서 받습니다. 실패하면 기본 시연 지역을 씁니다. (GAP-004)
  const [regionList, setRegionList] = useState<Region[]>([]);
  const [region, setRegion] = useState(REGIONS[0]);
  useEffect(() => {
    getPublicRegions()
      .then((list) => {
        if (list.length === 0) return;
        setRegionList(list);
        const names = list.map(regionName);
        setRegion((prev) => (names.includes(prev) ? prev : (names.find((n) => n.includes('용인')) ?? names[0])));
      })
      .catch(() => null);
  }, []);
  const [housing, setHousing] = useState<Housing>('월세');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    if (busy) return;
    // Supabase Auth는 이메일을 ID로 쓰고 PW는 기본 6자 이상입니다.
    if (!nickname.trim() || !loginId.trim() || password.length < 6) {
      setError(`${vendor ? '업체명' : '닉네임'}, ID(이메일)를 입력하고 PW는 6자 이상으로 정해 주세요.`);
      return;
    }
    if (!/^\S+@\S+\.\S+$/.test(loginId.trim())) {
      setError('ID는 이메일 주소로 입력해 주세요.');
      return;
    }
    if (vendor && phone.replace(/[^0-9]/g, '').length < 7) {
      setError('업체 연락처를 입력해 주세요.');
      return;
    }
    setBusy(true);
    const err = await signup({
      role,
      nickname: nickname.trim(),
      loginId: loginId.trim(),
      password,
      region,
      housing: vendor ? '기타' : housing,
      intro: vendor ? intro.trim() : undefined,
      phone: vendor ? phone.trim() : undefined,
    });
    setBusy(false);
    setError(err);
    // 성공하면 로그인 화면의 세션 가드가 소식지 또는 프로필 등록으로 이동시킵니다.
    if (!err) router.replace('/');
  };

  return (
    <Screen>
      <Hero title="회원가입" subtitle="거주 정보에 맞춰 소식과 하자 대응 방법을 알려 드려요." />

      <View style={s.roles}>
        {ROLES.map(({ role: r, desc }) => {
          const on = r === role;
          return (
            <Pressable
              key={r}
              accessibilityRole="radio"
              accessibilityState={{ selected: on }}
              accessibilityLabel={`${r}로 가입`}
              onPress={() => setRole(r)}
              style={[s.role, on && s.roleOn]}>
              <Txt variant="h2" color={on ? C.primary : C.text}>
                {r}
              </Txt>
              <Txt variant="caption" muted>
                {desc}
              </Txt>
            </Pressable>
          );
        })}
      </View>

      <Card>
        <Field
          label={vendor ? '업체명' : '닉네임'}
          value={nickname}
          onChangeText={setNickname}
          placeholder={vendor ? '예: 용인 하자케어' : '예: 집사'}
        />
        <Field
          label="ID"
          value={loginId}
          onChangeText={setLoginId}
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="이메일"
        />
        <Field label="PW" value={password} onChangeText={setPassword} secureTextEntry placeholder="6자 이상" />
      </Card>

      <Card>
        {regionList.length > 0 ? (
          <RegionSelect label={vendor ? '활동지역' : '거주지역'} regions={regionList} value={region} onChange={setRegion} />
        ) : (
          <Select label={vendor ? '활동지역' : '거주지역'} value={region} options={REGIONS} onChange={setRegion} />
        )}
        {vendor ? (
          <>
            <Field
              label="업체 연락처"
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
              placeholder="예: 031-000-0000"
            />
            <Field label="업체 소개" value={intro} onChangeText={setIntro} placeholder="예: 욕실 곰팡이 제거 전문" />
            <Txt variant="caption" muted>
              활동지역의 견적 요청서를 모두 받아 볼 수 있어요.
            </Txt>
          </>
        ) : (
          <Select label="거주형태" value={housing} options={HOUSINGS} onChange={setHousing} />
        )}
      </Card>

      {error && (
        <Txt variant="sub" color={C.danger}>
          {error}
        </Txt>
      )}
      <Button title="가입 완료" onPress={onSubmit} loading={busy} />
    </Screen>
  );
}

const s = StyleSheet.create({
  roles: { flexDirection: 'row', gap: 10 },
  role: {
    flex: 1,
    gap: 4,
    padding: 16,
    borderRadius: 24,
    backgroundColor: C.card,
    borderWidth: 2,
    borderColor: C.card,
  },
  roleOn: { borderColor: C.primary },
});
