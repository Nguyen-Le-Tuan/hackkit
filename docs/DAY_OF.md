# SỔ TAY NGÀY THI: AI_FOR_GOOD

Đây là **file duy nhất** bạn cần mở trong suốt cuộc thi. Đi từ trên xuống dưới, tick `[x]` khi xong.
Mọi lệnh đều đã điền sẵn tên, chỉ việc copy–paste. Lệnh nào lỗi: xem **mục 8**.

- Phần **mục 5** do công cụ tự sinh từ `docs/TASKS.md` (`make lanes`): ai làm gì, việc nào song song,
  ai chờ ai, lệnh và lời nhắc cho từng người. Đừng sửa tay trong khối đó.
- Mở file này bằng trình soạn thảo có xem trước Markdown. Muốn xem đẹp trên trình duyệt: commit + push,
  rồi mở `https://github.com/Nguyen-Le-Tuan/AI_FOR_GOOD/blob/main/docs/DAY_OF.md`.

## 1. Thông tin cố định

| Mục | Giá trị |
|---|---|
| Repo của đội | `Nguyen-Le-Tuan/AI_FOR_GOOD` (private), tạo từ template `Nguyen-Le-Tuan/hackkit` |
| Thư mục trên máy tôi | `~/Desktop/AI_FOR_GOOD` (worktree kế hoạch: `~/Desktop/AI_FOR_GOOD-agent`) |
| **Tôi** | `Nguyen-Le-Tuan`: điều phối, hỏi đối tác, review và merge PR |
| **Anh-08** | dùng **Claude Code**, cũng lo pitch/Devpost, **xác nhận đội ở bàn tiếp tân**, **người merge dự phòng** |
| **NguyenQBao** | dùng **Codex**, cũng lo QA/chạy demo, **đi hỏi đối tác** (B3) |

Nếu ai đổi công cụ hoặc vai trò: sửa bảng **Team** trong `docs/TASKS.md`, rồi `make lanes`.

## 2. Tối hôm trước

- [ ] Đăng nhập đủ: `claude --version`, `codex login status`, `gh auth status` đều báo đã đăng nhập.
- [ ] Có khóa Groq (nằm trong console Groq, **không** dán vào chat hay commit).
- [ ] Template đang xanh: `gh run list -R Nguyen-Le-Tuan/hackkit --limit 1` ra `completed success`.
- [ ] Tên repo còn trống: `gh repo view Nguyen-Le-Tuan/AI_FOR_GOOD` phải báo lỗi `Could not resolve`.
- [ ] Preflight thử trong repo template: `cd ~/Desktop/hackkit && ./scripts/orchestrate.sh --check --lecturebridge`
      (cần LectureBridge đang chạy, xem A2). Phải qua hết. Nếu `.env` của template còn khóa, `--check` chỉ
      **cảnh báo**; ở repo thi, chạy thật sẽ bị **chặn** nếu `.env` có khóa (xem A5).
- [ ] (Tùy chọn) Phương án chạy cục bộ nếu đối tác không cho gửi dữ liệu sang dịch vụ AI: cài Ollama và kéo
      một model nhỏ (hiện **chưa cài**).
- [ ] Nhắn Anh-08 và NguyenQBao: có tài khoản GitHub, đã đăng nhập agent của mình (`claude` hoặc `codex`),
      mang laptop sạc đầy, có Python 3.11+ và `make`.
- [ ] Laptop: sạc đầy, tắt cập nhật tự động, đóng ứng dụng không cần.

## 3. Tại địa điểm: trước khi rời phòng (khoảng 15 phút)

**A1. Cắm sạc, kiểm tra mạng.**
- [ ] `ping -c 2 github.com` (có phản hồi).

