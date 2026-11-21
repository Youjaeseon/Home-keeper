# LLM/비전 API 제공사별 "데이터 전송 조건" 조사

- **확인일**: 2026-11-21 (KST) — 모든 인용은 이 날짜에 각 사 공식 문서를 직접 열람해 확인
- **문서 버전**: 인용문 옆에 해당 문서의 effective/last-updated 날짜 병기. 날짜 표기가 없는 문서는 "문서에 버전 표기 없음"으로 적음
- **대상**: 사진(이미지 입력)을 외부 LLM에 보낼 때 계약·설정 수준에서 확인해야 하는 것
- **표기**: `확인` = 문서 원문 인용 있음 / `추정` = 문서 정황상 그럴 것으로 보이나 명시 없음 / `미확인` = 접근 실패 또는 문서 없음
- **한계**: NAVER Cloud·KT 문서는 SPA/WAF로 원문 접근이 막혀(403) 정책 조항을 확인하지 못했다. 해당 항목은 전부 `미확인`으로 남겼다. 추측으로 채우지 않았다.

---

## 0. 결론 3줄

1. **"API 입력을 학습에 쓰는가"는 제공사가 아니라 *과금 등급*으로 갈린다.** Gemini API 무료 티어(Unpaid)·Upstage 무료 이용·Meta Contributor 모델은 학습 사용이 명시되어 있고, 같은 회사의 유료 등급은 학습 미사용이다.
2. **ZDR(무보관)은 어느 회사도 해커톤에서 즉시 얻을 수 없다.** OpenAI·Anthropic 모두 영업 승인/계약이 필요하다. "ZDR 확보"를 전제로 설계하면 안 된다.
3. **국외이전을 없애는 선택지는 현재 사실상 (a) Vertex AI 서울 리전, (b) Upstage 한국 리전(Closed Beta)뿐이고, 둘 다 일반 VLM 이미지 분석용으로는 준비 비용 또는 기능 제약이 있다.** Meta SAM은 한국 접근 가능 + 학습 미사용(Standard Model)이라 지금 구조를 유지해도 정책상 문제는 없다.

---

## 1. 비교표

