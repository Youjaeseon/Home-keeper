import { router } from 'expo-router';
import { Check } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Select } from '@/components/select';
import { Button, Card, Field, Hero, Screen, Txt } from '@/components/ui';
import { C, F } from '@/constants/theme';
import { HOUSINGS, REGIONS } from '@/data/options';
import { useApp } from '@/store/app-store';
import type { Housing, Role } from '@/types';

const ROLES: { role: Role; desc: string }[] = [
  { role: '유저', desc: '하자를 진단하고 견적을 요청해요' },
  { role: '업체', desc: '견적서를 받고 제안서를 보내요' },
];

/** 스케치 2: 회원가입 (회원 유형, 닉네임, ID, PW, 거주지역, 거주형태, 사진 분석 동의) */
export default function SignupScreen() {
  const { signup } = useApp();
  const [role, setRole] = useState<Role>('유저');
  const [nickname, setNickname] = useState('');
  const [intro, setIntro] = useState('');
  const [agreed, setAgreed] = useState(false);
  const vendor = role === '업체';
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [region, setRegion] = useState(REGIONS[0]);
  const [housing, setHousing] = useState<Housing>('월세');
  const [error, setError] = useState<string | null>(null);

  const onSubmit = () => {
    if (!nickname.trim() || !loginId.trim() || password.length < 4) {
      setError(`${vendor ? '업체명' : '닉네임'}, ID를 입력하고 PW는 4자 이상으로 정해 주세요.`);
      return;
    }
    if (!agreed) {
      setError('사진 분석 동의에 체크해 주세요.');
      return;
    }
    const err = signup({
      role,
      nickname: nickname.trim(),
      loginId: loginId.trim(),
      password,
      region,
      housing: vendor ? '기타' : housing,
      intro: vendor ? intro.trim() : undefined,
    });
    setError(err);
    if (!err) router.replace('/news');
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
          placeholder={vendor ? '예: 집사 곰팡이케어' : '예: 집사'}
        />
        <Field label="ID" value={loginId} onChangeText={setLoginId} autoCapitalize="none" placeholder="아이디" />
        <Field label="PW" value={password} onChangeText={setPassword} secureTextEntry placeholder="4자 이상" />
      </Card>

      <Card>
        <Select label={vendor ? '활동지역' : '거주지역'} value={region} options={REGIONS} onChange={setRegion} />
        {vendor ? (
          <Field label="업체 소개" value={intro} onChangeText={setIntro} placeholder="예: 욕실 곰팡이 제거 전문" />
        ) : (
          <Select label="거주형태" value={housing} options={HOUSINGS} onChange={setHousing} />
        )}
      </Card>

      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: agreed }}
        accessibilityLabel="사진 분석 동의"
        onPress={() => setAgreed((v) => !v)}
        style={s.agree}>
        <View style={[s.box, agreed && s.boxOn]}>{agreed && <Check size={15} color={C.onPrimary} strokeWidth={3} />}</View>
        <Txt variant="sub" color={C.text} style={{ flex: 1 }}>
          <Txt variant="sub" color={C.primary} style={{ fontFamily: F.bold }}>
            [필수]{' '}
          </Txt>
          첨부한 사진이 하자 분석을 위해 AI(LLM)로 전송되는 것에 동의합니다.
        </Txt>
      </Pressable>
      {error && (
        <Txt variant="sub" color={C.danger}>
          {error}
        </Txt>
      )}
      <Button title="가입 완료" onPress={onSubmit} />
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
  agree: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 4 },
  box: {
    width: 24,
    height: 24,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: C.faint,
    backgroundColor: C.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxOn: { backgroundColor: C.primary, borderColor: C.primary },
});
