# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R2 · Failure taxonomy |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Cemri và cộng sự (2025), *Why Do Multi-Agent LLM Systems Fail?*, NeurIPS Datasets and Benchmarks Track. Bằng chứng từ phân tích trace và benchmark các hệ đa tác tử. [Kỷ yếu NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html) |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | MAST xếp kiểm chứng sai dữ kiện hoặc quyết định quan trọng vào nhóm Task Verification, mã FM-3.3 (*Incorrect verification*). [Phụ lục A.3](https://proceedings.neurips.cc/paper_files/paper/2025/file/b1041e52d3be19f0a9bc491657488e4a-Paper-Datasets_and_Benchmarks_Track.pdf#page=25) |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Tác giả xây taxonomy từ 150 trace được chuyên gia phân tích, rồi áp dụng lên MAST-Data với hơn 1.600 trace thuộc 7 framework. Nhóm dùng taxonomy này để diễn giải một ca trong LogiX-VN. Phép đo của nhóm chỉ dùng 14 claim public và MockLLM. |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Tắt ghi đè `delay_days` từ ticket sẽ sửa ca `C-002` ở seed `55`. Dự kiến pass rate tăng từ `69/70` lên `70/70`, pass^5 từ `13/14` lên `14/14`, variance về gần 0 và cost/success giảm nhẹ. |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Chạy `swarm` trên hai bản sao cùng commit `680d725`. Giữ MockLLM, tool, mẫu prompt, 14 claim public, seed `11,22,33,44,55`, bảng giá, evaluator và SQLite mới cho từng trial. Chỉ tắt nhánh cho phép dùng số ngày từ ticket thay `delay_days` của order trong bản sao thử nghiệm. |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Nhóm gán FM-3.3 cho ca `C-002` seed `55` vì Swarm đọc được order có cấu trúc rồi thay số ngày trễ bằng giá trị ticket trước khi tính lại quote. Đối chiếu trạng thái và refund trong ledger với nhãn public, rồi so pass rate, pass^5, seed variance và cost/success. |

## Kết quả ablation

Hai lượt dùng cùng `lab8.benchmark` từ `src/` của hai bản sao. Trong bản sao lấy số ngày từ order, thêm `False and` ngay sau `if` ở điều kiện `REFERENCE_WEAKNESS` trong `src/lab8/shapes/swarm_reference.py`. Bước parse ticket và các tool vẫn chạy theo cùng cấu hình. File Swarm tham chiếu trong nhánh nộp giữ nguyên.

```cmd
python -m lab8.benchmark --shapes swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out R2_swarm_baseline.json
python -m lab8.benchmark --shapes swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out R2_swarm_order_only.json
```

Trong lần chạy kiểm chứng, `--out` trỏ đến hai tệp cùng tên trong thư mục tạm. Hai báo cáo JSON được đính kèm bằng chứng ablation.

| Lượt chạy | Pass rate | Pass^5 | Seed variance | Chi phí mô phỏng (VND/success) |
| --- | ---: | ---: | ---: | ---: |
| Swarm gốc | 69/70 (0.9857) | 13/14 (0.9286) | 0.000816 | 49.57 |
| Swarm dùng `delay_days` từ order | 70/70 (1.0000) | 14/14 (1.0000) | 0.000000 | 48.72 |

Run ID `R-swarm-C-002-s55` xuất hiện trong cả hai file vì tên shape, claim và seed giống nhau. Nhãn yêu cầu `denied` và refund `0 VND`. Bản gốc trả `resolved` và ghi một refund `20.000 VND`. Biến thể trả `denied` với `0 VND` và ledger không có refund cho claim đó. Kết quả khớp giả thuyết. Đây là trial duy nhất đổi trạng thái hoặc kết quả chấm trong 70 cặp.

Giới hạn của kết quả là một thay đổi nguồn dữ kiện trên bộ public và MockLLM. Chi phí là mô phỏng, latency để `unavailable`.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
