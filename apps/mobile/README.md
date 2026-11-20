# Career Pair 모바일

Expo SDK 58 + Expo Router 앱입니다. 로그인, 프로필 등록·수정(지역·거주 형태), 내 분석 기록 목록, 사진 1~2장 선택, 위치·재질·선택 증상·외부 분석 동의 입력, 샘플 분석 제출, 결과 표시 화면이 구현되어 있습니다.

```bash
cp .env.example .env
npm install          # 저장소 루트에서
npm run mobile       # 저장소 루트에서
npm run typecheck --workspace @career-pair/mobile
```

로그인 후 홈은 `GET /me/profile`로 프로필을 확인합니다. 프로필이 없으면 `/profile` 등록 화면으로 이동하고, 등록·수정은 `GET /regions`의 지역 선택과 `PUT /me/profile`을 사용합니다. 같은 화면의 내 분석 기록 목록은 `GET /records`로 불러오며 항목을 누르면 저장된 결과를 다시 조회합니다.

분석 화면은 `expo-image-picker`로 사진 보관함에서 1~2장을 선택합니다. 첫 사진은 `overview`, 두 번째는 `closeup` 역할로 전송합니다. 제출 시 기록을 먼저 생성한 뒤 `/records/{record_id}/analyze`를 multipart로 호출하고, 결과 화면은 `GET /records/{record_id}`로 저장 결과를 다시 조회합니다. FormData 요청에는 클라이언트가 `Content-Type`을 직접 지정하지 않습니다.

현재 백엔드는 실제 모델 없이 입력값 기반 샘플 결과를 반환합니다. 결과 화면의 샘플 안내를 확인해야 하며, Home Keeper에는 `006_records_material.sql`·`007_profiles_and_regions.sql` 적용 전까지 실제 분석·프로필·목록 호출이 실패합니다.

`.env`의 `EXPO_PUBLIC_API_URL`은 실행 대상에 맞춘다.

| 실행 대상 | 주소 |
| --- | --- |
| iOS Simulator | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기 + Expo Go | `http://<Mac LAN IP>:8000` |

실제 기기에서는 API를 `npm run api`(0.0.0.0 바인딩)로 띄우고 같은 Wi-Fi에 연결한다. `EXPO_PUBLIC_SUPABASE_URL`은 `apps/api/.env`의 `SUPABASE_URL`과 같은 프로젝트여야 한다.

`EXPO_PUBLIC_` 값은 번들에 포함된다. publishable/anon key만 넣고 service role 키는 넣지 않는다.