**A2. Bật LectureBridge (terminal 1, để chạy suốt).**
```bash
cd ~/lecturebridge/lecturebridge
.venv/bin/python -m lecturebridge.live \
  --device cuda \
  --model distil-large-v3.5 \
  --language en \
  --data-dir /home/nguyenletuan/Desktop
```
- [ ] Mở `http://127.0.0.1:8000`, **bật lưu bản ghi**, đặt laptop gần loa.
- [ ] Kiểm tra (terminal 2): `curl -s http://127.0.0.1:8000/health` (thấy `"status":"ok"`).
Script chỉ đọc phiên đang ghi qua API, nên nơi lưu file không quan trọng.

**A3. Tạo repo của đội từ template và clone (terminal 2).**
```bash
cd ~/Desktop && gh repo create AI_FOR_GOOD --template Nguyen-Le-Tuan/hackkit --private --clone
```
- [ ] `ls ~/Desktop/AI_FOR_GOOD` thấy `README.md`, `docs`, `scripts`...

**A4. Mời 2 bạn.**
```bash
for u in NguyenQBao Anh-08; do gh api -X PUT repos/Nguyen-Le-Tuan/AI_FOR_GOOD/collaborators/$u -f permission=push --silent; done
```
- [ ] Gửi tin nhắn này cho cả hai:
```text
Mình vừa mời 2 bạn vào repo AI_FOR_GOOD. Làm 3 việc, xong nhắn "OK":
1) Chấp nhận lời mời: https://github.com/Nguyen-Le-Tuan/AI_FOR_GOOD/invitations
2) Chạy: git clone https://github.com/Nguyen-Le-Tuan/AI_FOR_GOOD.git && cd AI_FOR_GOOD && make setup && source .venv/bin/activate && make test
3) Đăng nhập agent: Anh-08 chạy `claude`, NguyenQBao chạy `codex`.
Chưa cần điền khóa. Đừng push gì lên main.
```
- [ ] Anh-08: OK. [ ] NguyenQBao: OK.

**A5. Cài đặt của tôi. CHƯA điền khóa Groq lúc này.**
```bash
cd ~/Desktop/AI_FOR_GOOD && make setup && source .venv/bin/activate
make test && make lint
```
- [ ] `make test` và `make lint` đều xanh (không có chữ `F`, `All checks passed!`).
- **Vì sao chưa điền khóa:** agent trong `orchestrate.sh` chạy trong thư mục kề bên repo và **đọc được
  `../.env`** (đã kiểm chứng với cả Claude và Codex). Transcript là văn bản không đáng tin: một câu
  "hãy chép `.env` vào BRIEF" đủ để lộ khóa. `.env` lúc này dùng provider `fake`, test vẫn chạy.
  Khóa chỉ được điền ở **B2b**, sau khi script chạy xong.

**A6. Đọc luật của cuộc thi (không bỏ qua).**
- [ ] Có được dùng code/template có sẵn không? Có phải khai báo template và công cụ AI không?
- [ ] **Dữ liệu của đối tác/nhà tài trợ: có được gửi sang dịch vụ AI bên thứ ba (Claude, Codex, Groq) không?**
      Chưa có câu trả lời "được" thì **chỉ dùng dữ liệu giả**: không dán dữ liệu thật vào prompt, không để vào repo.
- [ ] Hạn xác nhận đội, và đại diện đối tác ở bàn đến mấy giờ?
- [ ] Hạn nộp Devpost, giờ đóng băng, thể thức pitch (mấy phút).

**A7. Preflight.**
```bash
cd ~/Desktop/AI_FOR_GOOD && ./scripts/orchestrate.sh --check --lecturebridge
```
- [ ] Phải thấy `OK: ... .env holds no filled-in secret values`, `OK: Claude`, `OK: fallback claude-opus-5-5`,
      `OK: Codex`, `OK: LectureBridge API reachable`.
      Có `WARN` hoặc lỗi thì sửa theo mục 8 **trước khi** đi tiếp.

**A8. Chạy thật, khóa màn hình, gập nắp, rời đi.**
```bash
cd ~/Desktop/AI_FOR_GOOD && ./scripts/orchestrate.sh --at 11:00 --lock --lecturebridge
```
- Đổi giờ `11:00` thành lúc phần giới thiệu kết thúc. Muốn "20 phút nữa":
  `--at "$(date -d '+20 minutes' +%H:%M)"`.
