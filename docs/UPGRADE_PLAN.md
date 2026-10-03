# Kế hoạch nâng cấp hackkit v2: từ "code đúng" sang "thắng giải"

Soạn ngày 2026-10-03, sau UB AI for Good (NOCO Scout, đội HELIX, không có giải).
Nguồn: retro của buổi thi, bài học của chủ repo ("bỏ Streamlit, dùng HTML/CSS/JS"), review repo `hackkit`
(47 test, CI xanh) và repo `AI_FOR_GOOD` (Streamlit + bản `web/` HTML/CSS/JS của Anh-08).
Giải thích viết bằng tiếng Việt; code, lệnh và tên file viết bằng tiếng Anh.

---

## 0. Mục tiêu và nguyên tắc

**Mục tiêu:** ở hackathon kế tiếp (Devpost hoặc UB), đến **T+1:30** đã có một bản end-to-end xấu nhưng chạy được và đã deploy.
Đến **T+2:30** có slide v1 với ảnh chụp thật. Đến **T−1:00** đã có video demo và trang Devpost. Phần còn lại dành cho trau chuốt.

**Năm nguyên tắc rút từ hôm nay:**
1. **Giám khảo chấm thứ họ nhìn thấy.** Rubric có 5 mục, chỉ 1 mục là kỹ thuật. Template phải làm cho UI, pitch, video
   và trang Devpost **rẻ và tự động**, không để thành việc của giờ chót.
2. **Một ngôn ngữ cho logic, một ngôn ngữ cho giao diện.** Python giữ logic, LLM và dữ liệu. HTML/CSS/JS chỉ hiển thị.
   Không viết lại logic hai lần: bản `web/` của AI_FOR_GOOD phải chép mọi module sang JS, thêm `pyfmt.js` và test so khớp.
3. **AI phải nhìn thấy được trên sân khấu.** LLM vẫn không quyết định con số, nhưng phải có vai trò rõ trong luồng chính.
4. **Dữ liệu demo phát lại được.** Dữ liệu lưu sẵn, chạy offline, và có bản tĩnh để deploy miễn phí.
5. **Luật quan trọng phải do máy thực thi.** Đóng băng, chặn file đối tác, kiểm tra PR và nhánh đích phải là script,
   vì checklist trên giấy hôm nay đã bị bỏ qua.

---

## 1. Kiến trúc mới (thay Streamlit)

```
           ┌──────────── web/ (HTML + CSS + JS thuần, ES modules, không build step) ────────────┐
           │  ui-kit: tokens.css, components.css, ui.js (card, metric, badge, table, toast,      │
           │          skeleton, empty/error state, source badge, DEMO badge, modal)              │
           │  router.js (hash routes) · api.js (live | static) · map.js (MapLibre + deck.gl, tuỳ)│
           │  pages/home.js · pages/<feature>.js                                                 │
           └───────────────▲──────────────────────────────────────▲──────────────────────────┘
                           │ fetch /api/...                        │ fetch snapshots/*.json
        live mode ─────────┘                                       └──── static mode (GitHub Pages, offline)
           ┌──────────────────────────── FastAPI (src/hackkit/server.py) ─────────────────────┐
           │ /api/health · /api/features · /api/run/{feature} · /api/<custom routes>         │
           │ phục vụ luôn web/ bằng StaticFiles → một lệnh `make run`, một cổng                │
           └───────────────▲─────────────────────────────────────────────────────────────────┘
                           │
           src/hackkit (giữ nguyên: providers, extract + retry, cache, connector, evals, export)
           src/features/<name> (schema + rules + routes.py tuỳ chọn)
```

**Vì sao chọn FastAPI + web tĩnh:**
- Tính năng LLM cần giữ khóa API ở server. Bản `web/` thuần JS chỉ phát lại một câu trả lời viết sẵn, và Census geocoder
  chặn gọi thẳng từ trình duyệt (CORS). Hai việc đó đều cần một backend mỏng.
- Không có build step (không React, không bundler). Người mới và agent sửa được ngay; thư viện nạp từ CDN.
  Đội thấy bản này đẹp hơn hẳn Streamlit.
- **Static mode:** `make snapshot` gọi API cho các input demo và lưu thành JSON. `api.js` tự đọc snapshot khi
  không có server. Kết quả là deploy miễn phí lên GitHub Pages (link "Try it" cho Devpost) và demo offline vẫn chạy.

**Thay đổi cụ thể:**

