import { Redirect, router } from 'expo-router';
import { useState } from 'react';

import { Select } from '@/components/select';
import { Button, Card, Field, Hero, Notice, Screen, Txt } from '@/components/ui';
import { C } from '@/constants/theme';
import { HOUSINGS } from '@/data/options';
import { matchRegion } from '@/lib/adapters';
import { useApp } from '@/store/app-store';
import type { Housing } from '@/types';
import { Info } from 'lucide-react-native';

/**
 * 프로필 등록: 로그인은 됐지만 GET /me/profile이 404일 때(둘러보기 포함),
 * 또는 가입 직후 프로필 저장이 실패했을 때 같은 계정으로 저장만 다시 시도합니다.
 * 팀원 회원가입 화면의 입력칸 구성을 그대로 따릅니다.
 */
export default function ProfileSetupScreen() {
  const { ready, session, user, regions, pendingProfile, saveProfile, logout } = useApp();
  const names = regions.map((r) => r.display_name);
  const preset = pendingProfile ? matchRegion(pendingProfile.region, regions) : null;
  const [nickname, setNickname] = useState(pendingProfile?.nickname ?? '');
  const [region, setRegion] = useState(preset?.display_name ?? names[0] ?? '');
  const [housing, setHousing] = useState<Housing>(pendingProfile?.housing ?? '월세');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (ready && !session) return <Redirect href="/" />;
  if (user) return <Redirect href="/news" />;

  const onSubmit = async () => {
    const target = regions.find((r) => r.display_name === region);
    if (!nickname.trim() || !target) {
      setError('닉네임과 거주지역을 입력해 주세요.');
      return;
    }
    setBusy(true);
    const err = await saveProfile({ nickname, regionId: target.region_id, housing });
    setBusy(false);
    setError(err);
    if (!err) router.replace('/news');
  };

  return (
    <Screen>
      <Hero title="프로필 등록" subtitle="거주 정보에 맞춰 소식과 하자 대응 방법을 알려 드려요." />
      {pendingProfile?.notice && <Notice icon={Info}>{pendingProfile.notice}</Notice>}
      <Card>
        <Field label="닉네임" value={nickname} onChangeText={setNickname} placeholder="예: 집사" />
        {names.length > 0 ? (
          <Select label="거주지역" value={region} options={names} onChange={setRegion} />
        ) : (
          <Txt variant="sub" color={C.danger}>
            서버에서 지역 목록을 불러오지 못했습니다.
          </Txt>
        )}
        <Select label="거주형태" value={housing} options={HOUSINGS} onChange={setHousing} />
      </Card>
      {error && (
        <Txt variant="sub" color={C.danger}>
          {error}
        </Txt>
      )}
      <Button title="저장" onPress={onSubmit} loading={busy} />
      <Button
        title="로그아웃"
        variant="outline"
        onPress={async () => {
          await logout();
          router.replace('/');
        }}
      />
    </Screen>
  );
}
