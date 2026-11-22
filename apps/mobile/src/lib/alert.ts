import { Alert, Platform } from 'react-native';

/**
 * 제목·내용만 있는 안내 알림.
 * react-native-web의 Alert.alert는 브라우저에 아무것도 띄우지 않아, 웹에서는 window.alert를 씁니다.
 */
export function showAlert(title: string, message?: string) {
  if (Platform.OS === 'web') {
    window.alert(message ? `${title}\n\n${message}` : title);
    return;
  }
  Alert.alert(title, message);
}
