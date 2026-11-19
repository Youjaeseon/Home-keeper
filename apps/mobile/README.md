# Career Pair 모바일

Expo SDK 58 + Expo Router 앱입니다. 현재는 로그인과 FastAPI 연결 확인 화면만 있습니다.

```bash
cp .env.example .env
npm install          # 저장소 루트에서
npm run mobile       # 저장소 루트에서
```

`.env`의 `EXPO_PUBLIC_API_URL`은 실행 대상에 맞춘다.

| 실행 대상 | 주소 |
| --- | --- |
| iOS Simulator | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기 + Expo Go | `http://<Mac LAN IP>:8000` |

실제 기기에서는 API를 `npm run api`(0.0.0.0 바인딩)로 띄우고 같은 Wi-Fi에 연결한다. `EXPO_PUBLIC_SUPABASE_URL`은 `apps/api/.env`의 `SUPABASE_URL`과 같은 프로젝트여야 한다.

`EXPO_PUBLIC_` 값은 번들에 포함된다. publishable/anon key만 넣고 service role 키는 넣지 않는다.
