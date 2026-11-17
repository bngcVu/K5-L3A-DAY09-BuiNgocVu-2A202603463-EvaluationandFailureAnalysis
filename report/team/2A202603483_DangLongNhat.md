# Báo cáo cá nhân — 2A202603483_DangLongNhat

## 1. Thông tin thành viên

- Họ tên: Đặng Long Nhật
- MSSV: 2A202603483
- Email: nhatlong12cc@gmail.com
- GitHub: [Nhatlong2](https://github.com/Nhatlong2)

## 2. Phần việc phụ trách

TV3 phụ trách Shape C `orchestrator`, investigator chỉ đọc, handoff theo allowlist và trace theo hợp đồng v1.

## 3. Đóng góp cụ thể

- Commit `a56d25e` triển khai `src/lab8/shapes/orchestrator.py`. Commit `0020613` bổ sung `src/tests/test_orchestrator_handoff.py`.
- Investigator được cấp duy nhất `lookup_order`. Orchestrator tính quote từ dữ liệu đơn rồi chuyển quote đầy đủ cùng `crash_at` cho host. Kết quả lưu `proposal_amount` tách biệt với số tiền thực tế trong ledger.
- Test bổ sung kiểm tra payload investigator nhận, quyền đọc, trace an toàn và trace khi claim không tồn tại.

## 4. Bằng chứng

Sau khi merge Shape C, chạy lại hai bộ test trong `src/` trên Windows.

| Lệnh | Ca qua | Ca bị lọc | Thời gian |
| --- | ---: | ---: | ---: |
| `python -m pytest -q` | 199 | 248 | 24.75s |
| `python -m pytest -q -m student -o addopts=` | 248 | 199 | 29.20s |

- Ma trận student có 62 ca cho Shape C. Bộ test mặc định gồm hai ca trong `src/tests/test_orchestrator_handoff.py` kiểm tra quyền đọc, payload bàn giao và trace, kể cả khi claim không tồn tại.
- Rà 210 trace public của Workflow, Single Agent và Orchestrator từ 14 claim × 5 seed. Không tìm thấy canary, giá trị header hoặc thông tin cá nhân trong fixture.
- Với run `R-orchestrator-C-012-s11`, thử cả ba điểm crash trên DB riêng. Mỗi lần chạy lại ghi đúng một refund 35.000 VND và một audit `refund_committed`.

## 5. Công cụ AI đã dùng

Codex hỗ trợ viết test và đối chiếu bằng chứng. 

## 6. Tự đánh giá

Shape C đạt yêu cầu TV3 trên bộ public. Investigator chỉ dùng `lookup_order` trong phạm vi `principal_id`. Orchestrator tính quote từ dữ liệu đơn và gửi quote đầy đủ cho host kiểm tra phê duyệt, áp trần và ghi ledger. Các nhánh kết thúc sớm vẫn ghi trace qua `finish()`.

Hai test bổ sung kiểm tra dữ liệu thực tế trong handoff và trace. Lượt chạy lại sau merge trên Windows xác nhận kết quả trên bộ test host và ma trận student. Phạm vi tự đánh giá là dữ liệu public với MockLLM.
