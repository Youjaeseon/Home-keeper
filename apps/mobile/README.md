# Home Keeper 모바일 (`@career-pair/mobile`)

자취생·청년 1인 가구를 위한 AI 하자 진단 앱입니다. Expo SDK 58 + Expo Router(TypeScript)이며, 팀원이 만든 Home Keeper UI를 기반으로 합니다.

## 실행

```bash
cp apps/mobile/.env.example apps/mobile/.env   # 값 채우기
npm install                                    # 저장소 루트에서
npm run mobile                                 # 저장소 루트에서
npm run typecheck --workspace @career-pair/mobile
```

`.env`의 `EXPO_PUBLIC_API_URL`은 실행 대상에 맞춥니다.

| 실행 대상 | 주소 |
| --- | --- |
| iOS Simulator | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기 + Expo Go | `http://<Mac LAN IP>:8000` |

`EXPO_PUBLIC_` 값은 번들에 포함됩니다. publishable/anon key만 넣고 `service_role` 키는 절대 넣지 않습니다.

## 화면 구조 (`src/app`)

| 화면 | 파일 |
|---|---|
| 로그인 | `index.tsx` |
| 회원가입 | `signup.tsx` |
| 소식지 | `(tabs)/news.tsx` |
| 분석 ① 사진 촬영·선택 | `(tabs)/analyze/index.tsx` |
| 분석 ② 정보 기입 | `(tabs)/analyze/detail.tsx` |
| 분석 결과 | `(tabs)/analyze/result.tsx` |
| 업체 모음 | `(tabs)/vendors.tsx` |
| 사용자 정보 | `(tabs)/profile.tsx` |
| 채팅 목록 / 대화 | `dm/index.tsx`, `dm/[vendorId].tsx` |

`src/lib/`는 Supabase Auth 세션 저장(`storage*.ts`), 환경변수(`env.ts`), 백엔드 API 클라이언트(`api.ts`)입니다.

## 규칙

- API key는 앱 코드에 넣지 않습니다. 앱은 팀 backend만 호출하고 key는 backend에 둡니다.
- 실제 개인정보·실사진(EXIF 포함)을 외부 AI API로 보내지 않습니다.
- 폰트: Pretendard (SIL Open Font License 1.1, `assets/fonts/Pretendard-LICENSE.txt`).
