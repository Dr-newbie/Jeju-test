# Travel Route Planner MVP

네이버 지도/검색 API와 간단한 경로 최적화 알고리즘을 사용하는 여행 루트 플래너 MVP입니다.

## 기능

- 네이버 지역 검색 API로 장소 검색
- 네이버 Geocoding API로 주소 -> 좌표 변환
- 장소 카테고리 추론
- N일차 여행 루트 자동 생성
- 숙소 시작 기준 날짜별 route 생성
- 권역(landmark) 시딩 KMeans 기반 날짜 분배
- nearest-neighbor + 2-opt 기반 하루 경로 최적화
- 1일차 공항 출발 / 마지막날 공항 도착, 중간 날짜는 그날 숙소 기준 왕복
- 저녁 식사 후보 중 횟집/돼지고기 계열 우선 선택
- Next.js + Naver Maps JavaScript API 지도 표시
- 생성한 루트를 DB에 저장하고 공유 링크 발급
- 날짜별 동선 주변 카테고리별 추천 (네이버 지역 검색 기반, 별점 데이터는 제공되지 않음)

## Backend 실행

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env에 네이버 API 키 입력
uvicorn main:app --reload --port 5001
```

`DATABASE_URL`을 지정하지 않으면 로컬에서는 `backend/dev.db`(SQLite)로 자동 저장됩니다. 배포 환경에서는 Postgres를 붙여야 재시작 후에도 공유 링크가 유지됩니다 (아래 배포 섹션 참고).

## Frontend 실행

```bash
cd frontend
npm install
cp .env.local.example .env.local
# .env.local에 Naver Map Client ID 입력
npm run dev
```

접속:

```text
http://localhost:3000
```

## 주의

현재 MVP는 직선거리 기반입니다. 실제 서비스 수준으로 가려면 Naver Directions API 또는 별도 distance matrix를 붙이는 것이 좋습니다.

## 배포 (다른 사람도 접속 가능하게)

프론트(Next.js)는 Vercel, 백엔드(FastAPI)는 Render에 각각 배포하는 구성을 기준으로 합니다.

### 1. GitHub에 push

```bash
git remote add origin <your-repo-url>
git push -u origin master
```

### 2. 백엔드 (Render)

1. Render에서 New > Web Service > 이 repo 선택, Root Directory를 `backend`로 지정
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT` (Procfile에 이미 정의되어 있음)
4. Environment 탭에서 아래 값을 등록 (로컬 `.env`는 커밋되지 않으므로 반드시 여기서 다시 입력):
   - `NAVER_MAP_CLIENT_ID`, `NAVER_MAP_CLIENT_SECRET`
   - `NAVER_SEARCH_CLIENT_ID`, `NAVER_SEARCH_CLIENT_SECRET`
   - `ALLOWED_ORIGINS` = 배포될 Vercel 프론트 도메인 (예: `https://your-app.vercel.app`)
5. 배포 후 발급되는 URL을 기록 (예: `https://your-backend.onrender.com`)

#### Postgres 연결 (공유 링크 저장용)

공유 링크 기능은 DB가 있어야 재배포/재시작 후에도 유지됩니다.

1. Render 대시보드 > New > PostgreSQL로 무료 DB 인스턴스 생성 (무료 티어는 90일 후 만료되니 알아두기)
2. 생성된 Postgres의 **Internal Database URL**을 복사
3. 위에서 만든 Web Service의 Environment 탭에 `DATABASE_URL`로 등록
4. 재배포되면 앱 시작 시 자동으로 테이블이 생성됩니다 (`main.py`의 startup 훅)

### 3. 프론트엔드 (Vercel)

1. Vercel에서 New Project > 이 repo 선택, Root Directory를 `frontend`로 지정
2. Environment Variables에 등록:
   - `NEXT_PUBLIC_BACKEND_URL` = 2번에서 발급된 Render 백엔드 URL
   - `NEXT_PUBLIC_NAVER_MAP_CLIENT_ID` = NCP Maps Client ID
3. Deploy

### 4. NCP 콘솔 설정 갱신 (필수)

Naver Cloud Platform 콘솔 > AI·NAVER API > Application에서 사용 중인 Maps 애플리케이션을 열고:

- **Web 서비스 URL**에 배포된 Vercel 도메인(`https://your-app.vercel.app`)을 추가로 등록
- **API 선택**에 `Dynamic Map`이 체크되어 있는지 확인

이 등록이 없으면 로컬에서는 되던 지도가 배포 후 "인증 실패"로 다시 막힙니다.

### 5. 확인

배포된 Vercel URL을 휴대폰 브라우저로 열어서 검색 → 장소 추가 → 루트 생성 → 지도 표시까지 되는지 확인합니다.
