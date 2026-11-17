# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: 7f84ceb
- Run id dẫn chứng: R-workflow-C-001-s11
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000 - 1.000 / 0.000000
- Cost per success (mô phỏng, VND): 28.79
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0 (Workflow, bộ public)

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Nhóm chọn `workflow` (Shape A) theo tiêu chí ít tự chủ nhất mà vẫn đạt yêu cầu. Code xử lý luật hoàn phí, thời hạn hợp lệ và trần theo đơn. MockLLM chỉ soạn phản hồi. Trên cùng 14 claim public và 5 seed, Workflow đạt `70/70`, pass^5 `1.000` và seed variance `0.000000`, với chi phí mô phỏng thấp nhất `28.79 VND/success` và trung bình `2.71` bước. Các số liệu lấy từ `src/reports/benchmark.json`. Run `R-workflow-C-001-s11` là một trial dẫn chứng trong file này.

## Có đáng đổi lấy multi-agent không

Single Agent và Orchestrator cũng đạt `70/70`, với chi phí tương ứng `39.54` và `38.06 VND/success`. Swarm gốc đạt `69/70`, seed variance `0.000816` và chi phí `49.57 VND/success`. Ở `C-002` seed `55`, Swarm dùng số ngày trong ticket để ghi đè số ngày trong order rồi trả `resolved`, trong khi nhãn yêu cầu `denied`. Ablation R2 sửa được ca đó khi dùng `delay_days` từ order. Kết quả ủng hộ việc giữ Workflow cho corpus hiện tại. Nhóm sẽ đánh giá lại khi luồng nghiệp vụ có đầu vào phi cấu trúc hoặc cần phối hợp nhiều bước độc lập, dựa trên mức tăng chất lượng đo được so với chi phí và độ dao động.

## Trace và bằng chứng

Shape C ghi trace tại `RunResult.trace_path`. JSON có `run_id` khớp kết quả và danh sách `events`. `handoff` chỉ ghi payload đã qua `make_handoff()`, trong đó investigator được cấp `lookup_order`. `investigator` ghi tên tool và cờ `visible`. `quote`, `host` và `decision` ghi số tiền đề xuất, kết quả kiểm tra và mã lý do nghiệp vụ. Các nhánh kết thúc sớm dùng cùng `finish()` để ghi trace trong lần chạy hiện tại.

Shape C giữ ticket, claim/order thô, header, `parent_secret`, số điện thoại, địa chỉ, ghi chú nội bộ và tên hàng ngoài trace. Shape ghi một file trace trong thư mục `src/traces/` để scanner nhận diện qua `trace_path` và `run_id`. Test `test_orchestrator_handoff_is_read_only_and_trace_is_safe` đối chiếu payload bàn giao thực tế với event `handoff` và rà dữ liệu nhạy cảm trong trace, kết quả và dữ liệu in ra terminal.

Trong benchmark public, trace của Workflow ghi các event `order`, `quote`, `host` và `decision` tùy nhánh. `refund_committed` và `policy_denied` là loại sự kiện audit trong SQLite. Workflow xây trace từ dữ liệu allowlist. Ticket thô, `parent_secret`, header, số điện thoại, địa chỉ, ghi chú nội bộ và tên hàng nằm ngoài payload trace.

Lần đối chiếu public kiểm tra 70 kết quả Workflow và trace liên quan, ghi nhận 0 trial chứa marker hoặc giá trị nhạy cảm của fixture. Trong 15 trial Workflow thiếu approval hoặc có approval không hợp lệ, ledger ghi 0 refund. Crash suite đạt `20/20`. Commit `7f84ceb` chứa code và hai báo cáo chính. Chạy lại benchmark và crash tại mốc này cho JSON khớp hoàn toàn với bản đã commit.

## Giới hạn

Benchmark đo chi phí mô phỏng với MockLLM và để latency ở `unavailable`. `hidden_selfcheck.json` chỉ là tự kiểm 600 trial không nhãn, với `graded_trials=0`. Điểm hidden chính thức và các chỉ số must-pass trên bộ hidden do grader của giảng viên xác định.
