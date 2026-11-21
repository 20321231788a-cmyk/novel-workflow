# 长篇网文创作技能

> 面向中文长篇网文的 Codex 技能，覆盖新书初始化、文风锚点、排纲、续写和改稿。每本书独立维护文风、设定与创作进度。

[技能入口](SKILL.md) · [快速安装](#快速安装) · [使用示例](#使用示例)

## 创作流程

```text
书名与题材 / 已有书稿
  │
  ▼  独立建书与定调
     建立项目 AGENTS.md 和专属技能，按作者选择配置文风锚点
  │
  ▼  排纲
     锁定因果、关键场面、章节结果与下章期待
  │
  ▼  正文与轻量品控
     Pass 1 根据章纲和上章结尾起草 → Pass 2 回读故事、核对事实、校验字数
  │
  ▼  归档与衔接
     同步人物和资源变化，记录本章结果，承接下一章
```

## 核心功能

| 功能 | 实际产出 |
| --- | --- |
| 文风锚点 | 根据作者样章、参考文本或 A/B 试写，沉淀节奏、叙述口吻和语感样段。参考文本提取后再脱敏重构。[文风锚点指南](references/文风锚点与自动入库.md) |
| 留白排纲 | 在章纲里写清本章从何处切入、推进哪些关键场面、人物处境如何变化。需要构思高潮时可查技法目录。[章纲模板](references/章纲模板.md) · [技法目录](references/实战技法速查目录.md) |
| 两遍式正文 | 起草时调取本书文风、当前章纲、上章末尾和相关设定。初稿回读检查因果与连续性，默认每章至少 1700 个有效汉字。[正文创作指南](references/good-writing.md) |
| 校对与同步 | 词句校对保留原稿的情绪和叙事意图。章节落盘后同步明确发生的人物、设定和资源变化。[表达诊断](references/表达规范库/README.md) · [同步流程](references/同步流程.md) |

## 目录结构

```text
novel-workflow/
├── SKILL.md                           技能入口与工序路由
├── agents/openai.yaml                 Codex 显示名称与启动提示
├── references/                        文风锚点、章纲、叙事技法与表达诊断
└── scripts/
    ├── analyze_style_sample.py        样章节奏和表达特征分析
    ├── check_chapter_length.py        有效正文汉字核验
    ├── check-ai-patterns.js           表达问题只读扫描
    ├── compare_drafts.py              对照原稿与改稿
    ├── export_technique_catalog.py    导出技法速查目录
    └── quick_count.py                 快速统计文件汉字数
```

## 快速安装

在小说工作区根目录运行以下命令，然后打开或重启该工作区的 Codex 会话。技能名为 `$novel-workflow`。

```sh
gh repo clone 20321231788a-cmyk/novel-workflow .agents/skills/novel-workflow
```

样章分析、字数校验等脚本使用 Python 标准库。按需运行表达扫描时需要 Node.js。

## 使用示例

**建书并定调**

> 使用 $novel-workflow 在当前工作区初始化一本都市悬疑长篇。建书后先让我设置文风锚点。

**规划章节**

> 使用 $novel-workflow 根据现有细纲排第 4–6 章。请写清每章的起因、关键场面、人物处境变化和下一章的期待。

**续写并校验**

> 使用 $novel-workflow 接上第 6 章末尾，按已确认的第 7 章章纲写正文。写完核对知情边界和道具去向，再验有效汉字数。

## 同系列

[经纬AI，一键漫剧创作 skill](https://github.com/20321231788a-cmyk/jingwei-ai-manju-skill)
