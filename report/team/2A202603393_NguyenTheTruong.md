# Báo cáo cá nhân — 2A202603393_NguyenTheTruong

## 1. Thông tin thành viên

- Họ tên: Nguyễn Thế Trường
- MSSV: 2A202603393
- Email: 26ai.truongnt2@vinuni.edu.vn
- GitHub: https://github.com/Nguyen-The-Truong

## 2. Phần việc phụ trách

TV1 — Workflow: viết shape A `src/lab8/shapes/workflow.py` và test bổ sung.

## 3. Đóng góp cụ thể

- Commit chính: `d473a3e` ("commit workflow"): `workflow.py`, `test_workflow_extra.py`, `TEAM.md`, báo cáo cá nhân; đã gộp vào `main` ở `daa8d46`
- Shape `workflow`: các bước cố định. Đọc claim qua `get_claim_view`, kiểm `order_id` thiếu thì `needs_info`, `lookup_order` không thấy thì `escalated`, quote bằng `compute_compensation`, quote 0 thì `denied` (không gọi host), quote > 0 thì `durability.issue_refund` với quote đầy đủ và `crash_at`.
- Quyết định kỹ thuật: số ngày trễ và `order_id` chỉ lấy từ DB, không parse từ ticket, nên không có điểm yếu như swarm ở seed chia hết cho 5. Trace chỉ ghi field đã qua allowlist (order view, quote, kết quả host), không ghi ticket hay claim row thô. `InjectedCrash` được flush trace rồi ném lại, không bị bắt.
- Test thêm: `src/tests/test_workflow_extra.py` (104 test case):
  - Toàn bộ 14 claim public T01–T14 × 5 seed, đối chiếu status, `proposal_amount`, tổng ledger, audit `policy_denied` và chuỗi cấm trong trace.
  - Ticket nói "trễ 5 ngày" (T02) bị bỏ qua trên cả 5 seed, "ignore policy" (T09) và clause `SHIP-LATE-OLD` (T06) bị coi là dữ liệu.
  - Các nhánh biên: thiếu `order_id` (`needs_info`), sai principal (`escalated`, không lộ order), ship + damage lấy số lớn (T03), approval thấp hơn quote (T08), trần theo đơn (T13 `denied`, T14 chỉ hoàn phần chênh 120.000), claim không tồn tại trả `failed` không ném exception.
  - Gọi lại cùng claim chỉ một dòng ledger; crash tại cả 3 điểm (`before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`) rồi resume vẫn đúng một refund và một audit `refund_committed`.
  - Trace đúng contract v1 ở mọi nhánh, và vẫn được ghi khi có `InjectedCrash`.

## 4. Bằng chứng

- `python -m pytest -q -m student -o addopts= -k workflow`: 62 passed.
- `python -m pytest -q tests/test_workflow_extra.py -o addopts=`: 104 passed.
- `python -m pytest -q` (cổng host, gồm test mới): 158 passed.
- `python -m lab8.smoke`: pass.
- Demo crash rồi resume (claim C-012, seed 11, DB mới), output thật:

```text
> python -m lab8.run --shape workflow --claim-id C-012 --seed 11 --db crash.sqlite --crash-at after_effect_before_checkpoint
{"crashed": true, "at": "after_effect_before_checkpoint", "claim_id": "C-012"}      (exit code 2)

> python -m lab8.run --shape workflow --claim-id C-012 --seed 11 --db crash.sqlite
"run_id": "R-workflow-C-012-s11", "status": "resolved", "proposal_amount": 35000,
"refund_effects": [{"idempotency_key": "refund:C-012", "amount_vnd": 35000, "status": "committed"}],
"committed_audit_count": 1, "model_calls": 1, "tool_calls": 3, "error_reason": null

ledger: [('C-012', 35000)]            audit: [('refund_committed', 1)]
```

  Crash xảy ra sau khi ghi effect nhưng trước checkpoint; chạy lại vẫn chỉ có 1 dòng ledger và 1 audit, vì khóa idempotency `refund:C-012` do host giữ.
- Benchmark workflow so với swarm (public, 14 claim, seed 11,22,33,44,55, chạy qua `lab8.benchmark`):

