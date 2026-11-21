"""Export approved abstract technique cards into a categorized Markdown catalog.

Reads directly from `references/techniques-v2.json` with zero vector or database dependencies.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CATEGORY_GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "一、开局动机、奖励转化与设定显形",
        "适用于新书开篇立人设、金手指/系统发奖落地、日常切入超凡事件、战后结算转入下一章钩子。",
        ["luna-v2-004-01", "luna-v2-000-01", "luna-v2-003-02", "luna-v2-008-03", "luna-v2-005-03"],
    ),
    (
        "二、实战交锋、战术反制与公开立威",
        "适用于单挑打脸、越级反杀、能力克制破局、诱敌变招及公开场合震慑围观者。",
        ["luna-v2-006-02", "luna-v2-007-01", "luna-v2-004-03", "luna-v2-008-02", "luna-v2-001-02", "luna-v2-010-01", "luna-v2-009-02"],
    ),
    (
        "三、情报对话、试探取证与智斗拆解",
        "适用于利益谈判、套话摸底、异常规则试探，以及当众用现场证据击碎反派自信。",
        ["luna-v2-001-01", "luna-v2-007-02", "luna-v2-002-01", "luna-v2-009-01", "luna-v2-011-01", "luna-v2-012-02"],
    ),
    (
        "四、组织博弈、风险决断与多线加压",
        "适用于私人摩擦升级为公共冲突、团队/势力内部拍板、多线并行施压与连环突围。",
        ["luna-v2-003-03", "luna-v2-005-01", "luna-v2-008-01", "luna-v2-009-03", "luna-v2-007-03", "luna-v2-012-01", "luna-v2-003-01"],
    ),
    (
        "五、关系拉扯、人情代价与情感外化",
        "适用于信任破冰、身份相认、偏爱站队、两难人情抉择及把内心情绪外化为实际行动代价。",
        ["luna-v2-001-03", "luna-v2-000-02", "luna-v2-006-01", "luna-v2-011-03", "luna-v2-002-02"],
    ),
    (
        "六、时间跨度压缩与阶段尾声收束",
        "适用于闭关苦修/创业筹备的时间跳跃，以及大高潮落定后的情感余波与阶段收尾。",
        ["luna-v2-002-03", "luna-v2-011-02", "luna-v2-012-03"],
    ),
]


def build_markdown(cards: dict[str, dict]) -> str:
    lines: list[str] = [
        "# 实战技法速查目录（排纲期直接选用）",
        "",
        "本目录由离线蒸馏批准的 33 张抽象技法卡（`techniques-v2`）按戏剧功能分类导出，**彻底取代向量检索**。",
        "",
        "## 使用原则（专业作家排纲法）",
        "",
        "1. **在排章纲阶段选用，不在写正文前盲抽**：构思每章六栏章纲时，先明确本章核心戏剧任务（是打脸立威、奖励落地、谈判套话还是关系破冰），再从下方对应分组挑选 **1—2 项** 最契合的技法，将其节拍融入章纲的“技法与情绪”与“主角行动”栏。",
        "2. **服务具体人物与爽点，拒绝静态比例教条**：卡片中的推进节拍是戏剧骨架参考，心理、动作、对白和解释的实际篇幅随场面呼吸动态起伏，不按固定百分比凑字数，也不做写后段落字符偏移自评。",
        "3. **零原句依赖**：目录仅保留可跨题材迁移的叙事机制，具体遣词造句与腔调一律服从本书《本书文风锚点》。",
        "",
    ]

    used: set[str] = set()
    for title, desc, card_ids in CATEGORY_GROUPS:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"> {desc}")
        lines.append("")
        for cid in card_ids:
            card = cards.get(cid)
            if not card:
                continue
            used.add(cid)
            lines.extend(_format_card(cid, card))

    leftovers = [cid for cid in sorted(cards) if cid not in used]
    if leftovers:
        lines.append("## 七、其他补充技法")
        lines.append("")
        for cid in leftovers:
            lines.extend(_format_card(cid, cards[cid]))

    return "\n".join(lines).rstrip() + "\n"


def _format_card(cid: str, card: dict) -> list[str]:
    best_for = " / ".join(card.get("best_for", []))
    structure = " → ".join(s.rstrip("。.") for s in card.get("structure", []))
    methods = "；".join(s.rstrip("。.") for s in card.get("methods", []))
    avoid = "；".join(s.rstrip("。.") for s in card.get("avoid", []))
    dialogue = str(card.get("dialogue_pattern", "")).strip()
    action = str(card.get("action_pattern", "")).strip()
    return [
        f"### `{cid}` {card['name']}",
        f"- **适用场面**：{best_for}",
        f"- **戏剧目标与情绪机制**：{card['goal']} {card['emotion_mechanism']}",
        f"- **推进节拍**：{structure}",
        f"- **落地抓手**：{methods}（动作：{action}｜对白：{dialogue}）",
        f"- **避坑禁忌**：{avoid}",
        "",
    ]


def main() -> int:
    workflow_root = Path(__file__).resolve().parent.parent
    default_json = workflow_root / "references" / "techniques-v2.json"
    default_out = workflow_root / "references" / "实战技法速查目录.md"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=default_json)
    parser.add_argument("--output", type=Path, default=default_out)
    args = parser.parse_args()

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    cards = payload.get("cards", {})
    if not cards:
        raise SystemExit(f"No cards found in {args.source}")

    md = build_markdown(cards)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"Exported {len(cards)} cards to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
