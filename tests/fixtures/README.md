# SHACL 正反例夹具（tests/fixtures/）

- 所有夹具均仅使用合成占位编码与公开标准词条，**严禁**真实 VIN、个人身份信息（PII）或消费者投诉/问诊原文。
- `positive/`：每个 LinkML v3 模块至少 1 份合规示例图，运行 `pytest tests -q` 必须全部 `conforms == True`。
- `negative/`：每个模块与手写补充规则（隐私 VIN 拦截、禁词谓词拦截、MOT `k<5` 抑制校验、CandidateLink 越界分数校验、缺失必填属性）各 1 份违例图，运行 `pytest tests -q` 必须全部 `conforms == False` 且命中预期形状/错误消息。