| Việc | File | Ghi chú |
|---|---|---|
| Thêm `fastapi`, `uvicorn` | `pyproject.toml` | Bỏ `streamlit` khỏi dependency chính |
| `server.py`: app factory, route chung cho mọi feature đã đăng ký, StaticFiles cho `web/` | `src/hackkit/server.py` | Feature có thể thêm `routes.py` (APIRouter) |
| `web/` skeleton: `index.html`, `css/tokens.css` (màu, chữ, khoảng cách; sáng/tối), `css/components.css`, `js/ui.js`, `js/router.js`, `js/api.js`, `js/pages/home.js`, `js/pages/feature.js` (trang chung: input → kết quả → cờ review → tải .md/.json) | `web/` | Học từ `AI_FOR_GOOD/web/` nhưng bỏ phần logic chép sang JS |
| `map.js` tuỳ chọn: MapLibre + deck.gl với fallback SVG, tooltip giới hạn rộng | `web/js/map.js` | Lấy từ AI_FOR_GOOD, bỏ phần riêng của NOCO |
| Xoá `app/streamlit_app.py`, `.streamlit/`, `tests/test_app.py`; thay bằng `tests/test_server.py` (TestClient) | | Core `src/hackkit` không đổi |
| Makefile: `run` (uvicorn + web), `demo` (fake provider + DEMO_MODE), `web` (chỉ static mode), `snapshot` | `Makefile` | |
| Dockerfile chạy uvicorn, chép `web/` và `data/` | `Dockerfile` | Bản cũ không chép dữ liệu demo |
| Cập nhật README, AGENTS.md, DAY_OF §7 (bỏ "sidebar", "Clear saved results") | docs | |

**Xong khi:**
- `make run` mở trang chủ có thương hiệu.
- Feature `receipt` chạy được từ web cả ở live mode và static mode.
- Có ảnh chụp không bị đè chữ ở 1280 px và 1440 px.
- `pytest` và CI xanh.

---

## 2. Bộ công cụ "thắng giải" (thứ giám khảo nhìn thấy)

| Lệnh | Làm gì | Vì sao |
|---|---|---|
| `make shots` | Playwright mở các route khai báo trong `docs/pitch/shots.yaml` ở 1280 px và 1440 px, lưu PNG vào `docs/pitch/shots/`, **fail nếu console có lỗi** | Hôm nay phải tự dựng Firefox BiDi để chụp; lỗi bố cục trang chủ phát hiện lúc 14:57 |
| `make demo-video` | Playwright chạy kịch bản `docs/pitch/demo_flow.py` (gõ, bấm, rê chuột, có độ trễ) và quay video webm/mp4 | Video dự phòng hôm nay chưa bao giờ được quay. Devpost bắt buộc có video |
| `make deck` | `python-pptx` dựng slide 16:9 từ `docs/pitch/deck.yaml` (tiêu đề, 1 ý, ảnh từ `shots/`, speaker notes); xuất PDF bằng LibreOffice nếu có | Bộ dựng slide của Codex hôm nay phụ thuộc runtime riêng của Codex và đường dẫn tuyệt đối, nên không chạy lại được |
| `make deploy-static` | `make snapshot` rồi đẩy `web/` + snapshots lên GitHub Pages (`gh-pages` hoặc Actions) | Link "Try it" cho Devpost; giám khảo online thử được |
| `docs/SUBMISSION.md` | Mẫu Devpost: Inspiration / What it does / How we built it / Challenges / Accomplishments / What we learned / What's next / Built with, kèm checklist (video ≤ 3 phút để unlisted, link repo, link demo, ảnh bìa, track và giải phụ đăng ký) | Devpost chấm phần lớn qua trang này và video |
| `docs/pitch/` mẫu | `deck.yaml` 7 slide theo rubric, `script.md` 4 phút có cột "nói gì / làm gì", Q&A, checklist sân khấu | Rút từ PITCH_SCRIPT_EN.md đã viết hôm nay |
| README mẫu | Khung README của sản phẩm (không phải của hackkit) mà `make init-project NAME=...` sinh ra | Hôm nay README vẫn là của hackkit đến 15:30 |

Dependency tuỳ chọn, không bắt buộc khi cài: `pip install -e ".[pitch]"` gồm `playwright` và `python-pptx`,
cộng `playwright install chromium`. Cách này cũng giải quyết việc máy không có Chrome.

---

## 3. Luật do máy thực thi (an toàn và điều phối)