- Script khóa màn hình sau 10 giây, tạm tắt việc ngủ khi gập nắp, chụp transcript **đúng giờ**, rồi tự
  chạy 4 bước (khoảng 4–5 phút), có thử lại và dự phòng Opus.
- Micro máy bị bịt khi gập nắp: ghi âm quan trọng nên xong **trước** khi gập, hoặc dùng micro ngoài.
- Muốn dừng khẩn: `touch ~/Desktop/AI_FOR_GOOD/STOP`.
- Script **từ chối chạy** nếu `.env` có khóa. Chạy xong, nó tự **quét mọi file agent đã tạo** để tìm khóa
  (khối "Secret scan" trong `STATUS.md`).
- [ ] Đã thấy dòng `Locking the session` trước khi gập nắp.

## 4. Khi quay lại: bước 10, 11, 12 (tôi tự review và khóa quyết định)

**B1. Mở khóa, kiểm tra máy.**
- [ ] `gsettings get org.gnome.settings-daemon.plugins.power lid-close-ac-action` ra `'suspend'`
      (nếu ra `'nothing'`: `bash ~/.cache/orchestrate_lid_restore.sh`).

**B2. Đọc kết quả của máy (bước 10).**
```bash
cd ~/Desktop/AI_FOR_GOOD-agent/docs/agent
cat STATUS.md
less BRIEF.md        # q để thoát
less PLAN_REVIEW.md  # checklist 5 dòng ở cuối
```
- [ ] `STATUS.md`: có dòng `DONE`, cả 4 file có dấu `[x]`, không có file nào bị sửa ngoài `docs/agent`.
- [ ] **Khối "Secret scan" phải là `clean`.** Xem nhanh: `grep -A4 "Secret scan" STATUS.md`. Nếu có `ALERT`:
      **không merge** `agent/plan` (xem mục 8).
- [ ] `BRIEF.md`: đúng **challenge của đội**, **trọng số giám khảo**, **hạn chót**, **luật**, **API đối tác**.
- [ ] Mục "Uncertain or missing" của BRIEF: ghi lại để hỏi đối tác.
- Nếu BRIEF báo **không có nội dung kickoff**: âm thanh sai hoặc chưa đủ. Chạy lại khi đã có nội dung:
  `cd ~/Desktop/AI_FOR_GOOD && ./scripts/orchestrate.sh --now --lecturebridge`

**B2b. Điền khóa Groq. CHỈ khi `STATUS.md` có `DONE` và Secret scan `clean`.** Khóa không hiện trên màn hình
và không nằm trong lịch sử lệnh:
```bash
cd ~/Desktop/AI_FOR_GOOD && read -rsp "Dán khóa Groq rồi Enter: " K && echo && sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=groq|; s|^GROQ_API_KEY=.*|GROQ_API_KEY=$K|" .env && unset K
```
- [ ] Đã điền khóa. (Chạy lại `orchestrate.sh` sau này thì phải xóa khóa khỏi `.env` trước.)

**B3. Song song: hỏi đối tác (NguyenQBao) và xác nhận đội (Anh-08), trong lúc tôi làm B2 và B4.**
Đại diện đối tác có thể rời sớm: gửi ngay, đừng chờ tôi đọc xong BRIEF.
- [ ] Gửi **NguyenQBao** (nhớ thêm các câu trong mục "Uncertain or missing" của `BRIEF.md`):
```text
@NguyenQBao: đi hỏi đại diện đối tác ngay, ghi lại NGUYÊN VĂN câu trả lời, gửi lại trong 10 phút:
1) Dữ liệu/API họ cung cấp là gì, lấy ở đâu? Có được gửi sang Claude/Codex/Groq (dịch vụ AI bên thứ ba) không?
2) Người dùng thật của họ là ai, và hôm nay họ làm việc đó như thế nào?
3) Điều họ muốn thấy nhất trong một bản demo?
4) Ràng buộc hay luật riêng của challenge này? Nộp bài thế nào?
5) (dán thêm các câu từ BRIEF.md, mục "Uncertain or missing")
```
- [ ] Gửi **Anh-08**: `@Anh-08: ra bàn tiếp tân xác nhận đội mình và challenge, hỏi giờ hạn xác nhận. Báo lại kết quả.`
- [ ] Đã có câu trả lời của đối tác (ghi vào đây): ______

