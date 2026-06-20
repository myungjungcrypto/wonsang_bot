// PM2 설정 — 실시간 감지 봇(데몬)용.
//
// 이건 "상시 떠 있는" 봇(공지 폴링→감지→등급→알림)을 관리한다.
// ⚠️ collect_cases.py / backfill_cases.py 는 1회성 배치이므로 PM2에 올리지 말 것
//    (정상 종료를 PM2가 죽음으로 보고 무한 재시작함). 그건 venv에서 직접 실행.
//
// 사용:
//   python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
//   cp .env.example .env   # TELEGRAM_*, 필요시 HTTP_PROXY_URL 등 설정
//   pm2 start ecosystem.config.js
//   pm2 save
//   pm2 logs wonsang-bot

module.exports = {
  apps: [
    {
      name: "wonsang-bot",
      cwd: __dirname,
      script: "scripts/run_detector.py",
      interpreter: "./.venv/bin/python",   // venv 파이썬으로 실행
      autorestart: true,
      max_restarts: 20,
      restart_delay: 5000,                 // 죽으면 5초 후 재시작
      min_uptime: 10000,
      env: {
        PYTHONUNBUFFERED: "1",             // 로그 즉시 flush
      },
    },
  ],
};