| Công cụ | Làm gì | Lỗi hôm nay nó chặn được |
|---|---|---|
| `scripts/hooks/pre-commit` (cài trong `make setup`) | Chặn: `.xlsx .xls .docx .pptx .pdf .csv` ngoài danh sách cho phép; file > 5 MB; `node_modules`; **gitlink (mode 160000)**; `.env`; giá trị khóa (`secret_scan.py`) | File NOCO lên repo public; gitlink `AI_FOR_GOOD-agent`; symlink `node_modules`; 5 PNG trùng nhau |
| `partner/` trong `.gitignore` + AGENTS.md | Tài liệu đối tác để vào đây; agent đọc được nhưng không commit được | Như trên |
| `make verify PR=N` | Gộp thử PR với `main` trong worktree tạm → test, lint, grep trường cấm (cấu hình trong `hackkit.toml`), smoke test server, `make shots` cho route bị đổi, **kiểm tra nhánh đích là `main`**, rồi in ra báo cáo đạt/không đạt | Mỗi PR hôm nay tôi phải làm tay; PR2 của T18 merge nhầm vào nhánh của PR1 |
| `make freeze` / `make unfreeze` | Bật bảo vệ nhánh `main` qua `gh api`: chỉ nhận PR gắn nhãn `bugfix`, cần CI xanh | Giờ đóng băng bị dời 14:00 → 14:30 → 15:00, có PR merge lúc 14:57 |
| `make doctor` | Trên máy demo: kiểm tra Python, Node (nếu cần), trình duyệt, WebGL, cổng trống, dữ liệu offline, độ phân giải, pin/sạc | Laptop Linux không hiện bản đồ; máy demo chỉ được chốt lúc 14:15 |
| `make private` / `make public` | Bọc `gh repo edit --visibility` | Repo public suốt buổi thi |
| CI: thêm job `web` (node:test nếu có JS test) và chạy `make shots` ở chế độ smoke | | Test JS hôm nay có thể bị skip trên CI |

---

## 4. Nâng cấp framework (`src/hackkit`)

1. **Nguồn gốc dữ liệu là dữ liệu có cấu trúc.** Thêm `Provenance(source, confidence, note)` và `Sourced[T]` vào
   `schemas.py`, cùng helper hiển thị cho web, HTML và CSV. Chuỗi kiểu `"[noco_sheet]"` hôm nay buộc phải làm lại ở T20.
2. **Sửa lỗi cache:** khóa cache phải gồm provider và model. Hiện kết quả của fake provider bị phát lại khi chạy model thật;
   DAY_OF §7 có cảnh báo về lỗi này.
3. **Ba mẫu "AI nhìn thấy được"**, mỗi mẫu có ví dụ chạy được và eval:
   - `extract` (đã có): văn bản hoặc ảnh lộn xộn → schema.
   - `narrate`: LLM viết đoạn giải thích hoặc thư cho khách **quanh các con số do code tính**. Hàm kiểm tra bảo đảm
     mọi con số trong văn bản trùng với số đã tính, nếu không thì retry.
   - `ask`: câu hỏi tiếng Anh tự nhiên → bộ lọc có cấu trúc (Pydantic) → truy vấn tất định. Ví dụ "offices in
     Allentown saving over $50k".
4. **Mẫu "golden test":** `tests/golden/` + helper so sánh với bảng tính hoặc ví dụ của đối tác, có dung sai.
   Đây là thứ đã cứu phần máy tính hôm nay.
5. **Scaffold sinh đủ bộ:** `make feature NAME=x` tạo feature, test, eval case, route API và trang web
   (hiện chỉ tạo một file).
6. **Snapshot:** `hackkit.snapshot` chạy danh sách input demo qua API rồi lưu JSON cho static mode và demo mode.

---

## 5. Quy trình và tài liệu

**Mốc thời gian mặc định (in trong DAY_OF, `lanes.py` cảnh báo khi trễ):**

| Mốc | Phải có |
|---|---|
| T+0:30 | Chốt đề và ý tưởng; bảng rubric → điểm demo; "10 giây đầu giám khảo thấy gì"; con số tác động |
| T+1:30 | E2E xấu nhưng chạy được và đã deploy (static); slide nháp có tiêu đề |
| T+2:30 | Slide v1 với `make shots`; AI xuất hiện trong luồng chính |
| T−1:30 | `make freeze`; QA trên máy demo (`make doctor`) |
| T−1:00 | `make demo-video`; trang Devpost (`SUBMISSION.md`) xong |
| T−0:30 | Nộp xong, chụp xác nhận, tập pitch lần 3 |

**Vai trò cố định:**
- **Pitch/UX owner từ phút 0:** slide, kịch bản, ảnh chụp, video, Devpost. Hôm nay vai trò này bị dồn về cuối.
- **Integrator:** merge và `make verify`. Không kiêm thuyết trình và chạy demo.
- **Hai agent lane:** code theo hợp đồng.
- **Researcher/partner liaison.**