**B4. Chọn plan (bước 11, khoảng 10 phút, cả 3 người cùng quyết, sau khi có câu trả lời ở B3).**
- [ ] Tiêu chí: (1) khớp trọng số giám khảo, (2) một người dùng, một đường demo rõ, (3) dùng dữ liệu/API
      của nhà tài trợ nếu có, (4) làm trọn trong thời gian còn lại, (5) demo ổn định, không phụ thuộc may rủi.
- [ ] Plan đã chọn: ______ (ghi vào đây)

**B5. Đưa tài liệu kế hoạch vào `main`.**
```bash
cd ~/Desktop/AI_FOR_GOOD && git switch main && git merge agent/plan
```

**B6. Soạn `docs/spec.md` (tôi duyệt từng dòng).** Mở Claude Code trong repo (`claude`) rồi dán, thay `X`
bằng plan đã chọn:
```text
Đọc docs/agent/BRIEF.md, docs/agent/PLAN_REVIEW.md, docs/agent/PLANS.md. Tôi chọn Plan X, bản rút gọn
trong PLAN_REVIEW. Soạn docs/spec.md theo đúng 6 mục của file mẫu, thêm câu trả lời của đối tác dưới
đây (kể cả việc dữ liệu có được gửi sang dịch vụ AI không): <dán câu trả lời>. Chỉ ghi điều có trong tài liệu hoặc câu trả lời, ghi rõ chỗ chưa chắc.
Không viết code.
```
- [ ] Đã đọc và sửa `docs/spec.md` (vấn đề, **một** người dùng, đường demo từng bước, ngoài phạm vi).

**B7. Điền `AGENTS.md` (khối Project) và `docs/TASKS.md` (bước 12: khóa hợp đồng).** Vẫn trong Claude Code:
```text
Từ docs/spec.md: (1) điền khối "Project (FILL ON EVENT DAY)" trong AGENTS.md; (2) điền docs/TASKS.md:
Contract (feature key, schema, rules, file mẫu, eval) và bảng Tasks theo bốn việc của Plan X trong
PLAN_REVIEW. Giữ nguyên bảng Team. Quy ước: T1 là khung đăng ký tính năng, merge trong ~10 phút;
việc nào chỉ cần T1 để chạy eval thì ghi phụ thuộc mềm `T1~`; các việc chạy song song phải sửa file
KHÁC nhau. Không viết code.
```
- [ ] Đã đọc kỹ **Contract** và cột **Files it may touch**. Hai việc cùng đợt không được trùng file.
- [ ] Bảng **Team** đúng người, đúng công cụ.
- [ ] `docs/PITCH.md`: điền tiêu chí giám khảo và "khoảnh khắc demo chiến thắng".

**B8. Khóa quyết định và sinh luồng việc.**
```bash
cd ~/Desktop/AI_FOR_GOOD && make lanes
git add -A && git commit -m "docs: spec, tasks, luồng việc" && git push origin main
```
- [ ] `make lanes` không báo cảnh báo `⚠` (nếu có: sửa `docs/TASKS.md` rồi chạy lại).

**B9. Giao việc.** Mở **mục 5**, copy "Tin nhắn cho nhóm chat" gửi cả nhóm. Mỗi người chạy lệnh trong phần
của mình. Hai bạn đã clone từ A4 nên chỉ cần `git pull origin main` trước.
- [ ] Đã gửi tin nhắn giao việc.

