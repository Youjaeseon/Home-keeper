import { router } from 'expo-router';
import { ChevronRight, Info, Phone, Star } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { AppBar, Card, Chip, Hero, Notice, Screen, Txt } from '@/components/ui';
import { C, STROKE } from '@/constants/theme';
import { messageOf } from '@/lib/api';
import { usesRealVendors } from '@/data/yongin-vendors';
import { fetchVendors } from '@/services/vendors';
import { useApp } from '@/store/app-store';
import type { Vendor } from '@/types';
import { showAlert } from '@/lib/alert';

/** 스케치 8: 업체 모음 — 업체명, 설명, 연락처 (GET /providers, 내 지역 기준 별점순). */
export default function VendorsScreen() {
  const { user } = useApp();
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [isSample, setIsSample] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!user?.regionId) return;
    fetchVendors(user.regionId, null, user.region)
      .then((res) => {
        setVendors(res.vendors);
        setIsSample(res.isSample);
        setError(null);
      })
      .catch((e) => setError(messageOf(e)));
  }, [user?.regionId, user?.region]);

  return (
    <Screen safeTop>
      <AppBar title="업체 목록" />
      <Hero title="업체 모음" subtitle={`${user?.region ?? ''} 업체 중 직접 해결이 어려울 때 견적을 문의해 보세요.`} />
      {isSample && <Notice icon={Info}>이 지역에 등록된 업체가 없어 시연용 샘플 업체를 보여 드려요. 실제 업체가 아닙니다.</Notice>}
      {error && <Notice icon={Info}>{error}</Notice>}
      {usesRealVendors(user?.region) && vendors.length === 0 && !error && (
        <Notice icon={Info}>용인시 실제 업체 정보를 준비하고 있어요.</Notice>
      )}

      {vendors.map((v) => (
        <Pressable
          key={v.id}
          accessibilityRole="button"
          accessibilityLabel={`${v.name} 문의하기`}
          onPress={() =>
            v.realListing
              ? void Linking.openURL(`tel:${v.phone.replace(/[^0-9+]/g, '')}`)
              : v.chatAvailable
                ? router.push({ pathname: '/dm/[vendorId]', params: { vendorId: v.id, name: v.name } })
                : showAlert('앱 채팅을 지원하지 않는 업체예요', v.isSample ? '시연용 샘플 업체입니다.' : `전화(${v.phone})로 문의해 주세요.`)
          }
          style={({ pressed }) => pressed && { opacity: 0.85 }}>
          <Card style={s.row}>
            <View style={s.badge}>
              <Txt variant="title">{v.label}</Txt>
            </View>
            <View style={{ flex: 1, gap: 4 }}>
              <Txt variant="h2">{v.name}</Txt>
              <Txt variant="sub" muted>
                {v.description}
              </Txt>
              <View style={s.chips}>
                {v.specialties.map((sp) => (
                  <Chip key={sp} label={sp} />
                ))}
              </View>
              <View style={s.phone}>
                {!v.realListing && <Star size={13} color={C.sub} strokeWidth={STROKE} />}
                {!v.realListing && (
                  <Txt variant="caption" muted>
                    {v.rating.toFixed(1)} ({v.reviewCount})
                  </Txt>
                )}
                <Phone size={13} color={C.sub} strokeWidth={STROKE} style={{ marginLeft: 8 }} />
                <Txt variant="caption" muted>
                  {v.phone}
                </Txt>
              </View>
              {v.realListing && (
                <Txt variant="caption" muted>
                  누르면 전화 연결 · 출처 확인 {v.realListing.checkedAt}
                </Txt>
              )}
            </View>
            <ChevronRight size={20} color={C.faint} strokeWidth={STROKE} />
          </Card>
        </Pressable>
      ))}
    </Screen>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 18 },
  badge: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: C.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
  phone: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
});
