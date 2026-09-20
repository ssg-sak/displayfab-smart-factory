# DisplayFab 시연 서버 운영

## 로컬 Docker 시연 서버

`compose.demo.yml`은 기존 개발용 `docker-compose.yml`과 다른 PostgreSQL 볼륨을 쓴다.
시연 초기화가 기존 개발 DB를 지우지 않는다. DB 포트는 호스트에 노출하지 않는다.

루트의 `.env.demo`에 아래 두 값을 설정한다. 비밀번호는 URL에 바로 넣을 수 있는 영문·숫자를 사용한다.
이 파일은 Git과 Docker 이미지에서 제외된다.

```dotenv
DISPLAYFAB_DEMO_DB_PASSWORD=랜덤한영문숫자비밀번호
DISPLAYFAB_ADMIN_TOKEN=별도의랜덤한관리자토큰
```

```powershell
docker compose --env-file .env.demo -f compose.demo.yml up -d --build --wait
```

- 화면: http://127.0.0.1:8098
- API 상태: http://127.0.0.1:8098/api/health
- API 문서: http://127.0.0.1:8098/docs
- 로그: `docker compose --env-file .env.demo -f compose.demo.yml logs --tail 100 app`
- 중지: `docker compose --env-file .env.demo -f compose.demo.yml stop`
- 재개: 위 `up` 명령. Docker가 실행되면 `unless-stopped` 정책으로 재시작한다.

`DISPLAYFAB_HTTP_PORT`를 설정하면 다른 포트를 쓸 수 있다. 8000은 다른 프로젝트가 쓸 수 있으므로 기본값은 8098이다.
이 주소는 내 PC용이며, 인터넷 공개 주소는 아래 Render 배포 후 생긴다.

## Render + Neon 공개 배포

현재 공개 시연: https://displayfab-smart-factory.onrender.com

1. [Neon 콘솔](https://console.neon.tech)에서 가입하고 **시연 전용 프로젝트·DB**를 만든다.
   프로젝트 이름은 `displayfab-demo`로 정한다. Connect에서 SSL 접속 문자열을 복사한다.
   기존 개발 DB와 공유하지 않는다.
2. [이 저장소의 Render 배포 화면](https://render.com/deploy?repo=https://github.com/ssg-sak/displayfab-smart-factory)을 연다.
   `ssg-sak/displayfab-smart-factory`의 `main` 브랜치를 사용한다.
3. 저장소의 `render.yaml`을 사용하고 `DISPLAYFAB_DATABASE_URL`에 Neon 접속 문자열을 넣는다.
   `postgresql://`와 `postgresql+psycopg://`를 모두 지원한다. 비밀번호를 저장소에 넣지 않는다.
4. 배포 로그와 `/api/health`를 확인한다. `status=ok`, `db=ok`, `demo_autopilot=true`여야 한다.
5. 발급된 실제 `https://…onrender.com` 주소에서 아래 읽기 전용 점검을 실행한다.
   통과한 실제 주소만 README의 공개 시연 항목에 기록한다.

```powershell
python backend/scripts/check_deployment.py --base https://실제서비스주소.onrender.com
```

`DISPLAYFAB_ADMIN_TOKEN`은 Render가 생성한다. 브라우저 화면에 노출하지 않으며,
직접 초기화할 때만 `X-Admin-Token` 헤더로 보낸다.

Render 설정: [Blueprint](https://render.com/docs/blueprint-spec),
[Docker](https://render.com/docs/docker), [Health checks](https://render.com/docs/health-checks).
`sync: false`인 DB 연결 값은 Blueprint 최초 생성 시 입력한다. 기존 서비스라면 Environment에서 직접 설정한다.

## 동시 실행과 검증 범위

자동 시연, HTTP 쓰기, 통신 끊김 판정은 같은 실행 잠금을 사용한다.
초기화 요청은 진행 중인 시연의 마지막 커밋까지 기다린다. 상태 확인 등 읽기 요청은 계속 처리한다.
잠금과 요청 제한은 프로세스 메모리에 있으므로 **앱 1개 인스턴스, Uvicorn worker 1개**로 운영한다.
같은 시연 DB를 두 앱에서 동시에 사용하거나 여러 replica로 확장하지 않는다.
Docker 시작 명령에 `--workers 1`을 명시했다.

검증은 구분해서 수행한다.

```powershell
# SQLite 기반 자동 테스트: backend 폴더에서 실행
python -B -m pytest -q -p no:cacheprovider

# 실제 HTTP 시연: 자동 시연을 끈 별도 검증 서버에서 실행
python backend/scripts/demo_check.py --base http://127.0.0.1:8097

# 아래 명령은 대상 시연 데이터를 삭제한다. 시연 전용 DB에만 사용한다.
# 관리자 인증과 OLED/LCD 시연-초기화 동시 요청을 검증한다.
python backend/scripts/check_deployment.py --base http://127.0.0.1:8097 --exercise --admin-env-file .env.demo
```

자동 시연을 켠 서버에서는 6초마다 생존신호, 30초 간격으로 시연을 수행하고 주기적으로 데이터를 초기화한다.
불량·조건 불일치 시나리오의 `INSPECT_FAIL`, `RECIPE_MISMATCH`, `LOT_HOLD` 로그는 의도된 시연 결과다.
`Traceback`, `ObjectDeletedError`, `demo autopilot ... failed`는 운영 오류로 구분한다.

## 검증 기록 (2026-09-20 ~ 2026-09-21)

- SQLite 자동 테스트: 98개 통과. HTTP 시연/백그라운드 시연과 수동 초기화의 경합 재현 포함.
- Docker + PostgreSQL 실제 HTTP 시연: 41개 통과.
- 자동 시연을 켠 PostgreSQL 서버: 초기화와 OLED 합격·불량/LCD 시연을 동시에 요청하는 4회 반복 검증 통과.
- 장시간 검증 로그: 자동 초기화 427회, Python traceback 및 백그라운드 작업 실패 0건 확인.
- 관리자 토큰 없는 초기화는 403, 요청 상한 초과는 429와 Retry-After 반환. 읽기 health API는 200 유지.
- Edge 헤드리스 브라우저: 운전·생산·작업·알람·이력 5개 화면 200, 시연 배너 표시, JavaScript 오류 0건.
- 최종 로컬 설정: 8098 포트, 별도 시연 DB, 자동 시연 활성화, 초기화 간격 60분, 앱·DB 컨테이너 healthy.
- 2026-09-21 공개 HTTPS 검증: `https://displayfab-smart-factory.onrender.com`의 화면·정적 파일·OpenAPI 정상 응답.
  `/api/health`에서 `status=ok`, `db=ok`, `demo_autopilot=true`, 설비 8대 ONLINE 확인.
  공개 서버 검증은 읽기 전용으로 수행했으며, 시연 데이터 초기화나 쓰기 부하 검증은 하지 않았다.
