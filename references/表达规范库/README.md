# 表达规范库的调用与边界

版本：expression-v2-20261012。manifest.json 列出三份实际加载文件：wording.json（遣词10项）、syntax.json（句式10项）、prohibited.json（核实后禁止7项）。规则含触发线索、诊断、修正方向、保留条件及离线证据 ID，不收录参考原句或生成替换句。

在 Pass 2（编辑态审校）或词句校对阶段，由 `scripts/check-ai-patterns.js` 只读加载同一批 JSON 进行候选定位，再结合抽象规则人工复核。检测器为候选定位器：review 要结合上下文判断；prohibit_after_verification 表示确认条件成立后必须避免，程序不会自动作语义裁决。没有 detectors 的规则列入 manual_checks，仍须人工核对。所有B类同时列入 semantic_checks，触发式只覆盖部分线索，必须全文人工查来源，未命中不等于通过。

从技能根目录运行：

```text
node scripts/check-ai-patterns.js --check --json --library-dir references/表达规范库 --output <写作校验报告.json> <现有正文路径...>
```

项目存在本书适配.json 时，显式追加 --profile references/表达规范库/本书适配.json。公共模板不携带此文件，不把某本书的槽位、年龄或叙述形式传给新书。

输出记录库版本和库文件哈希、输入哈希、章节、物理行列、规则 ID、命中与保留条件。Markdown 标题、表格、围栏等排除；正常对白、系统括号和拟声仍参与定位。窗口不越过章节；原本TXT的两个全角空格段首按独立段识别，合订总标题不计为章标题。默认只读、无写回、无AI评分；配置错误必须修复，不能当作无命中。

本库是负向病灶与事实越权定位器，不是封闭词汇白名单。在线写作的正面语感、口吻与句式呼吸以各书本地 `references/本书文风锚点.md` 为准；原稿中通顺且符合人物的鲜活表达一律保留。
