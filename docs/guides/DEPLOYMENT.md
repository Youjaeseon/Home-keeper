# Docker 배포

FastAPI API를 Linux 컨테이너로 실행합니다. Expo 앱은 별도로 빌드·배포하고,
PostgreSQL·Auth·Storage는 기존 Supabase 프로젝트를 사용합니다.
Python 3.13과 `uv.lock`의 운영·vision 의존성을 설치하며, 개발용 reload는 사용하지 않습니다.
Docker Engine과 Docker Compose 2.30 이상이 필요합니다(`env_file.format: raw` 사용).
현재 lockfile의 Linux용 PyTorch는 CUDA 관련 패키지도 설치하므로 CPU 운영이어도
첫 빌드의 다운로드·이미지·캐시에 수 GB 이상의 디스크 공간이 필요합니다.
로컬 Linux arm64 빌드의 이미지 크기는 약 10GB였습니다.

검증 범위: Linux arm64 이미지 빌드, 기본 명령으로 기동·healthcheck 통과,
UID 10001 실행, `/health`·`/docs`·`/vision-test`·`/openapi.json` 응답,
vision 모듈 import와 실제 `best.pt`의 CPU 추론을 확인했습니다.
amd64·GPU·운영 DB·외부 AI 호출·HTTPS 접속은 이 검증에 포함하지 않았습니다.

## 서버 준비

저장소 루트에서 실행합니다. 기존 `.env`가 있다면 복사하지 말고 배포 값을 확인하세요.

```bash
cp apps/api/.env.example apps/api/.env
chmod 600 apps/api/.env
mkdir -p models
```

- `DATABASE_URL`: 운영 DB의 `career_pair_runtime` 연결 문자열. 컨테이너의 `localhost`는 컨테이너 자신이므로 Supabase DB 호스트를 사용합니다.
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`: 운영 Supabase 프로젝트 값.
- `LLM_API_KEY`, 필요 시 `LLM_MODEL` 등: 실제 사진 진단에 사용할 서버 키와 모델.
- `YOLO_MODEL_PATH=../../models/best.pt`: 신뢰할 수 있는 학습 체크포인트를 서버의 `models/best.pt`로 복사합니다. `/srv/models`에 읽기 전용으로 마운트되며 이미지에는 포함되지 않습니다. UID 10001 사용자가 디렉터리를 탐색하고 파일을 읽을 수 있어야 합니다.
- `MODEL_API_KEY`: 외부 분석 동의 시 SAM 호출에 사용할 서버 키.
- 사진 보관을 사용하면 Supabase 비공개 버킷과 `SUPABASE_STORAGE_KEY`를 설정합니다.
- Expo web을 사용하면 `CORS_ORIGINS`에 실제 웹 origin을 쉼표로 구분해 넣습니다.

환경변수 파일은 `KEY=value` 형식으로 작성하며 값을 따옴표로 감싸지 않습니다.
Compose는 `$`, `#`, 따옴표를 값 그대로 전달합니다. `.env`와 키는 이미지에 복사되지 않습니다.
YOLO를 사용하지 않으면 `YOLO_MODEL_PATH=`로 비우세요. 모델 디렉터리는 여전히 필요합니다.

## 빌드·마이그레이션·실행

```bash
docker compose build api
```

새 DB이거나 새 마이그레이션이 있으면 먼저 적용합니다. 운영 DB를 백업하고,
관리자 연결 문자열을 입력한 뒤 일회성 컨테이너에만 전달합니다.
일반 API 컨테이너의 `MIGRATION_DATABASE_URL`은 항상 빈 값으로 덮어씁니다.

```bash
read -r -s -p 'Migration DB URL: ' MIGRATION_DATABASE_URL
echo
export MIGRATION_DATABASE_URL
docker compose run --rm --no-deps -e MIGRATION_DATABASE_URL api python -m app.migrate
unset MIGRATION_DATABASE_URL
```

위 입력 명령은 Bash 기준입니다. zsh에서는 첫 줄을
`read -r -s 'MIGRATION_DATABASE_URL?Migration DB URL: '`로 바꿉니다.
마이그레이션은 서버 시작 시 자동 실행하지 않습니다.
처음 설정하는 DB의 런타임 역할 비밀번호·권한은 [개발 가이드](DEVELOPMENT.md#supabase-사용-시)를 참고하세요.

```bash
docker compose up -d --wait api
curl --fail http://127.0.0.1:8000/health
docker compose ps
docker compose logs --tail=100 api
```

`/health`는 프로세스 응답만 검사합니다. DB·모델·외부 API 연결은 실제 로그인 후
기록 생성·사진 분석·채팅으로 확인해야 합니다. 모델 로딩은 백그라운드에서 수행되므로
healthy 상태만으로 YOLO 준비 완료를 판단하지 않습니다.

## 외부 접속

기본 포트는 호스트의 `127.0.0.1:8000`에만 열립니다. 호스트의 HTTPS reverse proxy가
이 주소로 요청을 전달하도록 하고, `/chat/ws`의 WebSocket upgrade와 사진 분석 요청의
업로드 크기·응답 제한 시간을 설정합니다. 이 구성에는 TLS 인증서 발급·proxy가 포함되지 않습니다.
별도 네트워크 구성이 필요할 때만 `API_BIND_ADDRESS`, `API_PORT`를 지정해 실행합니다.

모바일의 `EXPO_PUBLIC_API_URL`은 외부에서 접속할 수 있는 HTTPS API 주소로 설정한 뒤
앱을 다시 빌드합니다. 서버 `.env`를 바꿔도 이미 배포한 앱의 주소는 바뀌지 않습니다.
채팅 연결 목록이 프로세스 메모리에 있으므로 worker 1개·API 컨테이너 1개로 운영합니다.

## 업데이트·중지

```bash
git pull --ff-only
docker compose build api
# 새 마이그레이션이 있으면 위의 일회성 명령으로 먼저 적용
docker compose up -d --wait api
```

재생성 시 기존 WebSocket 연결이 끊기며 앱이 재연결해야 합니다.
환경변수만 바꿨다면 `docker compose up -d --force-recreate --wait api`로 반영합니다.
중지는 `docker compose down`입니다. 운영 데이터는 외부 Supabase에 있고 모델은 호스트에 남습니다.
CPU 실행 기준이며 GPU 장치 전달은 구성하지 않았습니다.
