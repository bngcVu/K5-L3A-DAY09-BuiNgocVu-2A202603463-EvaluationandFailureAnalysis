# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (backend REPLAY: verdict của judge lưu sẵn trong CSV, không cần key).
Lớp dương là **FAIL** (`stats.POS`): việc của judge là *tìm ra* reply hỏng. Vì vậy Recall = độ nhạy với lỗi, Precision = tỉ lệ cờ FAIL của judge là đúng.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | **0.757** | **0.857** | **0.800** | ✅ PASS (exit 0) | **dùng**, chỉ để giám sát (non-blocking) |
| helpful | 100 | 0.375 | 1.000 | **0.300** | ❌ FAIL (exit 1), Recall và κ dưới sàn | **loại**, không dùng làm gate |

Ma trận nhầm lẫn (FAIL = dương):

| | tp | fp | fn | tn | Sensitivity (=R) | Specificity (TNR theo PASS) | FAIL quan sát → hiệu chỉnh Rogan-Gladen | CI 95% (bootstrap 2000, rng 2027) |
|---|---|---|---|---|---|---|---|---|
| tone_ok | 24 | 4 | 6 | 66 | 0.800 | 0.943 | 0.28 → **0.300** | [0.230, 0.393] |
| helpful | 9 | 0 | 21 | 70 | 0.300 | 1.000 | 0.09 → **0.300** | [0.193, 0.630] |

Đọc bảng:

- **Judge helpful rất "dễ dãi"**: chỉ cắm cờ 9% reply, trong khi người gắn nhãn thấy 30% hỏng. Rogan-Gladen kéo con số về 0.30, nhưng CI rộng tới [0.19, 0.63]. Mẫu số `sens + spec − 1 = 0.30` quá nhỏ nên khuếch đại sai số, đúng như cảnh báo "TPR thấp ⇒ CI rộng". Không thể dùng một con số rộng như vậy để chặn merge.
- **Judge tone** có `sens + spec − 1 = 0.743`, CI hẹp hơn hẳn. Tỉ lệ hiệu chỉnh 0.300 khớp đúng tỉ lệ FAIL của người (30/100), nên judge tone là thước đo dùng được.

## Audit thủ công: 10/10 bất đồng của tone + nhóm bất đồng của helpful

### tone_ok (cả 10 ca)

| # | Case | Reply (rút gọn) | Judge nói | Người nói | Ai đúng? | Sửa rubric |
|---|---|---|---|---|---|---|
| 1 | H-008 | "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | **Người** | Thêm luật: xưng hô với khách phải là "anh/chị"/"quý khách". "em… nha" là FAIL dù thân thiện. Thêm H-008 làm ví dụ FAIL. |
| 2 | H-017 | "Dạ, bạn ơi LogiX đã hoàn… rồi nha." | PASS | FAIL | **Người** | Gộp vào luật xưng hô: "bạn ơi", "nha" là suồng sã. Mở đầu bằng "Dạ" không đủ để PASS. |
| 3 | H-029 | "…vui lòng chờ. … không cần nhắn thêm." | PASS | FAIL | **Người** | Judge chỉ nhìn kính ngữ ở đầu câu. Thêm luật: câu mệnh lệnh hoặc chặn khách liên hệ ("không cần nhắn thêm") là FAIL, kể cả khi có "Dạ, vui lòng". |
| 4 | H-042 | "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | **Người** | Judge phạt vì "thiếu xin lỗi". Thêm luật: không bắt buộc xin lỗi; ngắn, lễ phép, đủ ý là PASS. |
| 5 | H-051 | "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | **Người** | Thêm whitelist thuật ngữ CS LogiX cho phép ("refund"). Không phạt vì lẫn tiếng Anh nếu từ đó nằm trong whitelist. |
| 6 | H-063 | "…đã hoàn 20.000đ và sẽ hoàn thêm…" | PASS | FAIL | **Người**, nhưng **sai tiêu chí** | Đây là lỗi *nội dung* (hứa ngoài kết quả hệ thống, gần FM-08), không phải lỗi giọng. Bỏ khỏi rubric tone, chuyển sang grader code so reply với ledger. Không sửa prompt tone vì ca này. |
| 7 | H-070 | "…cho đơn O-909 ạ 😂😂" | PASS | FAIL | **Người** | Thêm luật: emoji cười trong ngữ cảnh khiếu nại hoặc hoàn tiền là FAIL. |
| 8 | H-081 | "Dạ, đơn O-107 chưa đủ điều kiện hoàn…" | FAIL | PASS | **Judge**, nhãn người sai | Cột `note` ghi người đọc nhầm ticket. **Sửa nhãn thành FAIL** trong bộ nhãn mới, không sửa rubric. Nếu sửa nhãn thì tp=25, fp=3, P≈0.893, R≈0.806. Không sửa CSV công khai vì test M2 khoá số tham chiếu. |
| 9 | H-088 | "Dạ, dạ, LogiX đã hoàn…" | FAIL | PASS | **Người** | Lỗi gõ lặp từ không làm hỏng giọng. Thêm luật: lỗi chính tả hoặc gõ nhỏ không phải lỗi tone. |
| 10 | H-094 | "Da, LogiX da hoan… don O-341…" | PASS | FAIL | **Người** | Thêm luật: tiếng Việt mất dấu (dịch máy) là FAIL vì thiếu chuyên nghiệp. Thêm H-094 làm ví dụ FAIL. |

