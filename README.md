# wonsang_bot (원상봇)

업비트·빗썸 **원화(KRW) 신규상장 따리** 자동화 봇.

> 상태: **설계/계획 단계.** 상세 계획은 [`docs/PLAN.md`](docs/PLAN.md) 참고.

## 기능 (계획)

1. **원화상장 감지** — 업비트·빗썸 공지 게시 즉시 상장 코인·컨트랙트 특정
2. **등급 예측** — 대성공/성공/약성공/실패/큰실패 (시총·시간대·공급분포·소셜·내러티브·팀물량·토크노믹스 + 과거 케이스 2차 검증)
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
- ✅ **Phase 2 등급 예측** — 상장 감지 시 자동으로 **대성공/성공/약성공/실패/큰실패** 등급 + 근거 + 신뢰도 산출 → 텔레그램 추천
  - **피처**: 시간대(timing)·내러티브(narrative)·공급병목(supply)·상장유형(listing_type)은 이벤트만으로 계산, **거래소 가용성(venue_count, 백필상 최강 신호)**·**빗썸 기상장(bithumb_listed)**·시총(marketcap)·소셜(social)은 조회/provider 연결 시 활성(없으면 우아하게 비활성·신뢰도만 하락)
    - 캘리브레이션(백필 50건): venue_count 4+개소 실패율 5% vs 1개소 50%(최강 신호) / KRW만추가는 '실패'가 아니라 '중립'(실패율 8%) / 빗썸 기상장은 수집·검증 중
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
  - ⚠️ 업비트 공지 API는 **DC IP를 Cloudflare로 차단** → 집(가정용 KR IP) 프록시 필요. 셋업: [`docs/PROXY_SETUP.md`](docs/PROXY_SETUP.md)

### 상시 운영 (PM2 — 데몬)

실시간 감지 봇은 **PM2**로 띄운다(`ecosystem.config.js` 포함):
```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env
pm2 start ecosystem.config.js && pm2 save
pm2 logs wonsang-bot
```
- ⚠️ `collect_cases.py`/`backfill_cases.py`는 **1회성 배치**라 PM2에 올리지 말 것(정상 종료를 죽음으로 보고 무한 재시작). 그건 venv에서 직접 실행.

## 과거 케이스 수집 → 백필 (등급 예측 2차 검증용)

**1) 수집** (망 허용 환경 / 서울 IP + 공지 프록시 필요):

⚠️ 업비트 공지 API(`api-manager.upbit.com`)는 Cloudflare로 DC IP 차단 → **집 프록시 필요**([`docs/PROXY_SETUP.md`](docs/PROXY_SETUP.md)). 캔들(`api.upbit.com`)·해외 거래소·DEX는 직접 접근.

**권장 — 김프(따리) 모델** (`collect_kimchi_cases.py`):
```bash
COLLECT_LIMIT=50 python scripts/collect_kimchi_cases.py data/cases_kimchi.json  # 최근 50개만(빠름)
COLLECT_APPEND=1 python scripts/collect_kimchi_cases.py data/cases_kimchi.json  # 증분(새 상장만 추가)
python scripts/collect_kimchi_cases.py data/cases_kimchi.json                   # 전체 재수집
```
- 공지는 newest-first → `COLLECT_LIMIT=N`은 **최근 N건**만(가장 느린 캔들/CEX/DEX/코인게코 호출이 N건으로 제한). 분석도 보통 최근 50건 기준이라 `COLLECT_LIMIT=50`이면 충분.
- `COLLECT_APPEND=1`은 기존 파일의 이미 수집한 종목을 건너뛰고 **새 상장만 추가**(반복 실행이 빠름).
- **매수: 공지 +5분 해외** → **매도: 업비트 상장 오픈(첫 캔들 KRW)**, 환율은 업비트 KRW-USDT.
- 매수처는 **신원이 같은 토큰**을 CEX·DEX 전체에서 찾고(가격 아님 — CEX는 코인게코 티커, DEX는 컨트랙트로 신원 확정 + 브릿지 가능한 타 체인 포함), **유동성 적은 곳은 제거**한 뒤 **남은 구매처 중 최저가**로 매수(같은 토큰이면 싼 곳이 곧 이득).
- 공지(프록시) + 업비트 캔들 + 멀티 CEX/DEX 시세 + KRW-USDT 환율을 조합한 **실제 따리 수익률**.
- 대안(참고): `collect_upbit_market.py`(마켓목록·상장후 시점매도), `collect_cases.py`(공지·국내 시점매도).

**라벨**: 대성공 ≥25% / 성공 10~25% / 약성공 0~10% / 실패 -10~0% / 큰실패 ≤-10%.

**2) 백필** (오프라인 가능):
```bash
python scripts/backfill_cases.py data/cases_kimchi.json
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
