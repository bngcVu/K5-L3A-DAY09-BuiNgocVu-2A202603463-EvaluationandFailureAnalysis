# Báo cáo cá nhân — 2A202603427_NguyenVuKhanh

## 1. Thông tin thành viên

- Họ tên: Nguyễn Vũ Khanh
- MSSV: 2A202603427
- Email: vukhanhkg2005@gmail.com
- GitHub: https://github.com/vukhanhkg2005-lang

## 2. Phần việc phụ trách

TV4 — Ledger + Evaluation:
- Phụ trách kiểm thử tính bền vững (durability), cơ chế đảm bảo Idempotency của hệ thống Ledger.
- Thiết kế và triển khai bộ test chuyên sâu `src/tests/test_durability_extra.py` kiểm tra crash resilience, chống ghi trùng tiền bồi thường (double refund), và xác thực các điều kiện biên của Host Authorization Gate.
- Đo lường và nghiệm thu Crash Suite 20/20 kịch bản tiêm lỗi crash (`lab8.crash_test`).
- Rà soát trace public theo Trace Contract v1 để phát hiện marker secret, token và thông tin cá nhân của fixture.
- Chạy đo lường Benchmark toàn phần 4 shapes × 5 seeds trên 14 claims public (`src/reports/benchmark.json`).
- Tự kiểm trên bộ hidden không nhãn từ `src/student_drop/` và ghi kết quả vận hành vào `src/reports/hidden_selfcheck.json`.
- Soạn thảo và hoàn thiện Architectural Decision Record (`report/team/decision_adr.md`) và phụ trách các phần số liệu thực nghiệm trong Báo cáo nhóm (`report/team/group_report.md`).

## 3. Đóng góp cụ thể

- Commit `234438c` bổ sung năm test trong `src/tests/test_durability_extra.py`.
  1. `test_idempotency_same_claim_twice` kiểm tra retry giữ một refund và một audit `refund_committed`.
  2. `test_idempotency_retry_different_amount_conflicts` kiểm tra retry với số tiền khác báo xung đột và giữ effect đã ghi.
  3. `test_approval_mismatch_denied` kiểm tra approval của claim khác bị từ chối.
  4. `test_approval_missing_revoked_expired_and_non_positive` kiểm tra approval thiếu, bị thu hồi, hết hạn hoặc số tiền không dương.
  5. `test_order_cap_partial_and_exhausted_refund` kiểm tra trả phần chênh lệch trong trần và từ chối khi trần đã hết.
- Tạo lập các bộ báo cáo định lượng chuẩn xác bằng công cụ của lab:
  - `src/reports/crash.json` ghi kết quả đạt `20/20` kịch bản từ `lab8.crash_test`.
  - `src/reports/benchmark.json`: Sinh ra từ lệnh `python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/benchmark.json`, bao phủ 280 trials.
  - `src/reports/hidden_selfcheck.json` ghi kết quả tự kiểm 600 trial không nhãn. Điểm hidden chính thức do grader của giảng viên xác định.
- Quyết định kỹ thuật:
  - Đề xuất **Workflow (Shape A)** trong ADR vì đạt `70/70` trial public với phương sai bằng 0 và chi phí mô phỏng thấp nhất `28.79 VND/success`.
  - Khẳng định tính an toàn của Ledger dựa trên SQLite transaction `BEGIN IMMEDIATE` và khóa duy nhất `refund:{claim_id}`.

## 4. Bằng chứng

- **Kết quả Unit Test Durability**:
  - `python -m pytest -q tests/test_durability_extra.py -o addopts=` đạt **5 ca**.
- **Kết quả Kiểm tra Ma trận Sinh viên**:
  - `python -m pytest -q -m student -o addopts=`: **248 passed, 199 deselected** (100% test của nhóm xanh hoàn toàn).
- **Crash Safety 20/20**:
  - `python -m lab8.crash_test --count 20 --out reports/crash.json` sinh báo cáo với `count=20`, `passed=20` và `crash_safety="20/20"`.
- **Số liệu Benchmark Toàn phần** (trích xuất từ `src/reports/benchmark.json`):
  - `workflow`: Pass rate **1.000**, Pass^5 **1.000**, Variance **0.000000**, Cost/success **28.79 VND**, Mean Steps **2.71**.
  - `orchestrator`: Pass rate **1.000**, Pass^5 **1.000**, Variance **0.000000**, Cost/success **38.06 VND**, Mean Steps **4.36**.
  - `single`: Pass rate **1.000**, Pass^5 **1.000**, Variance **0.000000**, Cost/success **39.54 VND**, Mean Steps **8.21**.
  - `swarm`: Pass rate **0.986**, Pass^5 **0.929**, Variance **0.000816**, Cost/success **49.57 VND**, Mean Steps **2.80**.
- **An toàn Bảo mật & Trace**:
  - Lượt đối chiếu bản nộp quét 280 trace public và ghi nhận 0 trace chứa marker hoặc giá trị nhạy cảm của fixture. Kết quả kiểm tra approval của Workflow được ghi riêng trong ADR. [Báo cáo nhóm](group_report.md) · [ADR](decision_adr.md)
- **Tự kiểm tra Hidden Test**:
  - `src/reports/hidden_selfcheck.json` ghi 600 trial không nhãn, tổng `graded_trials=0`, `error_trials=0` và `leak_suspect_trials=0`.

## 5. Công cụ AI đã dùng

**Antigravity**, sử dụng vào các công việc:
- Hỗ trợ xây dựng kịch bản kiểm thử chuyên sâu trong `src/tests/test_durability_extra.py` theo đúng chuẩn pytest.

## 6. Tự đánh giá

- **Mức độ hoàn thành**: Hoàn thành 100% nhiệm vụ của vai trò TV4. Các tiêu chí nghiệm thu về tính bền vững (durability), crash resilience (20/20), idempotency, an toàn bảo mật không rò rỉ secret, và báo cáo benchmark toàn phần đều đạt chuẩn tối đa.
- **Bài học kinh nghiệm**:
  - Nhận thức sâu sắc về nguyên tắc "ít tự chủ nhất mà vẫn làm được việc": trong các hệ thống xử lý tài chính và chính sách doanh nghiệp, tính tiền định (determinism) và ranh giới kiểm soát của Host (Host Authorization Gate) quan trọng hơn nhiều so với việc để LLM tự do quyết định.
  - Hiểu rõ ranh giới bảo mật của Trace: Trace là bản ghi kiểm toán pháp lý chứ không đơn thuần là nhật ký gỡ lỗi (debug log), do đó việc áp dụng allowlist để lọc bỏ hoàn toàn PII và Secret là yêu cầu bắt buộc sống còn.
