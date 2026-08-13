# -*- coding: utf-8 -*-
"""
prompt 统一管理包
===========================
每部手机一个文件（phoneN.py），汇总该手机的游戏列表 + prompt 映射：
- phone0.py : 手机0（最初六款通用模板游戏：和平精英、王者荣耀、蛋仔派对、小小蚁国、完美世界、三角洲行动）
- phone1.py : 手机1（白 RN-38 1002650，5款专属/片段游戏）
- phone2.py : 手机2（蓝 RN-21 1002622，逆战：未来）
- phone3.py : 手机3（蓝 1002630，蛋仔派对、逆水寒）
- phone4.py : 手机4（黑 RN-37 1002649，7款游戏）
- phone5.py : 手机5（黑 RN-30 1002633，大话西游）
- phone6.py : 手机6（黑 RN-22 1002623，崩坏：星穹铁道、洛克王国：世界）
- phone7.py : 手机7（黑 RN-25 1002626，明日方舟、恋与深空）
- 以后新增手机：新建 phoneN.py（导出 GAMES / GAME_PROMPT_MAPPING / DEFAULT_PROMPT）
  并在下方 PHONES 注册

run.py 使用方式：
    from prompts import PHONES
    phone_cfg = PHONES[phone_num]
    for game in phone_cfg["games"]:
        task = phone_cfg["get_prompt"](game)
"""

from prompts import phone0, phone1, phone2, phone3, phone4, phone5, phone6, phone7
from prompts.phone0 import GAMES as GAMES_0, GAME_PROMPT_MAPPING as MAPPING_0, DEFAULT_PROMPT as DEFAULT_0
from prompts.phone1 import TASK_HEPING, GAMES as GAMES_1, GAME_PROMPT_MAPPING as MAPPING_1, DEFAULT_PROMPT as DEFAULT_1
from prompts.phone2 import GAMES as GAMES_2, GAME_PROMPT_MAPPING as MAPPING_2, DEFAULT_PROMPT as DEFAULT_2
from prompts.phone3 import GAMES as GAMES_3, GAME_PROMPT_MAPPING as MAPPING_3, DEFAULT_PROMPT as DEFAULT_3
from prompts.phone4 import GAMES as GAMES_4, GAME_PROMPT_MAPPING as MAPPING_4, DEFAULT_PROMPT as DEFAULT_4
from prompts.phone5 import GAMES as GAMES_5, GAME_PROMPT_MAPPING as MAPPING_5, DEFAULT_PROMPT as DEFAULT_5
from prompts.phone6 import GAMES as GAMES_6, GAME_PROMPT_MAPPING as MAPPING_6, DEFAULT_PROMPT as DEFAULT_6
from prompts.phone7 import GAMES as GAMES_7, GAME_PROMPT_MAPPING as MAPPING_7, DEFAULT_PROMPT as DEFAULT_7
from prompts.phone6 import PROMPT_XQTD, PROMPT_LKWORLD


def _make_phone_config(games, mapping, default_prompt) -> dict:
    """构造单部手机的配置字典（含按游戏取 prompt 的函数）。"""

    def get_prompt(game: str) -> str:
        custom = mapping.get(game)
        if custom:
            # 映射值可能是专属完整 prompt，也可能是带 %s 的模板变体
            # 含 %s 时替换游戏名（如 TASK_HEPING_QQ），否则直接返回
            if "%s" in custom:
                return custom % game
            return custom
        return default_prompt % game

    return {
        "games": games,
        "game_prompt_mapping": mapping,
        "default_prompt": default_prompt,
        "get_prompt": get_prompt,
    }


# ============================================================
# 手机编号 → 配置
# ============================================================
PHONES = {
    0: _make_phone_config(GAMES_0, MAPPING_0, DEFAULT_0),
    1: _make_phone_config(GAMES_1, MAPPING_1, DEFAULT_1),
    2: _make_phone_config(GAMES_2, MAPPING_2, DEFAULT_2),
    3: _make_phone_config(GAMES_3, MAPPING_3, DEFAULT_3),
    4: _make_phone_config(GAMES_4, MAPPING_4, DEFAULT_4),
    5: _make_phone_config(GAMES_5, MAPPING_5, DEFAULT_5),
    6: _make_phone_config(GAMES_6, MAPPING_6, DEFAULT_6),
    7: _make_phone_config(GAMES_7, MAPPING_7, DEFAULT_7),
}

# 兼容直接引用（供 run.py 旧写法或其他工具使用）
__all__ = [
    "PHONES",
    "TASK_HEPING",
    "PROMPT_XQTD",
    "PROMPT_LKWORLD",
    "phone0",
    "phone1",
    "phone2",
    "phone3",
    "phone4",
    "phone5",
    "phone6",
    "phone7",
]