## 5. LUỒNG VIỆC HIỆN TẠI (tự sinh, đừng sửa tay)

<!-- LANES:START -->
Chưa có dữ liệu. Sau bước **B8** chạy `make lanes`: khối này sẽ hiện ai làm gì, việc nào song song,
ai chờ ai, và lệnh/lời nhắc copy–paste cho từng người.
<!-- LANES:END -->

## 6. Vòng lặp điều phối của tôi

Mỗi khi có thay đổi, cập nhật trạng thái **một dòng** rồi đọc lại mục 5 (phần "Ngay bây giờ"):

| Sự kiện | Lệnh |
|---|---|
| Ai đó báo bắt đầu một việc | `make lanes SET="T1=doing"` |
| Ai đó mở PR | `make lanes SET="T1=review"` |
| Tôi merge PR xong | `make lanes SET="T1=merged"` rồi báo người đang chờ (mục 5 liệt kê) |
| Nhiều thay đổi cùng lúc | `make lanes SET="T1=merged T2=doing"` |

Quy trình mỗi PR:
```bash
cd ~/Desktop/AI_FOR_GOOD
gh pr list
gh pr checks <số PR> --watch          # chỉ merge khi xanh
gh pr merge <số PR> --merge
git switch main && git pull origin main && make test && make lint
```
- PR chậm hơn `main`? `gh api -X PUT repos/Nguyen-Le-Tuan/AI_FOR_GOOD/pulls/<số PR>/update-branch --silent`.
  ("Re-run jobs" không giúp vì dùng lại bản ghép cũ.)
- **Người merge dự phòng: Anh-08.** Khi tôi bận (hỏi đối tác, trình bày), Anh-08 merge theo đúng quy trình
  trên. Chỉ merge PR **xanh**, **không** merge PR của chính mình, và nhắn tôi sau mỗi lần merge để tôi chạy
  `make lanes SET=...`.
- **Quy tắc song song:** chỉ chạy song song khi (1) file không chồng nhau và (2) việc phụ thuộc đã merge.
  Việc quá ngắn (dưới ~10 phút của agent) thì để một agent làm liền, đỡ tốn công PR và merge.
- Cứ khoảng 30 phút nhìn lại "Ngay bây giờ" và dọn những việc đang chờ.
- Khi mọi việc của một đợt đã merge: `make demo` chạy thử một lượt.

## 7. Đóng băng và nộp bài

- [ ] **Trước hạn 1 giờ 30 phút: đóng băng.** Chỉ sửa lỗi, không thêm tính năng.
- [ ] `make test && make lint` đều xanh.
- [ ] **Làm nóng cache bằng model thật.** Laptop trình bày **phải chính là laptop làm bước này**: cache nằm ở
      `.cache/hackkit`, chỉ có trên máy đó và không lên git.
  1. `cd ~/Desktop/AI_FOR_GOOD && source .venv/bin/activate && LLM_PROVIDER=groq make run`
  2. Ở thanh bên, bấm **Clear saved results TRƯỚC**. Cache không phân biệt provider: kết quả của provider
     `fake` đã lưu (do `make demo` hay lúc tập) sẽ bị trả lại thay cho model thật (đã kiểm chứng).
  3. Chọn provider `groq`, chạy **từng input demo một lần**. Mỗi kết quả phải ghi `N model call(s)`
     (không phải `saved result`).
  4. Bật **Demo mode** ở thanh bên rồi chạy lại từng input: phải ghi `saved result` và không dùng mạng.
     (Hoặc mở bằng `DEMO_MODE=1 LLM_PROVIDER=groq make run`.)
  5. Input chưa từng được làm nóng sẽ báo lỗi "Demo mode is on and this input has no cached result":
     chỉ trình diễn đúng các input đã chạy.
  - Sửa `INSTRUCTIONS` hoặc schema thì cache cũ tự hết hiệu lực: phải làm nóng lại.
