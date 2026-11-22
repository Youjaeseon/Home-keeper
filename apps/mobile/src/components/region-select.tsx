import { Select } from '@/components/select';
import type { Region } from '@/lib/api';

/**
 * 거주지역 2단계 선택: 시·도를 고르면 그 시·도에 속한 시·군·구만 보여 줍니다.
 * 값은 지금처럼 지역 표시명(display_name) 하나이며, 서버에는 시·군·구 region_id가 저장됩니다.
 */
export function RegionSelect({
  label = '거주지역',
  regions,
  value,
  onChange,
}: {
  label?: string;
  regions: Region[];
  value: string;
  onChange: (displayName: string) => void;
}) {
  const provinces = regions.filter((r) => !r.parent_id);
  const childrenOf = (provinceId: string) => regions.filter((r) => r.parent_id === provinceId);

  const current = regions.find((r) => r.display_name === value);
  const province =
    provinces.find((p) => p.region_id === (current?.parent_id ?? current?.region_id)) ?? provinces[0];
  const cities = province ? childrenOf(province.region_id) : [];
  // 시·도 전체(예: 경기도)도 고를 수 있게 첫 항목으로 둡니다. 기존에 시·도로 저장된 프로필도 그대로 보입니다.
  const cityOptions = province ? [province.display_name, ...cities.map((r) => r.display_name)] : [];
  const cityValue = cityOptions.includes(value) ? value : (cityOptions[0] ?? '');

  if (provinces.length === 0) {
    // 서버가 상위 지역 정보를 주지 않으면 기존처럼 한 목록으로 보여 줍니다.
    return <Select label={label} value={value} options={regions.map((r) => r.display_name)} onChange={onChange} />;
  }

  return (
    <>
      <Select
        label={`${label} (시·도)`}
        value={province?.display_name ?? ''}
        options={provinces.map((p) => p.display_name)}
        onChange={(name) => {
          const next = provinces.find((p) => p.display_name === name);
          if (!next) return;
          const first = childrenOf(next.region_id)[0] ?? next;
          onChange(first.display_name);
        }}
      />
      <Select label={`${label} (시·군·구)`} value={cityValue} options={cityOptions} onChange={onChange} />
    </>
  );
}
