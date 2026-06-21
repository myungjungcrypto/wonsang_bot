# 집 PC(Windows) 레지덴셜 프록시 셋업 (처음부터)

업비트 공지 API(`api-manager.upbit.com`)는 데이터센터 IP를 Cloudflare로 차단한다.
집 인터넷(가정용 KR IP)을 **SSH 리버스 터널**로 EC2에 빌려줘서 우회한다.
EC2(`ec2-user@43.201.222.151`)는 이미 셋업돼 있고, **새 PC에서만** 아래를 진행한다.

```
[집 PC(WSL): tinyproxy@127.0.0.1:8888]
        ▲                          │ outbound SSH (-R)
        │  HTTPS CONNECT(내용 못 봄) │
[EC2: 127.0.0.1:8888] ◀────────────┘   ← 봇이 HTTP_PROXY_URL 로 사용
```

## 보안 요약
- 집 공유기에 여는 포트 0개(집→EC2 바깥 연결만). 외부 스캔 불가.
- 프록시는 집 PC **localhost 전용** 바인딩.
- HTTPS는 프록시가 `CONNECT`로 통째 터널 → **내용(키·응답) 복호화 불가**.
- 위생: 집 PC OS 최신화, EC2 SSH 키 인증만.

---

## A. 새 PC(Windows) 기본 셋업

### A-1. WSL 설치 — **관리자 권한 PowerShell**
```powershell
wsl --install -d Ubuntu
```
→ **재부팅** → 우분투 창에서 **사용자 이름/비밀번호** 설정.
(이후 프롬프트가 `user@DESKTOP-xxxx:~$` 면 WSL 안)

### A-2. 도구 설치 — **WSL(우분투)에서**
```bash
sudo apt update && sudo apt install -y tinyproxy autossh openssh-client
```
> sudo 비번 입력 시 화면에 아무것도 안 보이는 게 정상. 그냥 치고 Enter.

### A-3. SSH 키 생성 — **WSL에서** (PowerShell 말고!)
```bash
ssh-keygen -t ed25519 -f ~/.ssh/wonsang_ec2 -C "wonsang-proxy"
# "Enter passphrase" → 그냥 Enter 두 번(암호 없이)
cat ~/.ssh/wonsang_ec2.pub
```
→ 출력된 `ssh-ed25519 AAAA... wonsang-proxy` **한 줄 전체 복사**.

## B. EC2에 새 키 등록 (기존 접속수단: 맥북 .pem 등)
맥북에서 EC2 접속 후 **EC2 안에서**:
```bash
echo "ssh-ed25519 AAAA...복사한_한줄... wonsang-proxy" >> ~/.ssh/authorized_keys
```

## C. 새 PC에서 프록시 + 터널

### C-1. 접속 테스트 — **WSL에서**
```bash
ssh -i ~/.ssh/wonsang_ec2 ec2-user@43.201.222.151
```
→ `.pem` 없이 로그인되면 OK. 확인 후 `exit` 로 빠져나옴.

### C-2. tinyproxy localhost 전용 설정 + 시작 — **WSL에서**
```bash
sudo sed -i 's/^#\?Listen .*/Listen 127.0.0.1/'  /etc/tinyproxy/tinyproxy.conf
sudo sed -i 's/^#\?Port .*/Port 8888/'           /etc/tinyproxy/tinyproxy.conf
sudo sed -i 's/^#\?Allow .*/Allow 127.0.0.1/'    /etc/tinyproxy/tinyproxy.conf
sudo systemctl restart tinyproxy   # 안 되면: sudo service tinyproxy restart

pgrep -a tinyproxy
curl -s -x http://127.0.0.1:8888 https://api.ipify.org; echo   # 집 공인 IP 나오면 OK
```

### C-3. 리버스 터널 — **WSL에서** (백그라운드)
```bash
autossh -f -M 0 -N \
  -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "ExitOnForwardFailure=yes" \
  -i ~/.ssh/wonsang_ec2 \
  -R 8888:127.0.0.1:8888 \
  ec2-user@43.201.222.151

pgrep -a autossh   # 줄 나오면 실행 중
```

### C-4. ⭐ 최종 확인 — **EC2에서**
```bash
curl -s -x http://127.0.0.1:8888 https://api.ipify.org; echo          # 집 IP 나와야 함
curl -s -x http://127.0.0.1:8888 \
  "https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=5&category=trade" \
  | head -c 400; echo                                                  # JSON 나오면 우회 성공🎉
```

## D. EC2 봇에 프록시 적용 — **EC2에서**
`~/wonsang_bot/.env`:
```
HTTP_PROXY_URL=http://127.0.0.1:8888
POLL_INTERVAL_SEC=1.0
```

## E. 자동 시작 (집 PC, Task Scheduler)
- 프로그램: `wsl.exe`
- 인수:
  ```
  -d Ubuntu -e bash -lc "sudo systemctl start tinyproxy; autossh -M 0 -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -i ~/.ssh/wonsang_ec2 -R 8888:127.0.0.1:8888 ec2-user@43.201.222.151"
  ```
- "사용자 로그온 여부와 관계없이 실행" + "실패 시 다시 시작" 체크.

---

## 트러블슈팅
- **sudo 비번 까먹음**: PowerShell에서 `wsl -d Ubuntu -u root passwd user`
- **"Unit tinyproxy.service not found"**: 아직 설치 안 됨 → A-2 먼저
- **EC2 curl 이 빈 응답/refused**: 터널(autossh) 또는 tinyproxy 미실행 → C-2/C-3 확인
- **EC2 curl 에 EC2 IP(43.201…) 나옴**: 터널이 안 탄 것 → autossh 재실행
- **집 IP 바뀜**: EC2 보안그룹 SSH(22) 인바운드 허용 IP 갱신 필요할 수 있음