- [ ] `make demo` chỉ chạy bản **mẫu** với provider giả (tập offline). Đó **không** phải demo thật.
- [ ] Chạy một lần `LLM_PROVIDER=groq make eval`, ghi lại độ chính xác.
- [ ] Tập pitch 3 lần, quay video demo dự phòng.
- [ ] Điền `docs/PITCH.md`, hoàn tất Devpost **trước hạn ít nhất 30 phút**, ghi rõ đã dùng template
      `hackkit` và các công cụ AI.
- [ ] Thành viên đã được liệt kê, bài nộp đã bấm "submit".

## 8. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `make test`: `pytest: not found` | Chưa kích hoạt môi trường ảo | `source .venv/bin/activate` |
| `--check`: Codex lỗi đăng nhập hoặc model | Chưa đăng nhập hoặc bản cũ | `codex login`, `codex --version` |
| `--check`: Claude lỗi | Chưa đăng nhập | chạy `claude` một lần và đăng nhập |
| `--check`: LectureBridge không truy cập được | App chưa chạy | làm lại A2 |
| Script chờ rồi báo "no ... status=recording" | Chưa bật lưu bản ghi hoặc đã dừng ghi | bật ghi âm rồi chạy lại `--now` |
| BRIEF nói không có nội dung kickoff | Sai âm thanh hoặc chưa đủ | chạy lại `./scripts/orchestrate.sh --now --lecturebridge` |
| Màn hình sau khi gập nắp: máy ngủ | Cài đặt gập nắp chưa được chặn | rà lại A8, chạy `bash ~/.cache/orchestrate_lid_restore.sh` nếu cần |
| CI đỏ ở bước `ruff format` | Code mới chưa chuẩn | `make fmt` rồi commit |
| CI đỏ sau khi thêm tính năng | Test giả định thứ tự tính năng | báo tôi, không tự sửa test của template |
| PR đỏ sau khi `main` thay đổi | Nhánh lạc hậu | cập nhật nhánh (mục 6), không bấm "Re-run" |
| `git push` bị từ chối | Có người push trước | `git pull --rebase origin main` rồi push lại, **không** force-push |
| Xung đột khi merge | Hai người sửa cùng file | dừng lại, báo tôi; đừng tự giải quyết |
| PR do bot (Copilot) tự mở | Bot sửa CI tự động | đóng PR đó, không merge |
| Agent sửa file ngoài phạm vi việc | Lời nhắc chưa chặt | `git checkout -- <file>`, nhắc lại "chỉ sửa các file: ..." |
| Demo hiện kết quả mẫu thay vì model thật | Cache chứa kết quả của provider `fake` | Bấm **Clear saved results**, làm nóng lại bằng `groq` (mục 7) |
| Demo mode báo `no cached result` | Input chưa được làm nóng | tắt Demo mode, chạy input đó với `groq` một lần, bật lại |
| `orchestrate.sh`: `.env holds filled-in keys` | `.env` có khóa lúc chạy | đặt lại `GROQ_API_KEY=` (để trống), chạy lại, điền khóa ở B2b |
| `STATUS.md`: Secret scan `ALERT` | Agent chép khóa vào tài liệu | **không** merge: `git worktree remove --force ../AI_FOR_GOOD-agent && git branch -D agent/plan`; thu hồi khóa trong console; bỏ khóa khỏi `.env` rồi chạy lại |
| Lỡ làm lộ khóa API | Dán nhầm vào chat/commit | thu hồi khóa trong console Groq ngay, tạo khóa mới |

## 9. Nhật ký (điền giờ thật, dùng cho lần sau)

| Mốc | Giờ |
|---|---|
| Bắt đầu ghi âm | |
| Tạo xong repo, mời 2 bạn | |
| `orchestrate.sh` khởi chạy | |
| Quay lại, đọc xong kế hoạch | |
| Chốt plan, `make lanes` lần đầu | |
| PR đầu tiên được merge | |
| Đóng băng | |
| Nộp Devpost | |

Bài học trong ngày (viết vào đây, sau cuộc thi đưa vào template):
-
