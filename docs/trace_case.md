# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>`, run ID trong report |
| Triệu chứng | Grader nào fail; reply nói gì so với ledger ghi gì |
| Bước sai đầu tiên | Số thứ tự event + kind + trích payload (≤1 dòng) |
| Vì sao là bước *đầu tiên* | Các bước trước đó đúng ra sao (dẫn số event) |
| Failure mode | Mã FM-xx trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim@seed trên shape `fixed`: bước đó khác thế nào |
| Regression test | Tên test + grader/assert nào bắt được; đã thấy fail trên variant lỗi và pass trên `fixed` chưa |
| Chưa chắc chắn | Điều trace không chứng minh được |

## Case của nhóm: FM-05 pre_deducted trên C-014

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-014@11` (run ID `R-seeded_regression-C-014-s11`). Lỗi lặp lại ở cả 5 seed 11/22/33/44/55. |
| Triệu chứng | Grader Lab 8 báo FAIL `proposal_mismatch`. **Ledger** ghi `refund_vnd=90000` trong khi nhãn là 120.000. **Reply** lại nói "đã hoàn 120.000đ", nên đọc reply thì tưởng đúng. Status `resolved` khớp nhãn. |
| Bước sai đầu tiên | **#5 `proposal` `{"amount_vnd": 120000}`**: agent tự trừ 30.000 đã hoàn rồi mới truyền số này vào `issue_refund`. |
| Vì sao là bước *đầu tiên* | #1 `handoff` đúng scope. #2 `investigator` đọc đúng O-515 (`delay_days=5`, `damage_verified=true`, không có `model_override`). #3 `quote` 150.000 đúng luật "lấy số lớn hơn" (SHIP 30.000 với DMG 150.000). #4 `refund_history` đọc đúng `refunded_vnd=30000`. Bước #5 là lần đầu một con số khác quote đi vào host. Host đã tự trừ phần đã hoàn theo trần của đơn (`business_rules.md`), nên bị trừ hai lần: 120.000 − 30.000 = 90.000. |
| Failure mode | **FM-05** pre_deducted (layer orchestration/state). Hệ quả phụ: reply lệch ledger, cùng triệu chứng với FM-08. |
| Đối chứng | `fixed C-014@11`: #1–#3 giống hệt, **không có** event `proposal` hay `refund_history`. Quote 150.000 đi thẳng vào host, ledger 120.000, reply 120.000đ. Lab 8 PASS. |
| Regression test | `src/tests/test_lab9_trace_case.py`: `test_fm05_c014_first_wrong_step_is_proposal` assert #4 `refund_history`=30.000, #5 `proposal`=120.000, ledger 90.000, và guard `no_pre_deduction` **fail**. `test_fm05_c014_fixed_passes_same_guard` assert guard **pass** và Lab 8 PASS trên `fixed`. Kèm `test_fm03_c002_db_fact_kept` cho anchor FM-03 (swarm C-002@55 và seeded C-002@11 có `model_override` ở #3, `fixed` thì không). Lệnh chạy: `python -m pytest -q -m student -o addopts= tests/test_lab9_trace_case.py` → 5 passed. |
| Chưa chắc chắn | Trace không cho thấy *vì sao* agent trừ trước, vì MockLLM không ghi lý do. Chỉ biết event `proposal` xuất hiện ngay sau `refund_history`. Trace cũng không phân biệt được lỗi trừ trước với lỗi "host trừ thiếu", nên kết luận dựa vào luật trong `business_rules.md` (shape phải truyền quote đầy đủ). Với C-013 cùng lỗi này cho đề xuất 0 → `denied`. Status vẫn đúng, chỉ `proposal_amount` lệch, nên chỉ grader so `proposal_amount` mới bắt được. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
