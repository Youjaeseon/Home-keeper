import { Redirect } from 'expo-router';

/** 채팅 탭 자리. 실제 화면은 채팅 목록(/dm)입니다. */
export default function ChatTab() {
  return <Redirect href="/dm" />;
}