| 제공사 | 모델(비전 지원) | API 입력 학습 사용 | 보관 기간 | ZDR/계약 | 리전·국외이전 | 무료티어 사용 가능 여부 | 근거 URL |
|---|---|---|---|---|---|---|---|
| **OpenAI API** | GPT-6.2 / 6.1 계열, gpt-5.x (이미지 입력 지원). Chat Completions·Responses 모두 이미지 입력 | **없음** — "As of March 1, 2023, data sent to the OpenAI API is not used to train or improve OpenAI models (unless you explicitly opt in)" `확인` | 남용 모니터링 로그 **최대 30일**. Responses API는 `store` 기본값일 때 application state도 30일 보관 `확인` | ZDR·Modified Abuse Monitoring은 **OpenAI 사전 승인 + 추가 요건 동의 필요**, "Contact sales" `확인`. → 해커톤 자격 없음 `추정` | 기본 Global(미국 처리). 데이터 레저던시는 **자격 승인 필요**. `kr.api.openai.com`은 storage Yes·**processing No**, 게다가 "Image support in these regions requires additional approval" `확인` | 무료 등급 조항 없음(유료/선불 크레딧). 무료 크레딧 정책은 `미확인` | [Data controls](https://platform.openai.com/docs/guides/your-data) · [Data residency](https://platform.openai.com/docs/guides/data-residency) · [Enterprise privacy (2026-01-08)](https://openai.com/enterprise-privacy/) |
| **Google Gemini API — 무료(Unpaid)** | Gemini 4 Neon/Hydrogen/Argon, 3.x 계열 (이미지 입력) | **있음** — "Google uses the content you submit … to provide, improve, and develop Google products … and machine learning technologies". 게다가 "human reviewers may read, annotate, and process your API input and output" `확인` | 남용 모니터링 목적 **55일** `확인` | ZDR 없음(약관상 무료 등급은 개선 사용 전제) `확인` | 결제 계정 없는 Cloud 프로젝트 = Unpaid. 저장 위치 통제 없음 `확인`(약관에 리전 선택 조항 없음) | 사용 가능하지만 **"Do not submit sensitive, confidential, or personal information to the Unpaid Services"** 명시 → 사진 분석 부적합 `확인` | [Gemini API Additional Terms (Effective 2026-03-23)](https://ai.google.dev/gemini-api/terms) · [Abuse monitoring](https://aistudio.google.com/docs/usage-policies) |
| **Google Gemini API — 유료(Paid)** | 동일 | **없음** — "Google doesn't use your prompts … or responses to improve our products", DPA(Data Processing Addendum) 적용 `확인` | "logs prompts and responses for a limited period" (구체 일수는 약관에 없음). 남용 모니터링 55일은 별도 문서 기준 `확인`/`부분 미확인` | ZDR 계약 옵션 없음(Vertex와 다름) `추정` | "may be stored transiently or cached in **any country** in which Google or its agents maintain facilities" → 리전 보장 없음 `확인` | 유료 = "Cloud Project associated with an active billing account"일 때만 `확인` | [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms) |
| **Google Vertex AI (Gemini)** | Gemini 4 Neon/Hydrogen/Carbon/Argon (서울 `asia-northeast3` 제공) | **없음** — "Google won't use your data to train or fine-tune any AI/ML models without your prior permission or instruction" `확인` | 일반 모델: 의심 플래그 시 프롬프트 최대 **90일**(고객 선택 리전 내 저장). Frontier 모델: **30일**. Advanced AI(비-Google 모델 등): 프롬프트+응답 **30일**, "opt-out이 불가능할 수 있음" `확인` | ZDR 구성 가능(요청-응답 로깅 끄기, `store=false` 등) 단 "some Advanced AI features"에서는 불가 `확인` | **리전 선택 가능(서울)** — "stored in the same region or multi-region selected by the customer" `확인` | Vertex 무료 체험 크레딧 여부 `미확인` | [Zero data retention](https://cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention) · [Abuse monitoring](https://cloud.google.com/gemini-enterprise-agent-platform/models/abuse-monitoring) · [Locations](https://cloud.google.com/gemini-enterprise-agent-platform/resources/locations) |
| **Anthropic Claude API** | Claude Fable/Mythos/Opus/Sonnet 5.x (이미지 base64, 이미지당 5MB, 요청당 최대 600장/128MB) | **없음** — "Anthropic may not train models on Customer Content from Services" (Commercial Terms, Effective 2025-06-17) `확인` | "we automatically delete inputs and outputs on our backend within **30 days**" `확인`. 단 Covered Models(Fable/Mythos 5 계열)는 30일 보관 **필수** → ZDR 불가 `확인` | ZDR은 **영업팀 계약**으로만("contact the Anthropic sales team") `확인` | `inference_geo` = `global`(기본) 또는 `us`만. **workspace geo는 `us` 단일** → 한국 리전 없음 `확인` | 무료 크레딧 정책 `미확인`(문서상 유료 전제) | [API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention) · [보관 정책 (2026-07-01)](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data) · [Data residency](https://platform.claude.com/docs/en/manage-claude/data-residency) |
| **Meta SAM (api.meta.ai, 현재 사용 중)** | `sam-3-1` (이미지/프레임 분할, $2.50/1k images) | **없음(Standard Model)** — "Meta does not use your Content from Standard Services to train Meta Models". Geographic Use Policy(2026-11-09)에 **SAM 3.1이 Standard Models로 명시** `확인` | 숫자 없음 — ToS §4는 보관 "목적"만 열거("as needed … to provide the Services … policy review"). 수치 `미확인` | ToS상 ZDR 조항 확인 안 됨(가격표에 Voice Transcribe만 "ZDR priced at parity" 언급) `미확인` | 리전 선택 조항 없음. **한국은 Restricted Territories 아님** → 접근 가능. 단 "Muse Wonder/Muse Wonder Full은 South Korea 미제공" `확인` | 무료 등급 없음 — "pay-as-you-go … no minimums". 프로모션 크레딧은 존재 `확인` | [Data Commitments](https://dev.meta.ai/legal/commitments) · [Geo/Model Designation (2026-11-09)](https://dev.meta.ai/legal/geographic-use-policy) · [ToS](https://dev.meta.ai/legal/terms-of-service) · [Pricing](https://dev.meta.ai/docs/pricing-rate-limits) |
| **NAVER CLOVA Studio (HyperCLOVA X API)** | HCX-005 = **비전 지원**("이미지 입력은 … HCX-005에서만"), HCX-DASH-002는 텍스트 | `미확인` (약관 원문 접근 실패 — `www.ncloud.com/policy/terms`는 SPA, `guide.ncloud-docs.com`은 403) | `미확인` | `미확인` | Classic/VPC 환경. **국내 리전 서비스**이나 국외이전 조항 원문 `미확인` | 테스트 API 키 발급 가능(무료 테스트) `확인`. 단 테스트 등급의 데이터 조항 `미확인` | [CLOVA Studio v3 Chat Completions (updated 2026-09-17)](https://api.ncloud-docs.com/docs/clovastudio-chatcompletionsv3) · [개요](https://api.ncloud-docs.com/docs/ai-naver-clovastudio-summary) |
| **Upstage (Solar)** | Solar Pro 4 / Mini 4 = **텍스트 전용**(Capabilities: Chat/Structured/Tool/Reasoning, Vision 없음). 이미지는 Document OCR·Parse로만 처리 | **유료: 없음**("The Company shall not use Member Input/Output Data for service improvement or for training artificial intelligence models"). **무료: 있음**("Member Input/Output Data generated through services provided free of charge … may be used for … research and development of artificial intelligence technologies (including training)") `확인` | `미확인`(약관에 이미지/프롬프트 보관 일수 없음) | `미확인` | **한국 리전 엔드포인트 `kr.api.upstage.ai` 존재하나 "Closed Beta, 별도 승인 필요"**. 지원 모델: Solar Mini 4, Solar Decide, Document Parse, OCR, Information Extract `확인` | 무료 등급 있음 → **학습 사용 조항 적용** `확인` | [Terms of Service](https://www.upstage.ai/terms-of-service) · [Regional endpoints](https://console.upstage.ai/docs/guides/region-usage) · [Models](https://developers.upstage.ai/docs/models) |
| **LG AI (EXAONE API)** | K-EXAONE 2.5 = **Modalities: Text** → 비전 미지원. EXAONE Tabular는 정형데이터 모델 | `미확인`(API 약관 원문 미확보) | `미확인` | `미확인` | `미확인` | `미확인` | [Models (docs.exaone.ai)](https://docs.exaone.ai/docs/models) |
| **KT (Mi:dm 계열)** | `미확인` — APILink 포털이 SPA(문서 미노출) | `미확인` | `미확인` | `미확인` | `미확인` | `미확인` | [apilink.kt.co.kr](https://apilink.kt.co.kr/v2) (공개 문서 없음) |

---

## 2. 제공사별 확인된 사실 (근거 우선)

### 2-1. OpenAI API

- **학습 미사용 (API 전체 등급 공통)** `확인`
  > "As of March 1, 2023, data sent to the OpenAI API is not used to train or improve OpenAI models (unless you explicitly opt in to share data with us)." — *Data controls in the OpenAI platform*
  - 무료 크레딧/유료 구분 없이 "API"에 대한 진술이다. Gemini 무료 티어와 달리 **등급에 따른 학습 사용 분기가 문서에 없다**.
- **남용 모니터링 30일** `확인`
  > "By default, abuse monitoring logs are generated for all API feature usage and retained for up to 30 days" / "may contain certain customer content, such as prompts and responses"
  - `/v1/chat/completions`, `/v1/responses` 모두 `Data used for training: No`, `Abuse monitoring retention: 30 days` 표기.
- **Responses API는 기본이 "저장"** `확인`
  > "the Responses API has a 30 day Application State retention period by default, or when the `store` parameter is set to `true`."
  - ZDR 조직에서는 "`store` parameter … always treated as `false`". → 유료 일반 조직은 **`store:false`를 명시해야** 30일 저장을 피한다.
- **ZDR은 영업 승인제** `확인`
  > "Eligible customers … by getting approved for the Zero Data Retention or Modified Abuse Monitoring controls … subject to prior approval by OpenAI and acceptance of additional requirements … Get in touch with our sales team"
- **이미지 입력 예외** `확인`
  > "Image and file inputs are scanned for CSAM content upon submission. If the classifier detects potential CSAM content, the image will be retained for manual review, **even if Zero Data Retention** … is enabled."
- **데이터 레저던시** `확인` — "Eligible organizations can enable data residency … **Contact sales** to discuss your data residency needs and become eligible."
  - 지역표: `South Korea kr.api.openai.com` — Regional storage **Yes**, Regional processing **No**, 각주 "\* Image support in these regions requires additional approval."
  - → 한국 리전을 켜도 **추론은 국외**에서 일어나고, 게다가 이미지 입력은 추가 승인이 필요하다. **해커톤에서 국외이전 회피 수단이 되지 못한다.**
- **DPA/서브프로세서** `확인` — "we are able to execute a Data Processing Addendum (DPA) with customers … Please complete our DPA form"; 서브프로세서 목록 공개(openai.com/policies/sub-processor-list). 기업용은 SOC 2 Type 2 `확인`.

### 2-2. Google Gemini API — 무료 vs 유료 (핵심)

- **무료(Unpaid) = 학습 사용 + 사람 검토** `확인` (Effective 2026-03-23)
  > "When you use Unpaid Services … Google uses the content you submit to the Services and any generated responses to provide, improve, and develop Google products and services and machine learning technologies"
  > "To help with quality and improve our products, human reviewers may read, annotate, and process your API input and output. … **Do not submit sensitive, confidential, or personal information to the Unpaid Services.**"
  - 무료 등급에도 "Submission of Content" 라이선스가 이미지·문서까지 확장된다고 명시.
- **유료 판정 기준** `확인`
  > "Your access to Gemini API is a 'Paid Service' **only when** accessing the API through a Cloud Project associated with an active billing account."
  - → AI Studio에서 발급한 API 키(결제 미연결)는 **무료 등급**이다. "유료 키인 줄 알았는데 무료"가 가장 흔한 사고 지점.
- **유료 = 학습 미사용 + DPA** `확인`
  > "Google doesn't use your prompts (including … files such as images, videos, or documents) or responses to improve our products, and will process your prompts and responses in accordance with the Data Processing Addendum …"
  > "Google logs prompts and responses for a limited period of time, solely for detecting and preventing violations of the Prohibited Use Policy … This data may be stored transiently or cached in **any country**"
- **보관 기간** `확인` — 남용 모니터링 문서: "Google retains the following data for **fifty-five (55) days** for the purposes of detecting and preventing violations of the Prohibited Use Policy" (프롬프트·맥락·출력).
- **리전** — Gemini API 약관에는 리전 선택 조항이 없다. 유료여도 "any country" 문구가 남아 있어 **국내 처리 보장 불가** `확인`. 한국은 Gemini API 지원 국가 목록에 포함 `확인`.

### 2-3. Google Vertex AI (유료·리전 선택)

- **학습 미사용** `확인`
  > "Google won't use your data to train or fine-tune any AI/ML models without your prior permission or instruction. This applies to all managed models on Gemini Enterprise Agent Platform, including GA and pre-GA models."
- **ZDR 구성 가능하나 예외 존재** `확인`
  > "To achieve zero data retention, customers must take specific actions … Request-response logging: This feature is disabled by default … To achieve zero data retention, do not enable this feature." / "`store` defaults to `true` … To achieve zero data retention, explicitly set `store = false`" / "Zero data retention may not be possible when using some Advanced AI features."
- **보관** `확인`
  - Google Cloud 온라인 약관 고객: 분류기가 의심 플래그 시 프롬프트 최대 **90일**, "stored … in the same region or multi-region selected by the customer".
  - Frontier 모델: 로그 **30일**, "stored securely inside the customer's environment".
  - Advanced AI(비-Google 모델): 프롬프트·응답 **30일**, "may not be possible to opt-out".
- **서울 리전 존재** `확인` — Locations 문서에 `Seoul (asia-northeast3)` + Gemini 4 계열 모델이 리전별 표에 등재.

### 2-4. Anthropic Claude API

- **학습 미사용** `확인` (Commercial Terms, Effective 2025-06-17)
  > "Anthropic may not train models on Customer Content from Services."
- **30일 삭제** `확인` (Privacy Center, 2026-07-01)
  > "For Anthropic API users, we automatically delete inputs and outputs on our backend within 30 days of receipt or generation, except: … When you and we have agreed otherwise (e.g. zero data retention agreement) …"
- **ZDR은 계약제** `확인`
  > "To request ZDR for your organization, contact the Anthropic sales team. ZDR is enabled per organization"
- **Covered Models는 ZDR 불가** `확인`
  > "Claude Fable 5.2, Claude Mythos 5.2, … require 30-day data retention. ZDR is therefore not available for any of them unless expressly authorized by Anthropic."
- **리전** `확인` — `inference_geo` = `"global"`(기본) 또는 `"us"`. "Workspace geo … Currently, `"us"` is the only available workspace geo." → **한국 리전 없음**.
- **이미지 입력** `확인` — base64 소스, 이미지당 5MB(base64 기준), 요청당 최대 600장·128MB. (Vision 문서)

### 2-5. Meta SAM (현재 사용 중인 경로)

- **SAM 3.1은 Standard Model → 학습 미사용** `확인`
  > Data Commitments: "**Standard Services:** Meta does not use your Content from Standard Services to train Meta Models."
  > Geographic Use Policy(Last updated **2026-11-09**), "Standard Models (use constitutes use of 'Standard Services'): … **SAM 3.1** …"
  - Contributor Models는 `Muse Spark 1.2/1.3 Contributor` 두 개뿐 → **SAM에는 학습 사용 변형이 없다**.
  - 참고: Contributor(=Discounted)는 "Meta may use your Content … to train, develop, evaluate, and improve".
- **한국 접근 가능** `확인` — Restricted Territories 목록(아프가니스탄·벨라루스·중국·북한·러시아 등)에 한국 없음. 모델별 제한은 "Muse Wonder / Muse Wonder Full: South Korea"만.
- **보관 기간 숫자 없음** `미확인`
  > ToS §4 Retention: "Meta will retain your Content and Usage Data as needed: (i) to provide the Services …; (iv) when our systems flag data for a potential policy violation; and (v) for security, safety, abuse, and policy review"
  - 기간을 특정하지 않는다. 별도 ZDR 옵션은 가격표에서 Voice Transcribe 항목에만 언급 → SAM의 ZDR 가부 `미확인`.
- **무료 등급 없음** `확인` — "pay-as-you-go … with no minimums or upfront commitment". 프로모션 크레딧은 별도 조항으로 존재.

### 2-6. 국내 대안

- **NAVER CLOVA Studio = HyperCLOVA X API** `확인`(기능) / `미확인`(정책)
  > "이미지를 해석하고 이해할 수 있는 HCX-005 비전 모델과 경량화된 HCX-DASH-002 모델 … 이미지 입력은 HyperCLOVA X 비전 모델인 HCX-005에서만 사용할 수 있으며, 튜닝 학습은 지원하지 않습니다." — *텍스트 및 이미지 (updated 2026-09-17)*
  - 국내 리전(Classic/VPC). 테스트 API 키 발급 경로 존재.
  - **학습 사용 여부·보관 기간·국외이전 조항은 원문 접근 실패로 `미확인`** — 약관 페이지가 SPA이고 guide 호스트가 403.
- **Upstage** `확인`
  > 유료: "The Company shall not use Member Input/Output Data for service improvement or for training artificial intelligence models."
  > 무료: "Member Input/Output Data generated through services provided free of charge … may be used for service provision and improvement, as well as for research and development of artificial intelligence technologies (including training). … when using free services, Members shall not input any data containing their own personal information"
  - **한국 리전**: "use the Korea region dedicated endpoint `kr.api.upstage.ai`. Both API requests and the data being processed are handled exclusively within the Korea region." 단 **"Korea region is currently operated as a Closed Beta, and separate access authorization is required"**, 지원 모델은 Solar Mini 4·Solar Decide·Document Parse·OCR·Information Extract.
  - **비전 LLM 아님**: Solar Pro 4 Capabilities = Chat / Structured outputs / Tool calling / Reasoning (Vision 없음).
- **LG EXAONE API** `확인`(기능) — K-EXAONE 2.5 "Modalities: **Text**", "Languages: 한국어 / 영어". 비전 미지원 → 이번 용도 부적합. 약관·리전 `미확인`.
- **KT** — APILink 포털이 SPA 셸만 반환(1,898 bytes)해 문서·정책 확인 불가. 전 항목 `미확인`.

### 2-7. 이미지 입력의 금지 콘텐츠·민감정보 정책

| 제공사 | 얼굴/생체 | 신분증·개인정보 | 의료 이미지 | 근거 |
|---|---|---|---|---|
| OpenAI | "facial recognition databases without data subject consent", "real-time remote biometric identification in public spaces", "use of someone's likeness … without their consent", "evaluation or classification of individuals based on … biometric data" 금지 | "aggregate, monitor, profile, or distribute individuals' private or sensitive information without their authorization" 금지 | 고위험(의료 등) 자동화는 "human review" 없는 실행 금지 | [Usage policies](https://openai.com/policies/usage-policies/) |
| Google | "using personal data or biometrics without legally-required consent" 위반 | 동일 조항 | "automated decisions that have a material detrimental impact on individual rights without human supervision in high-risk domains — for example … healthcare" 금지 | [Generative AI Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy) |
| Anthropic | "비공개 연락처 정보, 건강 데이터, 생체인식 또는 신경 데이터(얼굴 인식 포함) … 허가 받지 않고 오용, 수집, 요청" 금지 / "얼굴 인식 … 모니터링" 금지 | "동의 없이 개인정보를 공유" 금지 | 의료: "질환 진단 … 해석" 고위험 사용은 자격 있는 사람의 책임 필요 | [Usage Policy (Effective 2026-11-12)](https://www.anthropic.com/legal/aup) |
| Meta | "Identify or track a specific individual based on biometric data, including facial recognition, without a lawful basis and consent" 금지 | "Collect, process, disclose, generate, or infer private or sensitive information about individuals … unless you have obtained the right to do so" | "unauthorized or unlicensed practice of any profession including … medical/health" 금지 | [Model API AUP](https://dev.meta.ai/legal/acceptable-use-policy) |

→ **공통 해석**: 하자 사진은 원칙적으로 안전하지만, 사진에 **사람 얼굴·신분증·문서·의료 영상이 함께 찍히면** 각 사 금지 조항에 닿을 수 있다. 하자 사진에도 임차인 얼굴·문서가 프레임에 들어오는 경우가 흔하다. `확인`(조항) / `추정`(실사진 빈도)

---

## 3. 조건 목록 ("~해야 한다")

각 조건: (a) 근거 → (b) 위반 시 리스크 → (c) 데모에서 최소로 충족하는 방법

**C1. 데모 경로에서 Gemini API 무료(AI Studio) 키를 쓰지 않는다.**
(a) Gemini API 약관: 무료 등급은 "improve and develop Google products" + "human reviewers may read" + "Do not submit sensitive, confidential, or personal information" (Effective 2026-03-23)
(b) 약관 위반 = 계정 정지·프로젝트 차단. 심사에서 "민감정보를 학습에 쓰이는 등급으로 보냈다"는 지적은 감점. 
(c) `.env`에서 Gemini 무료 키를 아예 쓰지 않고, `LLM_BASE_URL`/`MODEL_API_KEY`가 어떤 제공사·등급인지 README 표에 1줄로 고정 기재.

**C2. 외부 비전 호출은 "유료 등급 + 학습 미사용 조항이 확인된" 제공사로만 한다.**
(a) OpenAI "not used to train" / Vertex "won't use your data to train" / Anthropic "may not train models on Customer Content" / Meta "does not use your Content from Standard Services to train"
(b) 무료 등급 사용 시 학습 사용 + 법적 리스크(개인정보 처리 목적 외 이용).
(c) 데모에서는 **비식별 샘플 사진만** 전송(팀 정책 이미 있음) + 제공사·등급·약관 URL을 별첨에 기재.

**C3. Responses API를 쓰면 `store: false`를 명시한다.**
(a) OpenAI: "the Responses API has a 30 day Application State retention period by default, or when the `store` parameter is set to `true`"
(b) 사진·프롬프트가 30일 보관 → "원본 사진 미보관" 앱 설계와 모순, 소개서 기재와 불일치 시 신뢰도 하락.
(c) Chat Completions(현 `llm.py` 방식) 유지 또는 Responses 사용 시 `store: false` 하드코딩 + 코드 주석에 근거 URL.

**C4. 사진을 외부로 보내기 전 고지에 "제공사·목적·보관·국외이전"을 포함하고, 동의 이력과 철회를 저장한다.**
(a) 팀 문서 정책("호출 전 사진·제공사·목적 고지 후 동의") + 개인정보보호법상 국외이전 고지·동의 요건(이전되는 항목·국가·받는 자·목적·보유기간·거부 방법)
(b) 고지 누락은 심사 감점 + 법적 리스크. 현재 구현은 요청 단위 boolean만 있고 이력·철회 저장이 없다(사실 확인됨).
(c) 데모: 동의 화면에 4줄(제공사/목적/보관/국외) 텍스트 + 동의 시 `consent_at`, `provider`, `model`, `policy_url`을 DB 1행 기록. 철회는 스위치 off로 즉시 중단.

**C5. 앱 UI의 "외부 AI로 사진을 보내지 않아요" 문구를 코드 동작과 일치시킨다.**
(a) `apps/mobile/src/app/analyze.tsx:213`은 "현재 샘플 모드에서는 동의 여부와 관계없이 외부 AI로 사진을 보내지 않아요"라고 표시하지만, `apps/api/app/vision.py`는 `consent and settings.model_api_key`일 때 실제로 Meta SAM에 전송한다.
(b) **허위 고지**는 심사에서 가장 치명적인 유형(개인정보 고지 위반) + 팀 문서 정책 위반.
(c) 문구를 "동의 시 Meta SAM(분할)으로 전송, 그 외에는 전송 안 함"으로 수정하거나, 데모에서 `MODEL_API_KEY`를 비워 실제 전송이 없도록 고정. **둘 중 하나는 반드시.**

**C6. 얼굴·신분증·의료영상·문서가 포함된 사진은 외부 전송을 차단한다.**
(a) 4사 금지 조항(2-7 표) + 팀 정책("비식별 미확인 시 외부 분석 건너뛰기")
(b) AUP 위반 = 계정 정지, 민감정보 처리 리스크.
(c) 데모 최소: (i) 업로드 화면에 "얼굴·신분증·의료영상이 포함된 사진은 사용하지 마세요" 1줄, (ii) 서버에서 얼굴 검출 시 `segmentation_status=skipped_sensitive`로 스킵하는 분기 1개(모델 없이 스킵만 해도 요구 충족), (iii) 시연 사진은 팀 제작 샘플 고정.

**C7. "ZDR 확보"를 전제로 설계하지 않는다.**
(a) OpenAI ZDR = "prior approval by OpenAI … Contact sales"; Anthropic ZDR = "contact the Anthropic sales team"; Covered Models는 ZDR 불가.
(b) ZDR 전제 설계는 문서·소개서 기재와 실제 동작 불일치 → 심사 지적.
(c) 소개서에는 "30일 남용 모니터링 보관(제공사 정책), 우리 앱은 원본 미보관"처럼 **사실대로** 적는다.

**C8. 국외이전을 피해야 한다면 Vertex AI 서울 리전 또는 Upstage 한국 리전만 후보로 둔다 — 둘 다 준비 비용/기능 제약을 먼저 확인한다.**
(a) OpenAI `kr.api.openai.com`은 processing No + 이미지 추가 승인 / Anthropic은 `us`만 / Gemini API는 "any country" / Upstage 한국 리전은 Closed Beta + VLM 없음 / CLOVA Studio는 정책 `미확인`
(b) "국내 처리"라고 잘못 표기하면 허위 기재.
(c) 데모에서는 **국내 처리 주장을 하지 않는다.** 소개서에는 "외부 비전 모델은 Meta SAM(미국), 비식별 샘플만" 처럼 실제 경로를 적는다.

**C9. AI 활용내역·별첨에 제공사·모델명·약관명·버전(확인일)·URL을 적는다.**
(a) 제출물 요구사항("외부 자원 출처·라이선스·이용 조건") 
(b) 누락 시 형식 요건 미충족.
(c) 이 문서의 표 1을 그대로 축약해 붙인다(모델·학습 사용·보관·URL·확인일 2026-11-21).

**C10. 서버 로그·DB·백업에 이미지 원문과 프롬프트 원문을 남기지 않는다(현행 유지 + 신규 경로에도 적용).**
(a) 앱 설계(원본 미보관) + OpenAI "logs may contain prompts and responses"와 무관하게 우리 쪽 최소화 원칙
(b) "원본 미보관" 기재와 실제 로그 불일치.
(c) 신규 비전 함수도 `httpx` 예외 메시지·응답 본문을 로그에 남기지 않도록 기존 `llm.py` 패턴 유지.

---

## 4. 해커톤 데모에서 안전한 기본 선택

### 권장: **"외부 비전 LLM 신규 호출 없음"을 기본값으로 두고, 시연에 꼭 필요할 때만 OpenAI 유료 API + 비식별 샘플 사진**

**1순위 (기본, 추가 작업 0)**
- 사진 경로 = 로컬 YOLO + (동의 시) Meta SAM `sam-3.1` 유지. **SAM은 Standard Model로 학습 미사용이 문서에 명시**되어 있고 한국에서 접근 가능하므로, 지금 구조는 정책상 이미 안전하다.
- 새 비전 LLM 경로는 **기본 비활성**(`VISION_LLM_ENABLED=false` 같은 스위치) + 팀이 만든 비식별 샘플 사진으로만 동작.
- 이유: (i) 요구되는 4개 제공사 중 "무료 + 학습 미사용 + 국내" 조합이 존재하지 않는다, (ii) ZDR은 어디서도 즉시 못 얻는다, (iii) 남은 리스크는 "우리가 무엇을 어디로 보냈는가"를 정확히 쓰는 것뿐이고, 전송을 0으로 만들면 그 리스크도 0이 된다.

**2순위 (실시간 외부 비전 시연이 필요할 때)**
- **OpenAI 유료 API**(이미 있는 `llm.py` 확장, Chat Completions + base64 이미지, `store` 파라미터 없음).
- 이유: (i) "API 데이터는 학습에 사용하지 않는다"가 **등급 분기 없이** 문서화된 유일한 축, (ii) 이미 OpenAI 호환 클라이언트·타임아웃·폴백이 구현되어 있어 추가 리스크가 가장 작다, (iii) Chat Completions는 application state를 저장하지 않는다.
- 전제: **비식별 샘플 사진만**, 소개서에 "미국 처리·남용 로그 최대 30일" 명시.
- 하지 말 것: Responses API 기본값(`store` 미설정), Gemini 무료 키, Upstage 무료 등급.

**3순위 (심사에서 "국내 처리"가 중요할 때)**
- **Vertex AI Gemini, `asia-northeast3`(서울), Cloud Billing 연결(Paid)**.
- 이유: 유일하게 "학습 미사용 + 리전 선택 + ZDR 구성"을 동시에 문서로 제공. 
- 비용: 프로젝트·빌링·IAM·리전 설정 + `store=false`·요청-응답 로깅 off 확인 필요 → 남은 기간 대비 준비 부담이 크다. **마감 2026-11-23 17:00 기준으로는 1·2순위 권장.**

**절대 쓰지 말 것 (근거 있는 금지)**
| 금지 | 이유(근거) |
|---|---|
| Gemini API 무료(AI Studio 키) | 학습 사용 + 사람 검토 + "민감정보 제출 금지" 명시 (Effective 2026-03-23) |
| Upstage 무료 등급 | "services provided free of charge … may be used for … training" (ToS) |
| Meta `*-contributor` 모델 | "Meta may use your Content … to train" (Data Commitments) |
| ZDR 전제 설계 | OpenAI·Anthropic 모두 영업 승인/계약 필요 |
| "국내에서 처리됩니다" 문구 | OpenAI KR 리전은 processing No, 이미지 추가 승인 필요 |

---

## 5. 미확인 · 추가 확인 필요

| # | 항목 | 왜 미확인인가 | 확인 방법 |
|---|---|---|---|
| 1 | NAVER CLOVA Studio 학습 사용 여부·보관 기간·국외이전 조항 | `ncloud.com/policy/terms`가 SPA, `guide.ncloud-docs.com` 403 | 콘솔 로그인 후 약관 원문, 또는 고객센터 문의(1670-1179) |
| 2 | CLOVA Studio 테스트 API 키(무료) 등급의 데이터 조항 | 위와 동일 | 동일 |
| 3 | KT Mi:dm API 비전 지원·데이터 정책 | APILink 포털이 SPA 셸만 반환 | KT Enterprise 문의 / 계약 문서 |
| 4 | LG EXAONE API 약관·보관·리전 | 약관 페이지 경로 미노출(404) | docs.exaone.ai 내 Terms & Policies 로그인 후 확인 |
| 5 | Meta Model API 콘텐츠 보관 기간(숫자) | ToS는 목적만 열거, 수치 없음 | Meta 계약/Help Center, 또는 DPA 요청 |
| 6 | Meta SAM의 ZDR 옵션 존재 여부 | 가격표에 Voice Transcribe만 ZDR 언급 | Meta 영업 문의 |
| 7 | OpenAI 무료 체험 크레딧 정책(2026) | 문서에 free tier 조항 없음 | 플랫폼 결제 화면 확인 |
| 8 | Gemini API 유료 등급의 정확한 로그 보관 일수 | 약관은 "limited period", 별도 문서는 55일(남용 모니터링) | Google Cloud 지원 문의 |
| 9 | Vertex AI 무료 체험 크레딧으로 Gemini 사용 가능 여부 | 미확인 | Cloud Billing 콘솔 |
| 10 | 각 사의 서버 내부 이미지 전처리(리사이즈·썸네일) 보관 여부 | 공개 문서 없음 | 각 사 DPA/보안 백서 |
| 11 | 국내 개인정보보호법상 "국외이전" 고지·동의 요건의 데모 적용 범위 | 법률 판단 영역(본 조사 범위 밖) | 개인정보보호위원회 고시·법무 검토 |
| 12 | 대회(주최측) 외부 AI 사용 규정 원문 | 대회 문서 미확인 | 대회 안내문·운영사무국 |

---

## 6. 이 리포지토리에 즉시 반영할 지점 (조사 중 발견)

| 위치 | 현재 | 문제 | 조치 |
|---|---|---|---|
| `apps/mobile/src/app/analyze.tsx:213` | "동의 여부와 관계없이 외부 AI로 사진을 보내지 않아요" | `vision.py`는 동의+키가 있으면 Meta SAM으로 전송 → **허위 고지** | 문구 수정 또는 데모에서 `MODEL_API_KEY` 미설정 고정 |
| `apps/api/app/vision.py:126` | `https://api.meta.ai/v1/responses`, `sam-3.1` | 정책상 문제 없음(Standard Model)이나 **보관 기간 미확인** | 별첨에 "보관 기간 제공사 문서에 수치 미기재"로 정직하게 기재 |
| `apps/api/app/vision.py:172` | `if detections and consent and settings.model_api_key` | 동의 이력·제공사·정책 버전 미기록 | `consent_at`/`provider`/`policy_url` 1행 기록 추가 |
| `apps/api/app/llm.py` | OpenAI 호환 chat/completions, 기본 `api.openai.com` | `LLM_BASE_URL`을 무료 등급 엔드포인트로 바꾸면 조용히 약관 위반 가능 | 시작 시 허용 호스트 화이트리스트 검사 + README에 등급 명시 |
