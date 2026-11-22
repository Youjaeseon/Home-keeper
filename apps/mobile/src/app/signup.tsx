import { router } from 'expo-router';
import { useEffect, useState } from 'react';

import { Select } from '@/components/select';
import { Button, Card, Field, Hero, Screen, Txt } from '@/components/ui';
import { C } from '@/constants/theme';
import { HOUSINGS, REGIONS } from '@/data/options';
import { regionName } from '@/lib/adapters';
import { getPublicRegions } from '@/lib/api';
import { useApp } from '@/store/app-store';
import type { Housing } from '@/types';

/**
 * 스케치 2: 회원가입 (닉네임, ID, PW, 거주지역, 거주형태)
 * - 일반 가입은 요청인(유저) 전용입니다. 업체는 사전 등록 계정으로만 로그인합니다. (GAP-003)
 * - 외부 AI 사진 전송 동의는 가입 때가 아니라 분석 요청마다 받습니다. (GAP-011)
 */
export default function SignupScreen() {
  const { signup } = useApp();
  const [nickname, setNickname] = useState('');
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  // 지역 목록은 공개 API(GET /regions)에서 받습니다. 실패하면 기본 시연 지역을 씁니다. (GAP-004)
  const [regionOptions, setRegionOptions] = useState<string[]>(REGIONS);
  const [region, setRegion] = useState(REGIONS[0]);
  useEffect(() => {
    getPublicRegions()
      .then((list) => {
        const names = list.map(regionName);
        if (names.length === 0) return;
        setRegionOptions(names);
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
      setError('닉네임, ID(이메일)를 입력하고 PW는 6자 이상으로 정해 주세요.');
      return;
    }
    if (!/^\S+@\S+\.\S+$/.test(loginId.trim())) {
      setError('ID는 이메일 주소로 입력해 주세요.');
      return;
    }
    setBusy(true);
    const err = await signup({
      role: '유저',
      nickname: nickname.trim(),
      loginId: loginId.trim(),
      password,
      region,
      housing,
    });
    setBusy(false);
    setError(err);
    // 성공하면 로그인 화면의 세션 가드가 소식지 또는 프로필 등록으로 이동시킵니다.
    if (!err) router.replace('/');
  };

  return (
    <Screen>
      <Hero title="회원가입" subtitle="거주 정보에 맞춰 소식과 하자 대응 방법을 알려 드려요." />

      <Card>
        <Field label="닉네임" value={nickname} onChangeText={setNickname} placeholder="예: 집사" />
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
        <Select label="거주지역" value={region} options={regionOptions} onChange={setRegion} />
        <Select label="거주형태" value={housing} options={HOUSINGS} onChange={setHousing} />
        <Txt variant="caption" muted>
          업체 회원은 운영팀이 미리 등록한 계정으로 로그인해 주세요.
        </Txt>
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
