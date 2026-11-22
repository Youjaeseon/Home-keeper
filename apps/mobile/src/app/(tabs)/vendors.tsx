import { router } from 'expo-router';
import { ChevronRight, Info, Phone } from 'lucide-react-native';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppBar, Card, Chip, Hero, Notice, Screen, Txt } from '@/components/ui';
import { C, STROKE } from '@/constants/theme';
import { VENDORS } from '@/data/vendors';

/** 스케치 8: 업체 모음 — 업체명, 설명, 연락처 */
export default function VendorsScreen() {
  return (
    <Screen safeTop>
      <AppBar title="업체 목록" />
      <Hero title="업체 모음" subtitle="직접 해결이 어려울 때 견적을 문의해 보세요." />
      <Notice icon={Info}>시뮬레이션용 가상 업체입니다. 실제 업체·연락처가 아닙니다.</Notice>

      {VENDORS.map((v) => (
        <Pressable
          key={v.id}
          accessibilityRole="button"
          accessibilityLabel={`${v.name} 문의하기`}
          onPress={() => router.push({ pathname: '/dm/[vendorId]', params: { vendorId: v.id } })}
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
                <Phone size={13} color={C.sub} strokeWidth={STROKE} />
                <Txt variant="caption" muted>
                  {v.phone}
                </Txt>
              </View>
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
