import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { Camera, CircleCheck, Images } from 'lucide-react-native';
import { useState } from 'react';
import { Alert, Modal, Platform, Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';

import { AppBar, Button, Card, Hero, Screen, Txt } from '@/components/ui';
import { C, MAX_W, R, STROKE } from '@/constants/theme';
import { useApp } from '@/store/app-store';

const GAP = 10;

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
          Alert.alert('카메라 권한 필요', '설정에서 카메라 권한을 허용하거나 앨범에서 선택해 주세요.');
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
      Alert.alert('사진을 불러오지 못했습니다', '잠시 후 다시 시도하거나 다른 사진을 선택해 주세요.');
    }
  };

  return (
    <Screen safeTop>
      <AppBar title="AI 분석" />
      <Hero title={'어디가\n문제인가요?'} subtitle="하자 부위를 찍거나 고르면 AI가 유형과 위험도를 분석해요." />

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
