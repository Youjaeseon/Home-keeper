# 서비스 구조

구현된 코드 기준의 논리 구조다. 배포 토폴로지·프록시·오토스케일은 다루지 않는다.

## 구성

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 30, "rankSpacing": 30, "curve": "linear"}}}%%
flowchart TB
    subgraph CLIENT["클라이언트"]
        APP["Expo 앱"]
    end

    SUPA["Supabase Auth<br/>이메일 로그인"]

    subgraph SERVER["FastAPI · 단일 프로세스"]
        GATE["JWT 검증<br/>소유권 · 참여자"]
        API["REST + /chat/ws<br/>기록 · 진단<br/>요청문 · 프로필<br/>소식지 · 업체<br/>견적 · 채팅"]
        VISION["사진 관찰<br/>자체 학습 YOLO<br/>→ Meta SAM<br/>또는 Gemini"]
        TEXT["텍스트 생성<br/>진단 · 요청문"]
    end

    subgraph STORE["데이터 저장"]
        DB[("PostgreSQL<br/>앱 테이블 · RLS<br/>런타임 롤")]
        STORAGE[("Supabase Storage<br/>비공개 버킷")]
    end

    subgraph AIEXT["외부 AI"]
        SAM["Meta SAM 3.1"]
        LLM["Google Gemini<br/>API"]
    end

    subgraph BATCH["소식지 수집"]
        SYNC["GitHub Actions<br/>매일 04:00 KST<br/>수동 CLI"]
        GOV["보조금24<br/>Open API"]
    end

    APP -->|"로그인"| SUPA
    APP -->|"REST · WebSocket<br/>Bearer JWT"| GATE
    GATE -->|"JWKS / HS256"| SUPA
    GATE --> API
    API -->|"psycopg"| DB
    API -->|"업로드 · Signed URL"| STORAGE
    API --> VISION
    API --> TEXT
    VISION -->|"동의 시"| SAM
    VISION -->|"미탐지 시"| LLM
    TEXT -->|"LLM_API_KEY"| LLM
    SYNC -->|"serviceList"| GOV
    SYNC -->|"upsert"| DB
```

## 경계와 제약

- **클라이언트**: 앱은 Supabase Auth로만 직접 통신한다. 하단 탭은 소식·분석·채팅·업체·정보 5개이고, 채팅 탭은 별도 `/dm` 스택 화면을 연다. 데이터·사진·모델 호출은 모두 FastAPI를 거치며, 앱 번들에는 publishable key만 둔다.
- **인증·인가**: FastAPI가 Supabase JWT를 검증하고(HS256 공유 시크릿 또는 JWKS), 기록 소유자·채팅 참여자·견적 요청서 역할을 요청마다 확인한다. DB는 `career_pair_runtime` 롤만 접근하며 Supabase Data API 권한은 회수돼 있다. DB 버전은 코드에서 고정하지 않고 Supabase 인스턴스 설정을 따른다.
- **사진**: 원본은 저장하지 않는다. 긴 변 1600px·EXIF 제거 JPEG만 비공개 버킷에 올리고, 조회는 300초 Signed URL로 제한한다. SAM·Gemini 비전 전송은 사용자 동의와 서버 키가 모두 있을 때만 한다.
- **모델**: 자체 학습 YOLO 체크포인트(`models/best.pt`: 균열·벗겨짐)로 사진을 탐지하고, Meta SAM 3.1과 Google Gemini API는 서버 환경변수 키로만 호출한다. 모델 키·프롬프트·원본 사진은 로그에 남기지 않는다.
- **소식지 배치**: 조회 API는 DB만 읽는다. 수집은 `python -m app.support_sync`가 보조금24를 페이지 단위로 받아 한 트랜잭션으로 upsert하며, 실패하면 기존 행을 유지한다.
- **확장 제한**: 채팅 WebSocket 연결 레지스트리는 API 프로세스 메모리에 있다. 다중 워커·다중 인스턴스로 확장하려면 공유 브로커가 필요하다.