Tổng kết tone: judge sai **9/10** ca. FN = 6 (judge bỏ lọt: #1, 2, 3, 6, 7, 10) và FP = 3 (#4, 5, 9); riêng H-081 nhãn người sai.

- **Judge quá dễ** ở các tín hiệu suồng sã: xưng hô, emoji, giọng ra lệnh, mất dấu. Judge chấm theo dấu hiệu bề mặt "Dạ… ạ".
- **Judge quá khắt khe** ở các điểm không phải lỗi tone: thiếu xin lỗi, từ "refund", lỗi gõ.

Cả hai hướng đều sửa được bằng luật tường minh và ví dụ lấy từ split train. Theo `validate-evaluator`, ví dụ few-shot **chỉ được lấy từ split train**, không lấy từ các ca dev/test ở trên.

### helpful (21 bất đồng, đều là FN: judge PASS, người FAIL)

| Nhóm | Số ca | Ví dụ | Ai đúng? | Hành động |
|---|---|---|---|---|
| A. Reply nói **số tiền khác ledger**, kèm xin lỗi dài lặp lại | 13 (HL-016/028/035/041/043/053/058/070/072/074/090/096/098) | HL-016: "…xin lỗi… đã hoàn 55.000đ cho đơn O-404. Một lần nữa xin lỗi…", trong khi ledger ghi 35.000đ | **Người** | Judge bị **thiên kiến độ dài/lịch sự** (verbosity bias): reply càng dài, càng nhiều lời xin lỗi thì càng được PASS. Judge **không nhìn thấy ledger**, nên về nguyên tắc không thể chấm đúng. |
| B. Reply ngắn, nói **số tiền khác ledger** | 5 | HL-015 "đã hoàn 55.000đ cho đơn O-112", ledger 40.000đ; HL-020; HL-062; HL-087; HL-100 | **Người** | Đây là FM-08 (misreport), lỗi khách quan, **phải chấm bằng code** (regex số tiền trong reply so với `snapshot.refund_vnd`). Đưa vào metric FM-08 ở M3, không dùng judge. |
| C. Reply mơ hồ, **không có thông tin** | 3 | HL-047/091/097: "Ok bạn, đơn O-xxx xử lý rồi nhé." | **Người** | Đây là phần "helpful" đúng nghĩa, cần diễn giải. Rubric mới: PASS chỉ khi reply nêu (1) kết quả (hoàn/từ chối/cần thêm thông tin), (2) số tiền nếu có hoàn, (3) bước tiếp theo hoặc thời gian. Thiếu (1) là FAIL. |

**18/21** lỗi bị bỏ sót (nhóm A và B) là lỗi đối chiếu với ledger, judge không có dữ liệu để kiểm. Đó là lý do gốc khiến Recall chỉ 0.30, không phải do câu chữ của prompt.

## Kết luận

- **Loại `helpful` khỏi gate.** Recall = 0.30 (tp 9 / fn 21) nghĩa là judge bỏ lọt 70% reply hỏng, và κ = 0.375 < 0.6. Precision = 1.0 trông đẹp nhưng chỉ vì judge gần như không bao giờ nói FAIL (9/100). Trong lab này một judge dễ dãi như vậy sẽ cho qua đúng loại lỗi đáng sợ nhất: báo sai số tiền với khách. Dùng nó làm gate thì regression FM-08 sẽ được merge kèm dấu "đã kiểm".
- **Tách tiêu chí `helpful`.**
  - (a) *Số tiền khớp ledger*: grader **code** cho FM-08 (M3, `metric_spec.yaml`), blocking.
  - (b) *Đủ thông tin* (nhóm C): viết lại judge với rubric 3 ý ở trên, gắn nhãn lại và calibrate lại trước khi dùng. Trong lúc chờ thì non-blocking.
- **Giữ `tone_ok` nhưng non-blocking.** Judge qua sàn nhưng sai có hệ thống ở xưng hô và emoji (6 FN). Sửa rubric theo 7 luật ở bảng tone rồi chạy lại calibration.
- **Tiền và approval không bao giờ giao cho judge**, đúng quy tắc trong `failure_taxonomy.md`.

### Rủi ro còn lại

- **Chưa có held-out test thật.** Judge chỉ được kiểm trên dữ liệu replay đã công khai, và 100 dòng này vừa dùng để đo vừa dùng để đọc bất đồng. Theo `validate-evaluator`, các số trên là số **dev** (lạc quan). Sau khi sửa rubric cần nhãn người mới và chia train/dev/test (khoảng 15/45/40, stratify theo nhãn), rồi chạy test đúng **một lần**.
- **Mất cân bằng lớp.** Mỗi bộ có 30 FAIL / 70 PASS. 30 ca FAIL là mức tối thiểu để đo Recall. CI của helpful rộng cho thấy cần thêm ca FAIL (mục tiêu khoảng 50/50 theo skill).
- **Nhãn người cũng sai.** Ví dụ H-081. Cần người thứ hai gắn nhãn độc lập 20–50 ca và đo κ giữa hai người (κ dùng đúng chỗ là đo đồng thuận người–người) trước khi coi nhãn là ground truth.
- **Replay không bắt được drift của model.** Khi chuyển sang judge thật phải pin snapshot model có ngày cụ thể và calibrate lại mỗi lần đổi prompt hoặc model.
