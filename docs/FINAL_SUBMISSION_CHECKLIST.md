# Final Submission Checklist

Repository: `K4-L3B-LeDucHung-2A202602849-AIEvaluation` (tên đúng chuẩn `K4-L3B-<HoVaTen>-<MSSV>-AIEvaluation`).
Submission method (SUBMISSION.md): nộp **link GitHub repo** lên Codelab, repo Public (hoặc cấp quyền cho coach). Hạn chót mặc định 23h59 ngày lab (GMT+7).

Verified offline (không gọi API) bằng `pytest`, `validate_golden_dataset.py` và script audit trên các file artifact.

## 1. Deliverables

| Item | Required? | Current Status | Evidence / File | Manual Action |
|---|---|---|---|---|
| `solution/solution.py` hoàn thiện | Required | PASS — không còn TODO/NotImplementedError; giống hệt `template.py` | `solution/solution.py` | Không |
| `template.py` | Part of lab | PASS (đồng bộ với solution) | `template.py` | Không |
| `golden_dataset.json` 20 QA | Required | PASS — 20 record, 5/7/5/3, evidence verbatim, 10/10 tài liệu, validator PASS | `python validate_golden_dataset.py` | Không |
| `exercises.md` — worksheet, benchmark 3.2, rubric 3.3 | Required | PASS về nội dung/số liệu (bảng 3.2 khớp artifact 20/20). Exercises 1.1–1.3 là **bản nháp có đánh dấu** | `exercises.md` | Xem mục 3 |
| `reflection.md` — report, 3 failures, 5 Whys, clustering, improvement log, regression, final reflection | Required | PASS về cấu trúc; nội dung phân tích là **bản nháp dựa trên evidence** | `reflection.md` | Xem mục 3 |
| `artifacts/actual_answers.json` | Optional (nhưng nên nộp) | PASS — 20/20, không lỗi, `groq` / `openai/gpt-oss-120b` | `artifacts/actual_answers.json` | Không |
| `artifacts/benchmark_results.json` | Optional (nhưng nên nộp) | PASS — 20/20, đủ trường, giá trị trong [0,1] | `artifacts/benchmark_results.json` | Không |
| Tests `pytest tests/ -v` | Required (41 passed, 1 skipped nếu không làm bonus) | PASS — **48 passed, 0 skipped** (đã làm bonus 3.5 nên test skip chạy, +6 test bổ sung) | `tests/test_solution.py` (không sửa), `tests/test_rerank_bonus.py` (mới) | Không |
| Validator output | Required | PASS | `python validate_golden_dataset.py` | Không |
| README / hướng dẫn chạy | Needed for reproducibility | PASS — có provider/model, lệnh chạy, bonus | `README.md`, `.env.example` | Không |
| Screenshots / evidence ảnh | Not required by SUBMISSION.md/RUBRIC.md | N/A | — | Không |
| Bonus 3.5 (+5) | Optional | PASS — `rerank_by_overlap()`, test, demo 20 case, bảng thật trong `exercises.md` | `template.py`, `bonus/exercise_3_5_rerank_demo.py`, `artifacts/bonus_ex35_rerank.json` | Không |
| Bonus 3.4 (+5) | Optional | **PARTIAL** — 27/60 điểm RAGAS thật, 33/60 `null` do hết quota Groq; DeepEval chưa chạy; phương pháp + ánh xạ metric đã viết | `exercises.md`, `bonus/exercise_3_4_ragas_compare.py`, `artifacts/bonus_ex34_ragas.json` | Tuỳ chọn: chạy `--resume` khi có quota |

## 2. Files to submit vs NOT to submit

