# 집 PC(Windows) 레지덴셜 프록시 셋업

업비트 공지 API(`api-manager.upbit.com`)는 AWS 같은 데이터센터 IP를 Cloudflare로
차단한다. 집 인터넷(국내 가정용 IP)을 **SSH 리버스 터널**로 EC2에 빌려줘서 우회한다.

```
[집PC(WSL): tinyproxy@127.0.0.1:8888]
        ▲                         │ outbound SSH (-R)
        │  HTTPS CONNECT (내용 못 봄)│
[EC2: 127.0.0.1:8888] ◀───────────┘   ← 봇이 HTTP_PROXY_URL 로 여기 사용
```

## 보안 요약
- **집 공유기에 여는 포트 0개** (집 PC가 EC2로 바깥으로만 연결). 외부 스캔 불가.
- 프록시는 집 PC **localhost 전용** 바인딩.
- 업비트/거래소는 **HTTPS** → 프록시는 `CONNECT`로 통째 터널만, **내용(키·응답) 복호화 불가**.
- 남는 위생: 집 PC OS 최신화, EC2 SSH 키 인증만(비번 끄기).

---

## 1) 집 PC: WSL2 설치 (PowerShell 관리자)
```powershell
wsl --install -d Ubuntu
# 재부팅 후 Ubuntu 사용자/비번 설정
```

## 2) WSL(우분투) 안에서 프록시 + 터널 도구
```bash
sudo apt update && sudo apt install -y tinyproxy autossh openssh-client

# tinyproxy 를 localhost 전용으로
sudo sed -i 's/^#\?Listen .*/Listen 127.0.0.1/'  /etc/tinyproxy/tinyproxy.conf
sudo sed -i 's/^#\?Port .*/Port 8888/'           /etc/tinyproxy/tinyproxy.conf
sudo sed -i 's/^#\?Allow .*/Allow 127.0.0.1/'    /etc/tinyproxy/tinyproxy.conf

# EC2 접속 키(.pem)를 WSL 홈으로 복사 후 권한
#   (윈도우 경로 예: /mnt/c/Users/<나>/Downloads/jung_test.pem)
cp /mnt/c/Users/<나>/Downloads/jung_test.pem ~/jung_test.pem
chmod 600 ~/jung_test.pem
```

## 3) 프록시 + 리버스 터널 실행
```bash
tinyproxy        # localhost:8888 데몬으로 시작

autossh -M 0 -N \
  -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "ExitOnForwardFailure=yes" \
  -i ~/jung_test.pem \
  -R 8888:127.0.0.1:8888 \
  ec2-user@43.201.222.151
```
- `-R 8888:127.0.0.1:8888` = EC2의 127.0.0.1:8888 → 집 WSL의 tinyproxy 로 포워딩.
- autossh 가 끊기면 자동 재접속.

## 4) EC2: 프록시 경유 확인
다른 EC2 터미널에서:
```bash
curl -s -x http://127.0.0.1:8888 \
  "https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=5&category=trade" \
  | head -c 300; echo
```
- **JSON** 나오면 성공(아까 Cloudflare HTML → 이제 통과).

## 5) EC2: 봇에 프록시 적용
`~/wonsang_bot/.env`:
```
HTTP_PROXY_URL=http://127.0.0.1:8888
POLL_INTERVAL_SEC=1.0
```
→ 봇의 모든 외부 호출이 집 IP를 경유.

## 6) 집 PC: 자동 시작 (Task Scheduler)
- 프로그램: `wsl.exe`
- 인수:
  ```
  -d Ubuntu -e bash -lc "tinyproxy; autossh -M 0 -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -i ~/jung_test.pem -R 8888:127.0.0.1:8888 ec2-user@43.201.222.151"
  ```
- "사용자 로그온 여부와 관계없이 실행" + "실패 시 다시 시작" 체크.

---

## 대안: WSL 없이 (gost.exe + 윈도우 기본 ssh)
1. `gost.exe` 다운로드 → `gost -L http://127.0.0.1:8888` (localhost HTTP 프록시)
2. PowerShell:
   ```powershell
   ssh -N -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes `
     -i C:\path\jung_test.pem -R 8888:127.0.0.1:8888 ec2-user@43.201.222.151
   ```
3. 끊김 대비 .bat 루프 + Task Scheduler. (WSL 방식이 autossh로 더 안정적)
```
