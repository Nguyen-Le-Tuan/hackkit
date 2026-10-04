# SỔ TAY NGÀY THI

Đây là **file duy nhất** cần mở trong suốt cuộc thi. Đi từ trên xuống, tick `[x]` khi xong. Thay
`<ORG>`, `<REPO>` và tên người ở **mục 1** một lần (tìm–thay thế), sau đó mọi lệnh copy–paste được.
Lệnh lỗi: xem **mục 10**. Mục 6 do `make lanes` tự sinh từ `docs/TASKS.md`: đừng sửa tay khối đó.

## 0. Cách thắng (đọc 1 phút, cả đội)

1. **Giám khảo chấm thứ họ NHÌN THẤY.** Rubric thường có 5 mục, chỉ 1 mục là kỹ thuật. Người lo pitch
   (human-C) bắt đầu từ **phút 0**, không phải giờ cuối (`docs/pitch/README.md`).
2. **Bản xấu chạy trọn lúc T+1:30** tốt hơn bản đẹp lúc T−0:05. Deploy sớm (`make snapshot && make pages`).
3. **AI phải hiện trên sân khấu** (extract, nút Explain, ô Ask), nhưng **code giữ mọi con số**.
4. **Một con số tác động có nguồn** trên trang chủ và slide. Số minh họa thì đỏ (`demo`), nói rõ.
5. **Mốc giờ do máy canh** (`make lanes` báo TRỄ), **đóng băng bằng máy** (`make freeze`). Trễ thì cắt
   phạm vi, không dời mốc.

## 1. Thông tin cố định

| Mục | Giá trị |
|---|---|
| Repo của đội | `<ORG>/<REPO>` (**private** đến khi nộp), tạo từ template `Nguyen-Le-Tuan/hackkit` |
| Thư mục trên máy tôi | `~/Desktop/<REPO>` (worktree kế hoạch: `~/Desktop/<REPO>-agent`) |
| Hạn nộp / pitch | ______ / ______ phút (ghi giờ thật) |
| **Tôi** (human-A) | điều phối, review bằng `make verify`, merge |
| **<teammate 1>** | Claude Code, merge dự phòng |
| **<teammate 2>** | Codex, QA và chạy demo (human-B) |
| **<teammate 3>** | pitch/UX/Devpost từ phút 0 (human-C), hỏi đối tác |

Đổi người hoặc vai trò: sửa bảng **Team** trong `docs/TASKS.md`, rồi `make lanes`.

## 2. Tối hôm trước (mỗi laptop)

- [ ] Đăng nhập: `claude --version`, `codex login status`, `gh auth status`.
- [ ] Template xanh: `gh run list -R Nguyen-Le-Tuan/hackkit --limit 1` ra `completed success`.
- [ ] Công cụ pitch: `pip install -e ".[pitch]" && playwright install chromium` (thêm `ffmpeg`, LibreOffice nếu
      chưa có: `make doctor` sẽ nói).
- [ ] `make doctor` không có `FAIL`. Laptop: sạc đầy, tắt cập nhật tự động.
- [ ] Có khóa API (Anthropic hoặc Groq) trong console của nhà cung cấp. **Không** dán vào chat hay commit.
- [ ] (Tùy chọn) Ollama + một model nhỏ, nếu đối tác cấm gửi dữ liệu sang dịch vụ AI.
- [ ] Nhắn cả đội: có tài khoản GitHub, đã đăng nhập agent của mình, mang sạc, có Python 3.11+, `make`, Node 20+.

## 3. Kickoff: thiết lập (15 phút)

