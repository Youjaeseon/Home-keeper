import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { Camera, CircleCheck, Images, Sparkles } from 'lucide-react-native';
import { useState } from 'react';
import { Image as RNImage, Modal, Platform, Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';

import { AppBar, Button, Card, CardHeader, Hero, Screen, Txt } from '@/components/ui';
import { C, MAX_W, R, STROKE } from '@/constants/theme';
import { useApp } from '@/store/app-store';
import { showAlert } from '@/lib/alert';

const GAP = 10;

type SamplePreset = {
  key: string;
  label: string;
  source: number;
  location: string;
  position: string;
  material: string;
};

const SAMPLES: SamplePreset[] = [
  {
    key: 'wall-peel',
    label: '벽면 벗겨짐',
    source: require('@/assets/images/samples/wall-peel.jpg'),
    location: '거실',
    position: '벽면',
    material: '페인트',
  },
  {
    key: 'floor-damage',
    label: '바닥 균열·손상',
    source: require('@/assets/images/samples/floor-damage.jpg'),
    location: '거실',
    position: '바닥',
    material: '장판',
  },
  {
    key: 'wall-mold',
    label: '벽면 곰팡이',
    source: require('@/assets/images/samples/wall-mold.jpg'),
    location: '욕실',
    position: '벽면',
    material: '벽지',
  },
];

/** 번들된 정적 이미지를 웹/네이티브 공통 업로드 URI 문자열로 변환합니다. */
function resolveAssetUri(source: unknown): string | null {
  if (typeof source === 'string') return source;
  if (source && typeof source === 'object') {
    if ('uri' in source && typeof (source as { uri?: unknown }).uri === 'string') {
      return (source as { uri: string }).uri;
    }
    if ('default' in source) return resolveAssetUri((source as { default: unknown }).default);
  }
  if (typeof RNImage.resolveAssetSource === 'function') {
    return RNImage.resolveAssetSource(source as number)?.uri ?? null;
  }
  return null;
}

/** 스케치 5: 분석 Page ① — AI 분석 요청할 사진 촬영 또는 선택 */
export default function AnalyzePickScreen() {
  const { photos, addPhoto } = useApp();
  const { width } = useWindowDimensions();
  const [sheetOpen, setSheetOpen] = useState(false);
  const tile = (Math.min(width, MAX_W) - 48 - GAP * 2) / 3;

  const pick = async (source: 'camera' | 'library') => {
    setSheetOpen(false);
    // 선택 창(Modal)이 완전히 닫힌 뒤에 열어야 합니다. 닫히는 도중에 열면 iOS에서 앨범·카메라 화면이 뜨지 않습니다.
    if (Platform.OS !== 'web') await new Promise((r) => setTimeout(r, Platform.OS === 'ios' ? 600 : 200));
    // EXIF(촬영 위치 등)는 받지 않습니다. 서버 업로드 단계에서도 제거해야 합니다.
    const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.7, exif: false };
    try {
      if (source === 'camera' && Platform.OS !== 'web') {
        const perm = await ImagePicker.requestCameraPermissionsAsync();
        if (!perm.granted) {
          showAlert('카메라 권한 필요', '설정에서 카메라 권한을 허용하거나 앨범에서 선택해 주세요.');
          return;
        }
      }
      const result =
        source === 'camera'
          ? await ImagePicker.launchCameraAsync(options)
          : await ImagePicker.launchImageLibraryAsync(options);
      if (result.canceled || !result.assets[0]) return;
      const photo = addPhoto(result.assets[0].uri);
      router.push({ pathname: '/analyze/detail', params: { photoId: photo.id } });
    } catch {
      showAlert('사진을 불러오지 못했습니다', '잠시 후 다시 시도하거나 다른 사진을 선택해 주세요.');
    }
  };

  const pickSample = (sample: SamplePreset) => {
    const uri = resolveAssetUri(sample.source);
    if (!uri) {
      showAlert('샘플 사진을 불러오지 못했습니다', '잠시 후 다시 시도해 주세요.');
      return;
    }
    const photo = addPhoto(uri);
    router.push({
      pathname: '/analyze/detail',
      params: {
        photoId: photo.id,
        location: sample.location,
        position: sample.position,
        material: sample.material,
      },
    });
  };

  return (
    <Screen safeTop>
      <AppBar title="AI 분석" />
      <Hero title={'어디가\n문제인가요?'} subtitle="하자 부위를 찍거나 고르면 AI가 유형과 심각도를 분석해요." />

      <View style={s.grid}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="사진 추가"
          onPress={() => setSheetOpen(true)}
          style={({ pressed }) => [s.tile, s.addTile, { width: tile, height: tile }, pressed && { opacity: 0.85 }]}>
          <View style={s.addCircle}>
            <Camera size={24} color={C.text} strokeWidth={STROKE} />
          </View>
          <Txt variant="label">사진 추가</Txt>
        </Pressable>

        {photos.map((p, i) => (
          <Pressable
            key={p.id}
            accessibilityRole="button"
            accessibilityLabel={`사진 ${photos.length - i} 분석하기`}
            onPress={() => router.push({ pathname: '/analyze/detail', params: { photoId: p.id } })}
            style={({ pressed }) => [s.tile, { width: tile, height: tile }, pressed && { opacity: 0.85 }]}>
            <Image source={{ uri: p.uri }} style={StyleSheet.absoluteFill} contentFit="cover" />
          </Pressable>
        ))}
      </View>

      <Card style={{ gap: 12 }}>
        <CardHeader icon={Sparkles} title="샘플 사진으로 바로 체험하기" />
        <Txt variant="sub" muted>
          본인 사진이 없어도 1탭으로 AI 하자 분석을 바로 체험할 수 있어요.
        </Txt>
        <View style={s.sampleRow}>
          {SAMPLES.map((sample) => (
            <Pressable
              key={sample.key}
              accessibilityRole="button"
              accessibilityLabel={`${sample.label} 샘플 사진으로 분석하기`}
              onPress={() => pickSample(sample)}
              style={({ pressed }) => [s.sampleItem, pressed && { opacity: 0.8 }]}>
              <Image source={sample.source} style={s.sampleThumb} contentFit="cover" />
              <View style={{ gap: 2 }}>
                <Txt variant="label" numberOfLines={1}>
                  {sample.label}
                </Txt>
                <Txt variant="caption" muted numberOfLines={1}>
                  {sample.location} · {sample.position}
                </Txt>
              </View>
            </Pressable>
          ))}
        </View>
      </Card>

      {photos.length === 0 && (
        <Card style={{ gap: 12 }}>
          <Txt variant="h2">잘 찍는 방법</Txt>
          {['하자 부위가 화면 가운데 오도록', '밝은 곳에서 30cm 정도 거리에서', '화면이 흔들리지 않도록 뚜렷하게'].map((t) => (
            <View key={t} style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
              <CircleCheck size={18} color={C.primary} strokeWidth={STROKE} />
              <Txt variant="sub" color={C.text}>
                {t}
              </Txt>
            </View>
          ))}
        </Card>
      )}

      <Modal visible={sheetOpen} transparent animationType="fade" onRequestClose={() => setSheetOpen(false)}>
        <Pressable style={s.backdrop} onPress={() => setSheetOpen(false)}>
          <View style={s.sheet}>
            <View style={s.handle} />
            <Txt variant="title" style={{ marginBottom: 6 }}>
              사진 추가
            </Txt>
            <Button title="사진 촬영" icon={Camera} onPress={() => pick('camera')} />
            <Button title="앨범에서 선택" icon={Images} variant="soft" onPress={() => pick('library')} />
          </View>
        </Pressable>
      </Modal>
    </Screen>
  );
}

const s = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: GAP },
  tile: { borderRadius: R.tile, overflow: 'hidden', backgroundColor: C.card },
  addTile: { backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', gap: 8 },
  addCircle: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: C.accentCircle,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sampleRow: { flexDirection: 'row', gap: 10 },
  sampleItem: {
    flex: 1,
    gap: 8,
    backgroundColor: C.field,
    borderRadius: R.field,
    padding: 8,
  },
  sampleThumb: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 12,
    backgroundColor: C.accent,
  },
  backdrop: { flex: 1, backgroundColor: C.scrim, justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: C.bg,
    padding: 24,
    paddingBottom: 40,
    gap: 10,
    borderTopLeftRadius: R.sheet,
    borderTopRightRadius: R.sheet,
    width: '100%',
    maxWidth: MAX_W,
    alignSelf: 'center',
  },
  handle: { width: 44, height: 5, borderRadius: 3, backgroundColor: C.border, alignSelf: 'center', marginBottom: 8 },
});
