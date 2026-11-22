import { Redirect, router } from 'expo-router';
import { Tabs } from 'expo-router/js-tabs';
import { MessageCircle, Newspaper, ScanSearch, User } from 'lucide-react-native';
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

/** 하단 탭: 소식 | 분석 | 채팅 | 내 정보 (PROJECT_PLAN.md 4탭, GAP-020). 업체 목록은 내 정보에서 엽니다. */
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
      {/* 탭 버튼은 숨기고 화면(/vendors)은 유지합니다. */}
      <Tabs.Screen name="vendors" options={{ title: '업체', href: null }} />
      <Tabs.Screen name="profile" options={{ title: '내 정보', tabBarIcon: tabIcon(User) }} />
    </Tabs>
  );
}
