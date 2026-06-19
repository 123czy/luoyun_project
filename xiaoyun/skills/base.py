# -*- coding: utf-8 -*-
#
# 极简「技能(Skill)」系统：把 prompt 从巨型拼接字符串，拆成文件化、可组合、可注册的技能单元。
#
# 注意（诚实定位）：luoyun 是确定性管道，不是模型自主选技能的 agent。
# 所以这里的 Skill ≠ Claude 那种自动加载的技能，而是「结构化的 prompt 模块系统」：
# 每个 Skill 是一段带名字/描述的指令文本，由 compose() 按顺序拼装成最终 prompt。
#
# xiaoyun 用本系统组装出的 prompt 与 qiaoyun 的巨型字符串**逐字一致**（见 skills/library.py
# 的组装顺序 + tests 的 parity 断言），从而保证 A/B 只比「栈」、人设 100% 不变。

from typing import List, Union, Dict


class Skill:
    """一个 prompt 技能单元：name 唯一标识，text 为指令文本，description 供检索/文档。"""

    def __init__(self, name: str, text: str, description: str = ""):
        self.name = name
        self.text = text
        self.description = description

    def __repr__(self):
        return f"<Skill {self.name}>"


def compose(parts: List[Union[Skill, str]]) -> str:
    """
    按顺序把 Skill / 字面串拼成最终 prompt。
    用 '\\n'.join 实现：列表里放空串 '' 即代表 qiaoyun 原文中的空行（+ "\\n" + "\\n"）。
    """
    out = []
    for p in parts:
        if isinstance(p, Skill):
            out.append(p.text)
        elif isinstance(p, str):
            out.append(p)
        else:
            raise TypeError(f"compose() 只接受 Skill 或 str，收到 {type(p)}")
    return "\n".join(out)


class SkillRegistry:
    """技能注册表，便于按名取用、列举、文档化。"""

    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        if skill.name in self._skills:
            raise ValueError(f"duplicate skill name: {skill.name}")
        self._skills[skill.name] = skill
        return skill

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def all(self) -> Dict[str, Skill]:
        return dict(self._skills)