**3.1 Tạo repo (private) từ template, clone, mời đội.**
```bash
cd ~/Desktop && gh repo create <REPO> --template Nguyen-Le-Tuan/hackkit --private --clone
for u in <teammate1> <teammate2> <teammate3>; do gh api -X PUT repos/<ORG>/<REPO>/collaborators/$u -f permission=push --silent; done
```
- [ ] Gửi cho cả đội:
```text
Đã mời bạn vào <ORG>/<REPO>. Làm 3 việc, xong nhắn "OK":
1) Chấp nhận lời mời: https://github.com/<ORG>/<REPO>/invitations
2) git clone https://github.com/<ORG>/<REPO>.git && cd <REPO> && make setup && source .venv/bin/activate && make test
3) Đăng nhập agent của bạn (claude hoặc codex). Chưa điền khóa. Đừng push lên main.
```

**3.2 Cài đặt của tôi. CHƯA điền khóa.**
```bash
cd ~/Desktop/<REPO> && make setup && source .venv/bin/activate && make test && make lint
```
- [ ] Xanh. (`make setup` cài luôn hook chặn commit tài liệu đối tác, file lớn, `.env`, khóa.)
- **Vì sao chưa điền khóa:** agent trong `orchestrate.sh` chạy cạnh repo và đọc được `../.env`. Script từ chối
  chạy nếu `.env` có khóa. Khóa điền ở **5.6**, sau lần chạy kế hoạch cuối cùng.

**3.3 Đọc luật (không bỏ qua).**
- [ ] Được dùng template/code có sẵn không? Phải khai báo template và công cụ AI không?
- [ ] **Dữ liệu đối tác có được gửi sang Claude/Codex/Groq không?** Chưa có "được" thì chỉ dùng dữ liệu giả.
      Tài liệu đối tác để trong **`partner/`** (git bỏ qua, hook chặn), **không** để trong `docs/`.
- [ ] Rubric và trọng số, thể thức pitch (mấy phút, có Q&A không), hạn nộp, cách nộp (Devpost? file?).
- [ ] **Giải phụ / sponsor track**: liệt kê hết, ghi công nghệ cần dùng để dự thi.

**3.4 Preflight (1 phút).** `./scripts/orchestrate.sh --check --transcript <file đề hoặc file bất kỳ>`
- [ ] `OK` cho `.env`, Claude, Opus dự phòng, Codex. Có `WARN` thì sửa theo mục 10.

## 4. Phân tích đề (máy làm, người làm việc khác song song)

Chọn **một** luồng theo cách ban tổ chức phát đề:

**4a. Đề viết (giấy, PDF, trang web).** Chuyển sang chữ (`.txt`, chụp ảnh rồi nhờ AI chép), để ở `docs/` nếu
công khai, ở `partner/` nếu không. Rồi chạy ngay:
```bash
./scripts/orchestrate.sh --now --transcript docs/<de>.txt --document --no-lid-guard
```

**4b. Đề nói (kickoff trong phòng).** Bật LectureBridge ghi âm, đặt giờ chụp lúc phần giới thiệu kết thúc:
```bash
./scripts/orchestrate.sh --at 11:00 --lock --lecturebridge   # "20 phút nữa": --at "$(date -d '+20 minutes' +%H:%M)"
```
- Cả hai: thêm `--with-file docs/<file>.txt` (lặp lại được) cho đề giấy kèm ghi âm; thêm `--chosen "Tên challenge"`
  khi đội đã được giao hoặc đã chọn. Chạy lại sẽ tự lưu bản cũ vào `docs/agent/archive/`.
- Khoảng 5 phút. Tiến độ: `cat ~/Desktop/<REPO>-agent/docs/agent/STATUS.md`. Dừng khẩn: `touch STOP`.

**Trong lúc chờ (song song):**
- [ ] **human-C:** `make init-project NAME="<tên tạm>" TAGLINE="<một câu>" TEAM="<đội · tên>" EVENT="<sự kiện>"`,
      mở `docs/pitch/README.md`, chép rubric vào bảng "Rubric map", điền giờ thật vào bảng **Milestones** của
      `docs/TASKS.md`.
