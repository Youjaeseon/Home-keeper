import { Redirect, router } from 'expo-router';
import { Tabs } from 'expo-router/js-tabs';
import { MessageCircle, Newspaper, ScanSearch, User, Wrench } from 'lucide-react-native';
import type { ColorValue } from 'react-native';

import type { Icon } from '@/components/ui';
import { C, F } from '@/constants/theme';
import { useApp } from '@/store/app-store';

function tabIcon(IconCmp: Icon) {
  function TabIcon({ color, focused }: { color: ColorValue; focused: boolean }) {
    return <IconCmp size={23} color={typeof color === 'string' ? color : C.text} strokeWidth={focused ? 2.5 : 2} />;
  }
  return TabIcon;
}

/** 하단 탭: 소식 | 분석 | 채팅 | 업체 | 정보 (팀원 원본 5탭 유지, GAP-020 Hyeok 결정) */
export default function TabsLayout() {
  const { ready, user, needsProfile } = useApp();
  if (!ready) return null;
  if (needsProfile) return <Redirect href="/profile-setup" />;
  if (!user) return <Redirect href="/" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: C.bg },
        tabBarStyle: {
          backgroundColor: C.card,
          borderTopWidth: 0,
          borderTopLeftRadius: 28,
          borderTopRightRadius: 28,
          height: 74,
          paddingTop: 10,
          elevation: 0,
          shadowOpacity: 0,
        },
        tabBarActiveTintColor: C.primary,
        tabBarInactiveTintColor: C.faint,
        tabBarLabelStyle: { fontFamily: F.bold, fontSize: 12, marginTop: 2 },
      }}>
      <Tabs.Screen name="news" options={{ title: '소식', tabBarIcon: tabIcon(Newspaper) }} />
      <Tabs.Screen name="analyze" options={{ title: '분석', tabBarIcon: tabIcon(ScanSearch) }} />
      <Tabs.Screen
        name="chat"
        options={{ title: '채팅', tabBarIcon: tabIcon(MessageCircle) }}
        listeners={{
          // 채팅 탭은 탭 화면 대신 채팅 목록(스택 화면)을 엽니다.
          tabPress: (e) => {
            e.preventDefault();
            router.push('/dm');
          },
        }}
      />
      <Tabs.Screen name="vendors" options={{ title: '업체', tabBarIcon: tabIcon(Wrench) }} />
      <Tabs.Screen name="profile" options={{ title: '정보', tabBarIcon: tabIcon(User) }} />
    </Tabs>
  );
}
