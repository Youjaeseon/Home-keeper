import { Image } from 'expo-image';
import { StyleSheet, View } from 'react-native';

import { C, R } from '@/constants/theme';
import type { DefectRegion } from '@/types';

/** 스케치의 빨간 원: 사진 위에 손상 위치를 표시합니다. 원 색은 위험도 게이지 색을 따릅니다. */
export function DefectPhoto({
  uri,
  region,
  size = 220,
  color = C.riskHigh,
  round = false,
}: {
  uri: string;
  region?: DefectRegion | null;
  size?: number;
  color?: string;
  /** true면 원형으로 자르고 테두리를 없앱니다 (위험도 링 안에 넣을 때) */
  round?: boolean;
}) {
  return (
    <View style={[s.wrap, { width: size, height: size }, round && { borderRadius: size / 2, borderWidth: 0 }]}>
      <Image source={{ uri }} style={StyleSheet.absoluteFill} contentFit="cover" />
      {region && (
        <View
          accessibilityLabel="손상 위치 표시"
          style={[
            s.circle,
            {
              borderColor: color,
              left: (region.x - region.r) * size,
              top: (region.y - region.r) * size,
              width: region.r * 2 * size,
              height: region.r * 2 * size,
              borderRadius: region.r * size,
            },
          ]}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    borderRadius: R.card,
    overflow: 'hidden',
    backgroundColor: C.accent,
    alignSelf: 'center',
    borderWidth: 5,
    borderColor: C.card,
  },
  circle: { position: 'absolute', borderWidth: 4 },
});