**orchestrate.sh:**
- Commit các cờ đang nằm local: `--document`, `--with-file` và `--chosen` đã dùng thật và hữu ích.
- Thêm vào đầu ra:
  - `RUBRIC_MAP.md`: mỗi mục rubric → tính năng → khoảnh khắc demo.
  - "Prize tracks": các giải phụ của sponsor và công nghệ cần dùng để dự thi.
  - Kiểm tra "AI có nằm trong luồng chính không?".
- Bỏ phần riêng của AI_FOR_GOOD trong bản DAY_OF local: tên đề ACV/AAO/NOCO, file transcript. Đưa về dạng tổng quát.

**Tài liệu:**
- DAY_OF.md (tiếng Việt) giữ là runbook duy nhất, nhưng ngắn hơn: mỗi bước là một lệnh `make`.
- AGENTS.md (tiếng Anh) thêm luật UI: dùng ui-kit, không thêm framework JS, mọi trang có trạng thái loading, empty và error.

---

## 6. Lộ trình thực hiện

| Giai đoạn | Nội dung | Ước lượng | Xong khi |
|---|---|---|---|
| **P0 Dọn dẹp** | (a) AI_FOR_GOOD: quyết định với 2 file NOCO (private hoặc xoá khỏi lịch sử), gỡ gitlink `AI_FOR_GOOD-agent`, symlink `node_modules`, ảnh trùng, output build. (b) hackkit: commit các cờ của orchestrate, bỏ phần đặc thù NOCO trong DAY_OF và TASKS local | 1 giờ | Hai repo sạch, `git status` trống |
| **P1 Kiến trúc** | Mục 1: FastAPI + `web/` ui-kit + static mode; bỏ Streamlit | 1 ngày | `receipt` chạy trên web, live và static; CI xanh |
| **P2 Công cụ thắng giải** | Mục 2: `shots`, `demo-video`, `deck`, `deploy-static`, `SUBMISSION.md`, mẫu pitch | 1 ngày | Một lệnh ra slide PDF có ảnh thật và video 60 giây |
| **P3 Luật máy** | Mục 3: pre-commit, `verify`, `freeze`, `doctor`, `private` | nửa ngày | Commit file .xlsx bị chặn; `make verify` bắt được PR sai nhánh |
| **P4 Framework** | Mục 4: Provenance, sửa cache, `narrate`, `ask`, golden helper, scaffold đủ bộ | 1 ngày | Mỗi mẫu có ví dụ, test và eval |
| **P5 Quy trình** | Mục 5: mốc thời gian trong lanes, vai trò, orchestrate rubric map | nửa ngày | DAY_OF mới ≤ 1 trang mỗi giai đoạn |
| **P6 Diễn tập** | Thi thử 5 giờ với một đề Devpost cũ, đủ 4 người. Đo các mốc ở mục 5 và sửa template theo kết quả | 1 buổi | Đạt mốc T+1:30 và T−1:00 |

Thứ tự ưu tiên nếu ít thời gian: **P0 → P1 → P2 → P3**. P4 và P5 làm sau. P6 là bắt buộc trước giải lớn.

Cách triển khai: mỗi giai đoạn là một nhánh và một PR vào `hackkit`. Mỗi PR có `make verify` xanh và ảnh chụp
trước/sau cho phần UI.

---

## 7. Chiến thuật riêng theo loại cuộc thi

**Devpost (online hoặc lớn):**
- Giám khảo thường xem **video ≤ 3 phút + trang Devpost + link chạy thử** trong vài phút.
- Ưu tiên: video có lời dẫn, 10 giây đầu là khoảnh khắc wow, ảnh bìa đẹp, mục "Built with" đầy đủ.
- Đăng ký thêm **giải phụ của sponsor** bằng cách dùng công nghệ của họ, vì nhiều đội thắng nhờ giải phụ.

**UB (trực tiếp, pitch 3-5 phút, demo tại bàn):**
- Máy demo chốt từ đầu (`make doctor`), chạy offline, có video dự phòng.
- Một câu chuyện tác động có con số. Trả lời Q&A trung thực nhưng gọn.
- Ghi nguồn dữ liệu bằng một chú thích, không gắn nhãn ở khắp nơi.

---

## 8. Những gì giữ nguyên (đã chứng minh là tốt)

- Hợp đồng code chốt từ đầu, TASKS.md với danh sách file của từng task, `make lanes`, worktree cho từng agent.
- `src/hackkit`: providers, extract + retry, cache, connector, evals, demo mode.
- `secret_scan.py`, guard của orchestrate (lid, lock, secret), luật "LLM không quyết định con số".
- Test không gọi mạng; dữ liệu demo lưu sẵn; golden test với ví dụ của đối tác.
