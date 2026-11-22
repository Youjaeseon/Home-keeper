import { Droplets, PaintRoller, SprayCan } from 'lucide-react-native';
import { StyleSheet, View } from 'react-native';

import { Txt } from '@/components/ui';
import { C, STROKE } from '@/constants/theme';
import type { Vendor } from '@/types';

/** 실제 업체는 주 분야 아이콘, 그 밖의 업체(테스트·가상)는 기존처럼 A·B 글자를 보여 줍니다. */
const KINDS = {
  mold: { Icon: SprayCan, bg: '#DDEBD7', fg: '#3F6B3A' }, // 곰팡이 제거: 분무기
  paint: { Icon: PaintRoller, bg: '#F6E2CC', fg: '#8A5A2B' }, // 벽지·도장: 페인트 롤러
  water: { Icon: Droplets, bg: '#DCE8F0', fg: '#36607A' }, // 누수·방수·균열: 물방울
} as const;

function kindOf(v: Vendor): keyof typeof KINDS {
  if (v.specialties.includes('곰팡이 제거')) return 'mold';
  if (v.specialties.includes('벽지·도장 보수')) return 'paint';
  return 'water';
}

export function VendorBadge({ vendor }: { vendor: Vendor }) {
  if (!vendor.realListing) {
    return (
      <View style={[s.badge, { backgroundColor: C.accent }]}>
        <Txt variant="title">{vendor.label}</Txt>
      </View>
    );
  }
  const { Icon, bg, fg } = KINDS[kindOf(vendor)];
  return (
    <View style={[s.badge, { backgroundColor: bg }]} accessibilityElementsHidden importantForAccessibility="no">
      <Icon size={26} color={fg} strokeWidth={STROKE} />
    </View>
  );
}

const s = StyleSheet.create({
  badge: { width: 54, height: 54, borderRadius: 27, alignItems: 'center', justifyContent: 'center' },
});
