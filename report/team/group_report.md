# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: Hallucination
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`): `7f84ceb`.

## 2. Mục tiêu và cách tiếp cận

- **Hiểu bài toán**: Xử lý claim hoàn phí vận chuyển và bảo hiểm hư hại của công ty giả lập LogiX-VN theo cùng chữ ký hàm `run_claim` trên bốn kiến trúc khác nhau (Workflow, Single Agent, Orchestrator, Swarm). Ranh giới sống còn: tiền bồi thường, phê duyệt (approval) và chống ghi trùng do Host và code quyết định; model LLM chỉ được đọc dữ liệu và soạn thảo văn bản.
- **Cách tiếp cận và tiêu chí lựa chọn.** Thực nghiệm dùng cùng tập dữ liệu, cùng 5 seed và cùng bảng giá. Nhóm chọn kiến trúc ít tự chủ nhất mà vẫn đạt yêu cầu để giảm chi phí mô phỏng và giới hạn quyền giao cho model.
- **Phân chia công việc**: Nhóm 4 người chia việc độc lập theo 4 luồng song song: TV1 (Workflow + Tích hợp), TV2 (Single Agent ReAct), TV3 (Orchestrator + Handoff allowlist), TV4 (Durability, Crash suite, Benchmark và Evaluation).
- **Thứ tự thực hiện**: Cài đặt cổng host sạch (CP1) → Triển khai 3 shape độc lập (CP2) → Rà soát Idempotency và Crash resilience (CP3) → Nghiệm thu Crash suite 20/20 và rà secret leak (CP4) → Benchmark 4 shape và ra quyết định kiến trúc (CP5).

## 3. Giải pháp

- **Workflow** đọc claim và đơn theo các bước Python cố định. Code dùng dữ liệu đơn và policy hiện hành để tính quote. MockLLM chỉ soạn phản hồi.
- **Single Agent** đọc claim, đơn và lịch sử hoàn tiền qua vòng ReAct giới hạn 8 bước. Agent chỉ dùng tool đọc. Sau vòng lặp, code tính lại quote từ dữ liệu đơn.
- **Orchestrator** lấy mã claim và phạm vi chủ đơn từ dữ liệu hệ thống. `make_handoff()` tạo `handoff.v1` theo allowlist, để trống `facts` và chỉ cấp `lookup_order` cho investigator. Investigator đọc đơn theo phạm vi chủ đơn. Orchestrator tính quote bằng `compute_compensation()` từ order view. MockLLM chỉ nhận trạng thái để soạn phản hồi.

Cả ba shape gửi quote dương đầy đủ cho `durability.issue_refund()`. Host kiểm tra phê duyệt, áp trần theo đơn và xử lý các lần gọi lại. Shape C truyền `crash_at` đến host để bộ test kiểm tra khôi phục sau lỗi.

Trace của Shape C ghi handoff đã lọc, tên tool và kết quả kiểm tra phạm vi truy cập, giá trị quote, kết quả từ host và quyết định cuối. Các nhánh kết thúc sớm cũng ghi trace qua `finish()`. Nội dung ticket, claim/order thô, header, secret và thông tin cá nhân được giữ ngoài trace.

## 4. Kết quả

Bảng so sánh 4 shape lấy từ `src/reports/benchmark.json`. Chạy lại benchmark và crash suite tại `7f84ceb` cho kết quả JSON khớp hai file đã commit.

### Bảng số liệu Benchmark trên bộ Public Claims (14 claims × 5 seeds)

| Kiến trúc (Shape) | Pass Rate | Pass^5 | Seed min–max | Seed Variance | Cost/Success (mô phỏng) | Mean/p95 Steps | Model Calls TB | Ghi chú trạng thái |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Workflow (Shape A)** | **1.000** | **1.000** | 1.000 – 1.000 | **0.000000** | **28.79 VND** | 2.71 / 3.0 | 1.00 | Hoàn thành, 100% pass |
| **Orchestrator (Shape C)** | **1.000** | **1.000** | 1.000 – 1.000 | **0.000000** | **38.06 VND** | 4.36 / 5.0 | 1.00 | Hoàn thành, 100% pass |
| **Single Agent (Shape B)** | **1.000** | **1.000** | 1.000 – 1.000 | **0.000000** | **39.54 VND** | 8.21 / 9.0 | 5.64 | Hoàn thành, 100% pass |
| **Swarm (Shape D)** | **0.986** | **0.929** | 0.929 – 1.000 | **0.000816** | **49.57 VND** | 2.80 / 3.0 | 3.00 | Đối chứng, fail seed 55 |

- **Crash safety.** Đạt `20/20` kịch bản trong `src/reports/crash.json`.
- **Tự kiểm hidden.** `src/reports/hidden_selfcheck.json` ghi 600 trial không nhãn, gồm 200 trial cho mỗi shape `workflow`, `single`, `orchestrator`. Tổng `error_trials=0`, `leak_suspect_trials=0` và `graded_trials=0`. Điểm hidden chính thức do grader của giảng viên chấm.

### Phân tích so sánh chi tiết giữa các kiến trúc:

1. **Workflow (Shape A)**:
   - Chi phí mô phỏng thấp nhất ở `28.79 VND/success`, với trung bình `2.71` bước và pass rate `1.000` trên cả 5 seed public.
   - Code Python quyết định luồng và tính quote. MockLLM chỉ soạn phản hồi.

2. **Single Agent (Shape B)**:
   - Đạt pass rate `1.000`, với chi phí mô phỏng `39.54 VND/success` và trung bình `8.21` bước theo trace.
   - Vòng ReAct giới hạn 8 bước và dùng tool đọc. Benchmark ghi trung bình `5.64` lượt gọi MockLLM trên mỗi trial.

3. **Orchestrator (Shape C)**:
   - Đạt pass rate `1.000` và seed variance `0.000000`, với chi phí thực thi mô phỏng `38.06 VND/success`, trung bình `4.36` bước và `1.00` lượt gọi MockLLM.
   - `make_handoff()` giới hạn payload chuyển cho investigator. Investigator chỉ dùng `lookup_order` trong phạm vi `principal_id` của chủ đơn. Orchestrator dùng order view để tính quote và gửi quote đầy đủ cho host.

4. **Swarm (Shape D - Tham chiếu đối chứng)**:
   - Chi phí mô phỏng `49.57 VND/success` và seed variance `0.000816`. Swarm gốc qua `69/70` trial public.
   - Ở `C-002` seed `55`, Swarm ghi đè số ngày trễ trong order bằng số ngày từ ticket. Kết quả trả `resolved` và ghi refund `20.000 VND`, trong khi nhãn yêu cầu `denied` và refund `0 VND`. Ablation R2 dùng `delay_days` từ order sửa được trial này, nâng pass rate lên `70/70`.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

1. **Ranh giới an toàn thông tin & Trace Contract v1**:
   - *Vấn đề*: Trong các shape có sự tham gia của Agent (Single, Orchestrator), nếu để Agent tự do đọc dữ liệu thô từ claim hoặc order, nguy cơ rò rỉ các thông tin nhạy cảm như `parent_secret` (`CANARY_SECRET_*`), token `Bearer`, số điện thoại, địa chỉ khách hàng (`PII`) và ghi chú nội bộ vào file nhật ký `trace` là rất lớn. Bộ chấm thi của Ban tổ chức sẽ fail-closed ngay lập tức nếu phát hiện chuỗi cấm trong trace.
   - *Cách xử lý*. Dùng dữ liệu allowlist tại các cổng đọc và trong `make_handoff()`. Lần đối chiếu public quét 280 trace sinh bởi benchmark 4 shape × 14 claim × 5 seed. Số trace chứa marker secret, giá trị header hoặc thông tin cá nhân của fixture là 0.

2. **Tính bền vững (Durability) và Khôi phục sau Crash**:
   - *Vấn đề*: Khi hệ thống gặp sự cố mất điện/crash tại các thời điểm nhạy cảm (như ngay sau khi ghi tiền vào Ledger nhưng chưa kịp lưu checkpoint, hoặc trước khi ghi hiệu ứng), việc chạy lại (retry/resume) có nguy cơ gây ra lỗi ghi trùng tiền (double refund), vi phạm nghiêm trọng nguyên tắc kế toán tài chính.
   - *Cách xử lý*. Các shape dùng cơ chế idempotency của host với khóa duy nhất `refund:{claim_id}` và transaction `BEGIN IMMEDIATE`. Crash suite xác nhận `20/20` kịch bản kiểm thử đạt yêu cầu. Các ca retry và resume đối chiếu số dòng ledger và audit sau khi chạy lại.


## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`.

