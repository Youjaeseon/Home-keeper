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

/**
 * 확인·취소 두 버튼으로 묻습니다. 확인을 누르면 true.
 * 웹에서는 window.confirm을 씁니다.
 */
export function confirmAlert(title: string, message: string, confirmText = '확인'): Promise<boolean> {
  if (Platform.OS === 'web') return Promise.resolve(window.confirm(`${title}\n\n${message}`));
  return new Promise((resolve) => {
    Alert.alert(
      title,
      message,
      [
        { text: '취소', style: 'cancel', onPress: () => resolve(false) },
        { text: confirmText, style: 'destructive', onPress: () => resolve(true) },
      ],
      { cancelable: true, onDismiss: () => resolve(false) },
    );
  });
}