| Shape | Pass rate | pass^5 | Variance | Min / Max | Cost/success (mô phỏng, VND) | Steps |
| --- | --: | --: | --: | --: | --: | --: |
| workflow | 1.000 | 1.000 | 0.000000 | 1.000 / 1.000 | 28.79 | 2.71 |
| swarm | 0.986 | 0.929 | 0.000816 | 0.929 / 1.000 | 49.57 | 2.80 |

  Swarm trượt 1 trial (T02 ở seed 55, `resolved` thay vì `denied`) vì tin số ngày trong ticket. Workflow không có điểm yếu này, và chi phí mô phỏng thấp hơn khoảng 42%. Đây là số liệu của riêng workflow và swarm; so sánh đủ 4 shape do TV4 chạy ở `reports/benchmark.json`.

## 5. Công cụ AI đã dùng

**Claude Code** (trợ lý AI trong VS Code), dùng vào:
- Đọc và tóm tắt đề bài, checkpoint, phân công, luật nghiệp vụ và contract.
- Viết bản đầu của `workflow.py` theo docstring trong file, và viết `test_workflow_extra.py`.
- Hướng dẫn cài môi trường và chẩn đoán lỗi (xem phần khó khăn).

Cách tự kiểm tra, không tin kết quả AI một cách mù quáng:
- Chạy 62 test student của shape workflow, cổng host `pytest -q` và `lab8.smoke`, đều ra kết quả ở mục 4.
- Đối chiếu từng nhánh của `workflow.py` với bảng trong `docs/business_rules.md` và `docs/contracts.md`.
- Tự chạy demo crash rồi resume bằng CLI và kiểm ledger/audit trực tiếp trong SQLite, không chỉ dựa vào test.
- Chạy benchmark qua `lab8.benchmark` và lấy số từ file JSON do công cụ sinh ra, không tự điền.
- Kiểm tra không copy khối `REFERENCE_WEAKNESS` của swarm.

### Khó khăn đã gặp
- **Python 3.10.11 quá cũ:** `python -m lab8.smoke` báo "Python 3.10.11 quá cũ. Cần Python 3.11+". Xử lý: cài Python 3.12 bằng `winget install -e --id Python.Python.3.12`, mở lại terminal, xóa `.venv` cũ và tạo lại bằng `py -3.12 -m venv .venv`. Sau đó `python --version` ra 3.12.10 và smoke pass. Lưu ý: kết quả `54 passed` đầu tiên chạy trên Python 3.10 cũ, phải chạy lại sau khi đổi.
- **Dùng cmd thay vì PowerShell:** các lệnh `Remove-Item`, `deactivate`, `.\.venv\Scripts\Activate.ps1` không chạy trong cmd. Xử lý: dùng `rmdir /s /q .venv` và `.venv\Scripts\activate.bat`.
- **Thông tin thành viên chưa lưu:** email/GitHub gõ trong editor chưa lưu nên file trên đĩa vẫn trống; xử lý bằng cách lưu file rồi cập nhật lại cả `TEAM.md` và báo cáo này.

## 6. Tự đánh giá


**Làm được:** Hoàn thành shape A `workflow.py` và qua 62/62 test student.
Viết thêm 104 test case riêng, phủ cả 14 claim public × 5 seed, các điểm crash
và nhánh biên; cổng host xanh và tự chạy demo crash rồi resume bằng CLI và kiểm ledger trực tiếp: đúng 1 refund, 1 audit
`refund_committed`. Trên bộ public, workflow đạt pass rate 1.000, pass^5 1.000,
trong khi swarm 0.986 và 0.929 vì tin số ngày trong ticket ở seed 55. Mình cũng chạy
tự kiểm trên `student_drop/`: 40 claim × 5 seed, không có lỗi hay `leak_suspect`.

**Hiểu được:** Hiểu vì sao tiền phải do `compute_compensation` tính chứ không
do MockLLM, và vì sao phải truyền quote đầy đủ vào `issue_refund` để host tự trừ
phần đã hoàn (nếu shape trừ trước thì T14 bị trừ hai lần).

**Hạn chế:**
- Số liệu benchmark chỉ trên bộ public (14 claim) và MockLLM nên chi phí và độ ổn
  định chỉ là mô phỏng, chưa có kết quả hidden có nhãn nên chưa thể kết luận
  workflow tốt nhất.
- Sử dụng Claude Code để viết bản đầu `workflow.py` và test
- Ban đầu gặp lỗi Python 3.10 phải nâng lên 3.12.