- [ ] **partner-qa:** gửi tin dưới cho đại diện đối tác/ban tổ chức (họ có thể về sớm: đi ngay).
- [ ] **Hai người dùng agent:** đọc đề, mỗi người chọn một challenge làm được trong vài giờ, 2 dòng lý do.
```text
Hỏi đối tác/ban tổ chức, ghi NGUYÊN VĂN, gửi lại trong 10 phút:
1) Dữ liệu/API họ cung cấp là gì? Có được gửi sang Claude/Codex/Groq không? Có ví dụ tính tay (để làm golden test) không?
2) Người dùng thật là ai, hôm nay họ làm việc đó thế nào, mất bao lâu? (=> con số tác động)
3) Họ muốn thấy gì nhất trong demo? Điều gì làm họ nói "wow"?
4) Rubric, thời lượng pitch, cách và hạn nộp, giải phụ.
5) Được dùng số liệu/ảnh của họ trong slide và repo công khai không?
```

## 5. Quyết định và khóa hợp đồng (khoảng 20 phút)

**5.1 Đọc kết quả.**
```bash
cd ~/Desktop/<REPO>-agent/docs/agent && cat STATUS.md && less BRIEF.md && less PLAN_REVIEW.md
```
- [ ] `STATUS.md`: `DONE`, 4 file `[x]`, không sửa file ngoài `docs/agent`, **Secret scan `clean`** (`ALERT` => mục 10).
- [ ] `BRIEF.md` khớp đề: challenge, rubric, hạn, luật, dữ liệu. Ghi lại "Uncertain or missing".

**5.2 Chọn challenge và plan (cả đội, sau khi có câu trả lời của đối tác).** Plan thắng phải:
- [ ] ghi điểm ở **mọi** mục rubric (xem "rubric map" trong PLANS), một người dùng, một đường demo rõ;
- [ ] có **khoảnh khắc 10 giây đầu** và **một con số tác động có nguồn**;
- [ ] có **AI hiện trong luồng chính** (extract / Explain / Ask), code giữ số;
- [ ] làm trọn trong thời gian còn lại, demo không phụ thuộc may rủi; dự được giải phụ nào thì ghi.
- [ ] Plan đã chọn: ______
- [ ] `cd ~/Desktop/<REPO> && git switch main && git merge agent/plan`

**5.3 Soạn `docs/spec.md`** (tôi duyệt từng dòng). Trong Claude Code:
```text
Đọc docs/agent/BRIEF.md, PLAN_REVIEW.md, PLANS.md (và file đề trong docs/ nếu có). Tôi chọn plan X, bản rút gọn
trong PLAN_REVIEW. Điền docs/spec.md theo đúng các mục của file mẫu, kể cả rubric map, 10 giây đầu, con số
tác động (có nguồn) và chỗ AI hiện ra. Thêm câu trả lời của đối tác: <dán>. Chỉ ghi điều có trong tài liệu hoặc
câu trả lời, ghi rõ chỗ chưa chắc. Không viết code.
```

**5.4 Khóa hợp đồng.** Trong Claude Code:
```text
Từ docs/spec.md: (1) điền khối "Project (FILL ON EVENT DAY)" trong AGENTS.md; (2) điền docs/TASKS.md: Contract
và bảng Tasks theo plan (giữ T0 pitch và T4 AI hiện ra; T1 là khung feature, merge trong ~10 phút; phụ thuộc
mềm `T1~`; việc song song sửa file KHÁC nhau). Giữ nguyên bảng Team và Milestones. Không viết code.
```
- [ ] Đọc kỹ **Contract** và cột **Files it may touch**: hai việc cùng đợt không trùng file.

**5.5 Sinh luồng việc, giao việc.**
```bash
make lanes && git add -A && git commit -m "docs: spec, tasks, milestones" && git push origin main
```
- [ ] `make lanes` không có `⚠`. Gửi "Tin nhắn cho nhóm chat" ở **mục 6** cho cả đội.
- Feature mẫu **receipt** chỉ để template chạy được từ đầu. Khi feature của đội chạy (T1):
  `make remove-example` xóa nó ở mọi chỗ và trỏ ảnh chụp, video sang feature của đội.

