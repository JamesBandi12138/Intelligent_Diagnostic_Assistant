from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeCard:
    card_id: str
    title: str
    aliases: tuple[str, ...]
    summary: str
    red_flags: tuple[str, ...]
    follow_up_prompts: tuple[str, ...]
    department_candidates: tuple[str, ...]
    source_note: str


KNOWLEDGE_CARDS: tuple[KnowledgeCard, ...] = (
    KnowledgeCard(
        card_id="abdominal_pain",
        title="腹痛导诊卡",
        aliases=("腹痛", "肚子疼", "胃痛", "肚子痛", "右下腹痛", "上腹痛"),
        summary="腹痛导诊优先确认疼痛位置、起病方式，以及发热、呕吐、腹泻、黑便、压痛等红旗症状。",
        red_flags=("持续加重", "固定右下腹", "发热", "反跳痛", "黑便", "持续呕吐"),
        follow_up_prompts=(
            "更具体在上腹、肚脐周围、右下腹还是固定在某一侧？",
            "有没有发热、呕吐、腹泻、黑便，或者按压时明显更痛？",
        ),
        department_candidates=("消化内科", "普外科", "急诊科"),
        source_note="local-triage-card+QASystemOnMedicalKG-reference",
    ),
    KnowledgeCard(
        card_id="headache",
        title="头痛导诊卡",
        aliases=("头痛", "头疼", "脑袋疼", "偏头痛", "头晕"),
        summary="头痛导诊优先确认是否突发剧烈，以及是否伴随视物异常、说话不清、肢体无力、呕吐或发热。",
        red_flags=("突发剧烈", "视物模糊", "说话不清", "肢体无力", "反复呕吐", "高热"),
        follow_up_prompts=("这次头痛是突然一下子很重，还是慢慢加重？同时有没有视物模糊、说话不清、肢体无力、呕吐或发热？",),
        department_candidates=("神经内科", "急诊科"),
        source_note="local-triage-card+QASystemOnMedicalKG-reference",
    ),
    KnowledgeCard(
        card_id="eye_discomfort",
        title="眼部不适导诊卡",
        aliases=("眼痛", "眼睛疼", "眼睛不舒服", "眼红", "眼痒", "异物感", "视物模糊"),
        summary="眼部不适导诊优先确认是否视力下降、畏光、分泌物增多、外伤史或隐形眼镜相关刺激。",
        red_flags=("视力下降", "畏光", "眼外伤", "化学刺激", "剧烈眼痛"),
        follow_up_prompts=("有没有视力下降、畏光、明显分泌物增多、外伤，或者最近佩戴隐形眼镜后加重？",),
        department_candidates=("眼科", "急诊科"),
        source_note="local-triage-card+QASystemOnMedicalKG-reference",
    ),
    KnowledgeCard(
        card_id="chest_pain",
        title="胸痛导诊卡",
        aliases=("胸痛", "胸口痛", "胸闷", "胸前区疼痛"),
        summary="胸痛导诊优先确认压榨感、活动后加重、呼吸相关疼痛，以及出汗、气短、放射痛等急症信号。",
        red_flags=("压榨感", "大汗", "气短", "放射至左肩背", "持续胸痛"),
        follow_up_prompts=("胸痛是压榨样还是刺痛样？有没有活动后加重、大汗、气短，或者向左肩背部放射？",),
        department_candidates=("心内科", "呼吸内科", "急诊科"),
        source_note="local-triage-card+QASystemOnMedicalKG-reference",
    ),
    KnowledgeCard(
        card_id="throat_discomfort",
        title="咽喉不适导诊卡",
        aliases=("喉咙痛", "咽痛", "咽喉不适", "吞咽痛", "喉咙不舒服"),
        summary="咽喉不适导诊优先确认吞咽痛、发热、咳嗽、呼吸受限以及症状持续时间。",
        red_flags=("呼吸困难", "高热", "声音明显嘶哑", "吞咽困难"),
        follow_up_prompts=("除了咽喉痛，还有没有发热、咳嗽、吞咽困难，或者呼吸受限？",),
        department_candidates=("耳鼻喉科", "呼吸内科", "急诊科"),
        source_note="local-triage-card+QASystemOnMedicalKG-reference",
    ),
)