## 7. Hạn chế và hướng cải thiện

1. **Hạn chế thực nghiệm hiện tại**:
   - **Mô hình MockLLM**: Trong phạm vi bài lab, MockLLM hoạt động dựa trên các bộ luật và quy tắc mô phỏng xác định (deterministic mock). Do đó, các độ đo về chi phí token và số bước gọi model mới chỉ phản ánh mức độ phức tạp về mặt cấu trúc luồng điều khiển, chưa phản ánh được sự biến động thực tế về mặt ngữ nghĩa (semantic drift) hay độ suy giảm hiệu năng do context window dài của các mô hình LLM sản xuất (production models như Gemini 1.5 Pro, Claude 3.5 Sonnet).
   - **Độ trễ.** Benchmark ghi `latency=unavailable`. Độ trễ triển khai thực tế cần đo riêng trên môi trường và model tương ứng.
   - **Phạm vi dữ liệu**: Dữ liệu đầu vào trong bài lab chủ yếu là các trường có cấu trúc (bảng claim, bảng order).

2. **Hướng cải thiện & Điều kiện làm quyết định kiến trúc thay đổi**:
   - Khi bài toán mở rộng sang tiếp nhận các loại dữ liệu phi cấu trúc phức tạp (như hình ảnh gói hàng bị móp méo, tài liệu hóa đơn scan PDF mờ, hoặc biên bản đối soát viết tay từ bên chuyển phát), kiến trúc Workflow thuần túy bằng code if/else sẽ không thể tự trích xuất thông tin. Khi đó, nhóm sẽ nâng cấp lên kiến trúc **Orchestrator** (Shape C): dùng Agent thị giác (Vision LLM) để phân tích trích xuất dữ liệu thô vào các schema chuẩn, sau đó bàn giao (handoff) qua allowlist sang Workflow xác định để tính toán tài chính và ra quyết định bồi thường, kết hợp với Guardrails để chống Prompt Injection.

## 8. Tài liệu tham khảo

1. Tài liệu bài giảng và hướng dẫn thực hành AI20K K5 - L3A Day 08: *Hallucination — From Workflows to Agents*.
2. Anthropic (2024), *Building Effective Agents*, Anthropic Research Blog.