**5.6 Điền khóa** (chỉ khi `STATUS.md` có `DONE` và Secret scan `clean`; khóa không hiện ra màn hình):
```bash
read -rsp "Dán khóa rồi Enter: " K && echo && sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=anthropic|; s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$K|" .env && unset K
```
(Groq: thay `anthropic` bằng `groq` và `ANTHROPIC_API_KEY` bằng `GROQ_API_KEY`.)

## 6. LUỒNG VIỆC HIỆN TẠI (tự sinh, đừng sửa tay)

<!-- LANES:START -->
Chưa có dữ liệu. Sau bước **5.5** chạy `make lanes`: khối này hiện mốc giờ (và mốc nào TRỄ), ai làm gì,
việc nào song song, ai chờ ai, và lệnh/lời nhắc copy–paste cho từng người.
<!-- LANES:END -->

## 7. Vòng điều phối (human-A)

| Sự kiện | Lệnh |
|---|---|
| Ai đó bắt đầu / mở PR / tôi merge | `make lanes SET="T1=doing"` / `"T1=review"` / `"T1=merged"` |
| Đạt một mốc | ghi `yes` ở cột Done của bảng Milestones, rồi `make lanes` |

Mỗi PR:
```bash
make verify PR=<số>     # gộp thử với main + guard + lint + test + smoke; chỉ merge khi "VERDICT: MERGE OK"
gh pr checks <số> --watch && gh pr merge <số> --merge && git switch main && git pull origin main
```
- PR nhắm nhầm nhánh (lỗi PR chồng nhau): `gh pr edit <số> --base main`. PR lạc hậu:
  `gh api -X PUT repos/<ORG>/<REPO>/pulls/<số>/update-branch --silent`.
- **Merge dự phòng:** khi tôi bận, người merge dự phòng làm đúng các bước trên, không merge PR của chính mình.
- Song song chỉ khi file không chồng nhau và phụ thuộc đã merge. Việc dưới ~10 phút: để một agent làm liền.
- Mỗi 30 phút: đọc "Ngay bây giờ" và bảng mốc ở mục 6; dọn việc đang chờ.

## 8. Pitch song song (human-C, từ phút 0)

Làm theo `docs/pitch/README.md`. Tóm tắt:
- [ ] T+0:30: rubric map, "10 giây đầu", tìm **một** con số tác động có nguồn; `web/config.json` (hero, impact).
- [ ] T+1:30: `make shots` trên bản xấu; `docs/pitch/deck.toml` v0 chỉ có tiêu đề; `make deck`.
- [ ] T+2:30: deck v1 có ảnh thật; `docs/pitch/script.md` lượt đầu; `docs/SUBMISSION.md` bản nháp.
- [ ] Sau đóng băng: `make pitch` (ảnh + slide + video), tập 3 lần có bấm giờ.

## 9. Đóng băng và nộp bài

- [ ] **T−1:30: `make freeze`** rồi `git push`. Từ đây CI chỉ cho qua PR gắn nhãn `bugfix`.
- [ ] `make test && make lint` xanh trên `main`.
- [ ] **Làm nóng bằng model thật, trên chính laptop trình diễn:** `make run`, chạy **từng input demo** một lần
      (mỗi kết quả ghi `N model call(s)`). Cache tách theo provider, nên kết quả của `fake` không bao giờ bị trả
      lại thay model thật.
- [ ] `make snapshot` (vẫn với model thật), commit `web/snapshots/`, push: bản offline và trang Pages dùng nó.
- [ ] Tập trên **laptop trình diễn**: `make doctor` (terminal) + mở `http://localhost:8000/#/doctor` (trình duyệt
      trình diễn: WebGL, font, màn hình). Tắt Wi-Fi, `make web`: vẫn chạy.
- [ ] `DEMO_MODE=true make run`: chỉ phát lại kết quả đã lưu, không gọi mạng. Input chưa làm nóng sẽ báo lỗi: chỉ
      trình diễn input đã chạy.