| File / folder | Submit? | Ghi chú |
|---|---|---|
| `solution/solution.py`, `template.py`, `domain_assistant.py`, `evaluate_answers.py`, `validate_golden_dataset.py`, `requirements.txt`, `.env.example`, `.gitignore`, `__init__.py` | Yes | |
| `golden_dataset.json`, `data/technology_store/` | Yes | |
| `exercises.md`, `reflection.md`, `README.md`, `docs/FINAL_SUBMISSION_CHECKLIST.md` | Yes | |
| `tests/` (kể cả `tests/test_rerank_bonus.py`) | Yes | `test_solution.py` giữ nguyên |
| `artifacts/*.json` (4 file) | Yes | Giữ nguyên giá trị `null` trong `bonus_ex34_ragas.json` |
| `bonus/` | Yes | |
| `RUBRIC.md`, `RULES.md`, `SUBMISSION.md`, `CHECKPOINTS.md`, `guide_lab.md` | Yes (tài liệu đề bài, giữ nguyên) | |
| **`.env`** | **NO — chứa API key thật** | Đã nằm trong `.gitignore`, không bị track |
| `.venv/` | NO | gitignored |
| `__pycache__/`, `.pytest_cache/` | NO | gitignored, đã xoá |
| Thư mục cài ragas ngoài repo (ví dụ `%TEMP%\b34`) | NO | Nằm ngoài repo |

## 3. STUDENT MUST DO BEFORE SUBMISSION

1. **Đọc, hiểu và viết lại bằng lời của bạn** các đoạn đánh dấu `[MANUAL STUDENT CONFIRMATION REQUIRED]` — 13 chỗ trong `reflection.md` và 6 chỗ trong `exercises.md` (Exercises 1.1–1.3). RULES.md yêu cầu phần phân tích, 5 Whys và reflection do học viên tự viết và giải thích được khi coach vấn đáp; bản nháp chỉ dùng số liệu và quan sát kiểm chứng được, không có trải nghiệm cá nhân. Hai câu của Final Reflection cần ý kiến cá nhân của bạn (dự đoán ban đầu, metric sẽ dùng trong production). Sau đó xoá các dấu đánh dấu.
2. **Commit và push** (chưa có commit nào cho các thay đổi này): `git add -A`, `git commit`, `git push origin main`; xác nhận repo Public hoặc đã cấp quyền cho coach.
3. **Nộp link repo lên Codelab** trước 23h59 ngày lab (GMT+7).
4. *(Tuỳ chọn, chỉ để lấy trọn bonus 3.4)* khi quota API hồi lại: chạy lệnh `--resume` bên dưới rồi cập nhật bảng trong Exercise 3.4 (không bắt buộc cho 100 điểm chính).

## 4. Known limitations (không phải blocker)

- Exercise 3.4 chỉ có bằng chứng thực nghiệm một phần: các case Hard/Adversarial chưa có điểm RAGAS; DeepEval chưa chạy. Không có số liệu nào được ước lượng hay điền thay `null`.
- Các số liệu benchmark chính (Exercise 3.2) dùng metric token-overlap trong `template.py`; `reflection.md` nêu rõ giới hạn của metric này (A01/A02 là từ chối đúng nhưng bị chấm gần 0).
- Test count trong SUBMISSION.md/RUBRIC.md ("41 passed, 1 skipped") áp dụng khi không làm bonus; bài này làm bonus 3.5 nên kết quả là 48 passed, 0 skipped.

## 5. Commands

Trước khi nộp:

```bash
python -m pytest tests/ -v                  # expect: 48 passed
python validate_golden_dataset.py           # expect: PASS
git status                                  # .env must NOT be listed
git add -A && git commit -m "Final submission" && git push origin main
```

Sau khi Groq reset (**không chạy bây giờ**; tuỳ chọn):

```bash
pip install --target <short_dir> -r bonus/requirements-bonus.txt
# bash:        PYTHONPATH=<short_dir> python bonus/exercise_3_4_ragas_compare.py --resume
# PowerShell:  $env:PYTHONPATH="<short_dir>"; python bonus/exercise_3_4_ragas_compare.py --resume
```

`--resume` giữ nguyên 27 điểm đã có và chỉ chấm lại 33 metric đang `null`.
