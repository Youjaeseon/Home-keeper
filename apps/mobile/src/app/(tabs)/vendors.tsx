import { router } from "expo-router";
import { ChevronRight, Info, Phone, Star } from "lucide-react-native";
import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, View } from "react-native";

import { VendorBadge } from "@/components/vendor-badge";
import { AppBar, Card, Chip, Hero, Notice, Screen, Txt } from "@/components/ui";
import { C, STROKE } from "@/constants/theme";
import { messageOf } from "@/lib/api";
import { fetchVendors } from "@/services/vendors";
import { useApp } from "@/store/app-store";
import type { Vendor } from "@/types";

/** 분야 필터: 작업 종류 이름 → 버튼 문구 (화면에 있는 분야만 버튼으로 보여 줍니다) */
const FIELDS: { key: string; label: string }[] = [
  { key: "곰팡이 제거", label: "곰팡이" },
  { key: "벽지·도장 보수", label: "도배·도장" },
  { key: "원인 점검", label: "누수·원인 점검" },
];

/** 스케치 8: 업체 모음 — 업체명, 설명, 연락처 (GET /providers, 내 지역 기준 별점순). 분야 버튼으로 걸러 봅니다. */
export default function VendorsScreen() {
  const { user } = useApp();
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [isSample, setIsSample] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState<string | null>(null);
  const load = () =>
    user?.regionId
      ? fetchVendors(user.regionId, null, user.region)
          .then((res) => {
            setVendors(res.vendors);
            setIsSample(res.isSample);
            setError(null);
          })
          .catch((e) => setError(messageOf(e)))
      : Promise.resolve();
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.regionId, user?.region]);

  return (
    <Screen safeTop onRefresh={load}>
      <AppBar title="업체 목록" />
      <Hero
        title="업체 모음"
        subtitle={`${user?.region ?? ""} 업체 중 직접 해결이 어려울 때 견적을 문의해 보세요.`}
      />
      {isSample && (
        <Notice icon={Info}>
          이 지역에 등록된 업체가 없어 시연용 샘플 업체를 보여 드려요. 실제
          업체가 아닙니다.
        </Notice>
      )}
      {error && <Notice icon={Info}>{error}</Notice>}

      {/* 분야별 버튼: 전체 + 목록에 있는 분야만 */}
      {vendors.length > 0 && (
        <View style={s.filters}>
          {[
            { key: null as string | null, label: "전체" },
            ...FIELDS.filter((f) =>
              vendors.some((v) => v.specialties.includes(f.key)),
            ),
          ].map((f) => {
            const on = field === f.key;
            return (
              <Pressable
                key={f.label}
                accessibilityRole="button"
                accessibilityState={{ selected: on }}
                accessibilityLabel={`${f.label} 업체만 보기`}
                onPress={() => setField(f.key)}
                style={[s.filter, on && s.filterOn]}
              >
                <Txt
                  variant="label"
                  color={on ? C.onPrimary : C.text}
                  numberOfLines={1}
                  adjustsFontSizeToFit
                  minimumFontScale={0.9}
                  style={s.filterText}
                >
                  {f.label} {f.key ? vendors.filter((v) => v.specialties.includes(f.key as string)).length : vendors.length}
                </Txt>
              </Pressable>
            );
          })}
        </View>
      )}

      {vendors
        .filter((v) => !field || v.specialties.includes(field))
        .map((v) => (
          <Pressable
            key={v.id}
            accessibilityRole="button"
            accessibilityLabel={`${v.name}에 메시지 보내기`}
            // 업체를 누르면 메시지 창으로 이동합니다(뒤로 가면 업체 목록). 전화는 전화번호 버튼으로만 겁니다.
            // 앱에 가입하지 않은 업체는 메시지 창에서 '앱 채팅 미지원' 안내가 나옵니다.
            onPress={() =>
              router.push({
                pathname: "/dm/[vendorId]",
                params: { vendorId: v.id, name: v.name },
              })
            }
            style={({ pressed }) => pressed && { opacity: 0.85 }}
          >
            <Card style={s.row}>
              <VendorBadge vendor={v} />
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
                  {!v.realListing && (
                    <Star size={13} color={C.sub} strokeWidth={STROKE} />
                  )}
                  {!v.realListing && (
                    <Txt variant="caption" muted>
                      {v.rating.toFixed(1)} ({v.reviewCount})
                    </Txt>
                  )}
                  {v.phone.replace(/[^0-9]/g, "").length >= 7 ? (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={`${v.name}에 전화 걸기 ${v.phone}`}
                      hitSlop={6}
                      onPress={() =>
                        void Linking.openURL(
                          `tel:${v.phone.replace(/[^0-9+]/g, "")}`,
                        )
                      }
                      style={({ pressed }) => [
                        s.call,
                        pressed && { opacity: 0.7 },
                      ]}
                    >
                      <Phone size={13} color={C.primary} strokeWidth={STROKE} />
                      <Txt variant="label" color={C.primary}>
                        {v.phone}
                      </Txt>
                    </Pressable>
                  ) : (
                    <Txt variant="caption" muted>
                      {v.phone}
                    </Txt>
                  )}
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
  // 분야 버튼은 한 줄에 모두 들어가도록 폭을 나눠 갖고, 글자는 조금 작게 씁니다.
  filters: { flexDirection: "row", gap: 6 },
  filter: {
    flexGrow: 1,
    flexShrink: 1,
    paddingHorizontal: 8,
    minHeight: 34,
    borderRadius: 999,
    backgroundColor: C.card,
    alignItems: "center",
    justifyContent: "center",
  },
  filterOn: { backgroundColor: C.primary },
  filterText: { fontSize: 12, lineHeight: 16 },
  row: { flexDirection: "row", alignItems: "center", gap: 14, padding: 18 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 2 },
  phone: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 4,
  },
  call: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: C.accent,
  },
});
