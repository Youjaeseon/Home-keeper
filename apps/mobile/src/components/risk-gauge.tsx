import { View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';

import { DefectPhoto } from '@/components/defect-photo';
import { Txt } from '@/components/ui';
import { C, riskColor, riskLabel } from '@/constants/theme';
import type { DefectRegion } from '@/types';

/** 위험도 원형 게이지. 색은 위험도 구간(낮음·주의·높음)으로만 바뀝니다. */
export function RiskGauge({ risk, size = 148 }: { risk: number; size?: number }) {
  const stroke = 16;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const color = riskColor(risk);

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={C.border} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circ} ${circ}`}
          strokeDashoffset={circ * (1 - risk / 100)}
        />
      </Svg>
      <Txt variant="caption" muted>
        위험도
      </Txt>
      <Txt variant="display" color={color} style={{ fontSize: 34, lineHeight: 40 }}>
        {risk}%
      </Txt>
      <Txt variant="label" color={color}>
        {riskLabel(risk)}
      </Txt>
    </View>
  );
}

/**
 * 원형 사진 + 사진 테두리를 감싸는 위험도 링.
 * 링이 채워진 길이 = 위험도(%), 색은 위험도 구간(낮음·주의·높음)을 따릅니다.
 */
export function RiskPhotoRing({
  uri,
  region,
  risk,
  size = 260,
  stroke = 16,
  gap = 8,
}: {
  uri: string;
  region?: DefectRegion | null;
  risk: number;
  size?: number;
  stroke?: number;
  /** 링과 사진 사이 여백 (px) */
  gap?: number;
}) {
  const r = (size - stroke) / 2;
  const c = size / 2;
  const color = riskColor(risk);
  // 12시 방향에서 시계 방향으로 위험도 퍼센트만큼만 채웁니다 (100% = 한 바퀴).
  const pct = Math.max(0, Math.min(100, risk));
  const angle = (pct / 100) * 2 * Math.PI;
  const ex = c + r * Math.sin(angle);
  const ey = c - r * Math.cos(angle);
  const photo = size - (stroke + gap) * 2;

  return (
    <View
      accessibilityLabel={`위험도 ${risk}%, ${riskLabel(risk)}`}
      style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center', alignSelf: 'center' }}>
      <Svg width={size} height={size} style={{ position: 'absolute' }}>
        <Circle cx={c} cy={c} r={r} stroke={C.border} strokeWidth={stroke} fill="none" />
        {pct >= 100 ? (
          <Circle cx={c} cy={c} r={r} stroke={color} strokeWidth={stroke} fill="none" />
        ) : pct > 0 ? (
          <Path
            d={`M ${c} ${c - r} A ${r} ${r} 0 ${pct > 50 ? 1 : 0} 1 ${ex} ${ey}`}
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            fill="none"
          />
        ) : null}
      </Svg>
      <DefectPhoto uri={uri} region={region} size={photo} color={color} round />
    </View>
  );
}

/** 3구간 범례 */
export function RiskLegend() {
  const items = [
    { c: C.riskLow, t: '낮음 0~39' },
    { c: C.riskMid, t: '주의 40~69' },
    { c: C.riskHigh, t: '높음 70~100' },
  ];
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 14 }}>
      {items.map((i) => (
        <View key={i.t} style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
          <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: i.c }} />
          <Txt variant="caption" muted>
            {i.t}
          </Txt>
        </View>
      ))}
    </View>
  );
}
