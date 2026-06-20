# wonsang_bot (원상봇)

업비트·빗썸 **원화(KRW) 신규상장 따리** 자동화 봇.

> 상태: **설계/계획 단계.** 상세 계획은 [`docs/PLAN.md`](docs/PLAN.md) 참고.

## 기능 (계획)

1. **원화상장 감지** — 업비트·빗썸 공지 게시 즉시 상장 코인·컨트랙트 특정
2. **등급 예측** — 대성공/성공/보통/실패/큰실패 (시총·시간대·공급분포·소셜·내러티브·팀물량·토크노믹스 + 과거 케이스 2차 검증)
3. **구매처 산정** — $10k 기준 CEX/DEX/브릿지 중 가격·유동성 최적처 추천 (→ 자동매수 확장)
4. **옮기기** — CEX 출금은 보안상 수동(준비/체크리스트 제공)
5. **판매하기** — 입금량 고려 적정 매도가 제안 (해외가 +1.5% 이상 전량 매도 목표)
6. **정리봇** — 상장 시 자동 매도(현물 / 현물-선물 헤지 모드)
7. **현선갭 플레이** — 현·선 갭 모니터·진입처 추천·임계값 자동 정리
8. **아이디어 수집** — 텔레그램 아이디어/채널에서 판단기준·기능 갱신

## 안전 원칙

- 자금 이동(특히 CEX 출금)은 **보안 우선 → 수동 실행**
- 자동화는 **추천 → 반자동(원클릭) → 자동** 순으로 단계적 적용
- CEX API 키는 **거래 전용·출금 비활성·주소 화이트리스트**

## 현재 구현 상태

- ✅ **Phase 0 골격** — 설정/로깅/저장소(SQLite)/이벤트 버스/HTTP 래퍼
- ✅ **Phase 1 감지** — 업비트·빗썸 공지 폴링 → 신규 디프 → 제목 파싱(상장여부·심볼·KRW마켓) → **컨트랙트 주소 특정** → 텔레그램 알림
  - **컨트랙트 특정**: 공지 본문에서 주소·체인 추출(EVM/Tron/Solana) + CoinGecko 교차검증·동명 티커 해소(시총순위), 본문↔코인게코 주소 일치 시 신뢰도 승격
- ✅ **Phase 2 등급 예측** — 상장 감지 시 자동으로 **대성공/성공/보통/실패/큰실패** 등급 + 근거 + 신뢰도 산출 → 텔레그램 추천
  - **피처**: 시간대(timing)·내러티브(narrative)·공급병목(supply) 은 이벤트만으로 계산, 시총(marketcap)·소셜(social)은 데이터 provider 연결 시 활성(없으면 우아하게 비활성·신뢰도만 하락)
  - **스코어링**: 가용 피처 가중합 → 등급(임계값 조정 가능), 데이터 부족은 신뢰도로 표현
  - **2차 검증**: 과거 케이스 DB와 최근접 이웃 비교로 2차 등급 제시
  - **백필 파이프라인**: 과거 상장기록(JSON) → 라이브와 **동일한 피처 추출기로 재구성** + 실현수익률→등급 라벨 → `cases` 저장 (`scripts/backfill_cases.py`). 데이터만 채우면 2차검증·캘리브레이션 가동
- ⏳ 다음: Phase 3 구매처 산정($10k CEX 추천) — 이때 시세/온체인 provider 연결

> ⚠️ 거래소 공지 **엔드포인트/응답 스키마와 제목 포맷은 라이브에서 재검증 필요**
> (개발 환경은 아웃바운드 망 차단). 어댑터 파싱부는 픽스처로 테스트됨.

## 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # requests
cp .env.example .env                      # 값 채우기 (TELEGRAM_*, 필요시 프록시 등)
python scripts/run_detector.py
```

- 기본은 `TELEGRAM_DRY_RUN=true`(전송 대신 로그), `LLM_ENABLED=false`.
- 첫 실행은 기존 공지를 알림 없이 `seen` 처리(과거 공지 폭탄 방지).
- AWS EC2 운영 시 **서울 리전(ap-northeast-2)** 권장. 차단되면 `HTTP_PROXY_URL`로 국내 프록시 주입.

## 과거 케이스 수집 → 백필 (등급 예측 2차 검증용)

**1) 수집** (망 허용 환경 / 서울 IP 권장 — 거래소 공지는 해외 IP 차단 잦음):
```bash
COINGECKO_ENABLED=true python scripts/collect_cases.py [출력.json]
# 옵션: COLLECT_PAGES=20 COLLECT_WINDOW_H=48 COLLECT_SLEEP=1.5
```
- 업비트 공지 아카이브를 훑어 과거 원화상장을 찾고, **국내 KRW 캔들**로 실현수익률, (선택)코인게코로 시총 스냅샷을 모아 `cases_collected.json` 생성.
- **라벨 방법론**: 상장 **+5분 매수** → 상장 직후 **+15분 시점 매도(고점 아님)** 수익률 → 대성공 ≥25% / 성공 10~25% / 보통 0~10% / 실패 -10~0% / 큰실패 ≤-10%. (`COLLECT_ENTRY_MIN`/`COLLECT_EXIT_MIN`로 조정)
- 해외 서버라면 `.env`의 `HTTP_PROXY_URL`로 국내 프록시 주입. (서울 EC2면 보통 그대로 동작)

**2) 백필** (오프라인 가능):
```bash
python scripts/backfill_cases.py data/cases_collected.json
```
- 각 케이스를 **라이브와 동일한 피처 추출기**로 재구성 + 실현수익률→등급 라벨 → `cases` 저장.
- 저장된 케이스는 다음 실행부터 등급 예측의 **2차 등급(최근접 이웃)** 에 자동 반영.
- `data/cases_seed.example.json` 은 형식 설명용 템플릿(합성값).

> 수집기 순수 로직(수익률 계산·페이지네이션·조립)은 stdlib 단위테스트로 검증됨.
> 거래소 엔드포인트/스키마는 라이브에서 재검증 필요(어댑터 파싱부 격리).

## 테스트

```bash
PYTHONPATH=src python -m unittest discover -s tests   # 의존성 없이 동작(stdlib)
```

## 개발

- Python 3.11 / asyncio, 핵심 로직은 표준 라이브러리, HTTP는 `requests`
- 구조: `src/wonsang_bot/{config,core,detector,resolver,predictor,collector,llm,notify,storage}`
- 자세한 스택·로드맵: [`docs/PLAN.md`](docs/PLAN.md)