- [ ] `make pitch` lần cuối; `docs/pitch/out/demo.mp4` mở sẵn ở cửa sổ thứ hai làm dự phòng.
- [ ] `LLM_PROVIDER=<thật> make eval`: ghi độ chính xác vào README/Devpost.
- [ ] `make pages` (trang "Try it"); nếu luật yêu cầu repo công khai: `make public` (chạy guard trước).
- [ ] Devpost từ `docs/SUBMISSION.md`, **trước hạn ≥ 30 phút**: video, ảnh, link, thành viên, giải phụ, khai báo
      template và công cụ AI. Bấm **Submit**, chụp màn hình xác nhận.

## 10. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `pytest: not found` | Chưa kích hoạt môi trường ảo | `source .venv/bin/activate` |
| `--check`: Codex/Claude lỗi | Chưa đăng nhập hoặc bản cũ | `codex login`, chạy `claude` một lần |
| `--check`: LectureBridge không truy cập được | App chưa chạy hoặc chưa bật ghi | bật app và bật lưu bản ghi, chạy lại `--now` |
| BRIEF nói không có nội dung kickoff | Âm thanh sai hoặc chưa đủ | chạy lại với `--now` khi đã có nội dung |
| Commit bị hook chặn (`guard: ... FAIL`) | File đối tác, file lớn, `.env`, khóa, gitlink, symlink | làm theo dòng hướng dẫn trong thông báo; tài liệu đối tác để ở `partner/` |
| `make verify`: target branch FAIL | PR nhắm nhánh khác `main` | `gh pr edit <số> --base main` |
| `make verify`: merge FAIL | Xung đột với `main` | người làm: `git fetch origin && git merge origin/main`, sửa, push |
| CI `freeze-check` đỏ | Đang đóng băng, PR chưa gắn nhãn | chỉ sửa lỗi: gắn nhãn `bugfix`; tính năng mới thì chờ |
| CI `e2e` đỏ | Trang lỗi JS hoặc tràn ngang ở 390 px | chạy `python scripts/shots.py --smoke`, sửa trang được nêu |
| CI đỏ ở `ruff format` | Code chưa chuẩn | `make fmt` rồi commit |
| `git push` bị từ chối | Có người push trước | `git pull --rebase origin main` rồi push lại, **không** force-push |
| Trang trắng / "No server" | Server chưa chạy | `make run` (hoặc `make web` cho bản tĩnh) |
| Bản đồ không hiện 3D | Trình duyệt tắt WebGL | `#/doctor`; bật hardware acceleration; app tự chuyển bản đồ SVG |
| Demo mode báo `no cached result` | Input chưa được làm nóng | tắt demo mode, chạy input đó với model thật một lần |
| Nút Explain hiện "Fallback text" | Model bịa số không có trong metrics | bình thường: code đã chặn; thêm số cần nói vào metrics nếu muốn |
| Agent sửa file ngoài phạm vi | Lời nhắc chưa chặt | `git checkout -- <file>`, nhắc lại "chỉ sửa các file: ..." |
| `STATUS.md`: Secret scan `ALERT` | Agent chép khóa vào tài liệu | **không** merge; xóa worktree và nhánh `agent/plan`; thu hồi khóa; chạy lại |
| Lỡ lộ khóa API | Dán nhầm vào chat/commit | thu hồi trong console ngay, tạo khóa mới |
| Lỡ đẩy tài liệu đối tác lên repo | Commit trước khi có hook | `make private` ngay; xóa khỏi lịch sử (hỏi người hiểu git); báo đối tác nếu cần |

## 11. Nhật ký (điền giờ thật, sau cuộc thi đưa bài học vào template)

| Mốc | Giờ |
|---|---|
| Có đề / bắt đầu ghi âm | |
| `orchestrate.sh` khởi chạy / xong | |
| Chốt plan, `make lanes` lần đầu | |
| Bản xấu chạy trọn + deploy | |
| Slide v1 có ảnh thật | |
| Đóng băng | |
| Nộp | |

Bài học trong ngày:
-
