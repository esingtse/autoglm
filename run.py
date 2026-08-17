from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.model import ModelConfig
from phone_agent.config import get_messages
from phone_agent.memory import MemoryManager
from phone_agent.results import activity_notes_to_game_events
from phone_agent.device_factory import get_device_factory

# ============================================================
# prompt 统一从 prompts 包引入（手机配置 + prompt）
# 原 import 写法（保留注释备用）：
#   from prompts import TASK_HEPING, PROMPT_XQTD, PROMPT_LKWORLD
# ============================================================
from prompts import PHONES


from commonproto.pb4.proto.grpc import k2av_pb2
from commonproto.pb4.proto.ad.ad_pb2 import GameEvent
from utils.k2av_util import create_k2av_stub, send_k2av
import base64

import argparse
import json
import os

# ============================================================
# 模型配置（原硬编码版本，保留注释备用）
# ============================================================
# Gemini
# model_config = ModelConfig(
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
#     model_name="gemini-3.5-flash",
#     api_key=os.environ.get("GEMINI_API_KEY", ""),
#     extra_body={
#         "reasoning_effort": "low",   # 关闭思考；也可 "low" / "medium" / "high"
#     },
# )

# --- 从 run_config.json 读取模型配置（当前使用）---
def load_run_config() -> dict:
    """读取 run_config.json；文件不存在或解析失败时返回空配置，使用默认值。"""
    cfg_path = os.path.join(os.path.dirname(__file__), "run_config.json")
    if not os.path.isfile(cfg_path):
        print(f"⚠️ 未找到 {cfg_path}，使用默认模型配置")
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


_run_cfg = load_run_config()

model_config = ModelConfig(
    base_url=_run_cfg.get(
        "base_url", "https://generativelanguage.googleapis.com/v1beta/openai/"
    ),
    model_name=_run_cfg.get("model_name", "gemini-3.5-flash"),
    api_key=_run_cfg.get("api_key", ""),
    extra_body=_run_cfg.get(
        "extra_body", {"reasoning_effort": "low"}  # 关闭思考；也可 "low" / "medium" / "high"
    ),
)


# --- Memory: enable knowledge base learning ---
memory = MemoryManager()

# ============================================================
# 命令行参数
# ============================================================
_arg_parser = argparse.ArgumentParser(description="手机 Agent 采集脚本")
_arg_parser.add_argument(
    "--phone",
    type=int,
    default=1,
    choices=list(PHONES.keys()),
    help="无 devices 配置时回退：选择第几部手机配置（默认 1）",
)
_arg_parser.add_argument(
    "--device",
    type=str,
    default=None,
    help="只跑指定 device_id（默认跑 run_config.json 里 devices 全部）",
)
_args = _arg_parser.parse_args()

# ============================================================
# 原 TASK_HEPING 定义（已迁移至 prompts.py，保留注释备用）
# ============================================================
# TASK_HEPING = """
# 第一步：在屏幕中找到《%s》游戏图标并点击启动，等待游戏加载完成并进入主屏幕。加载过程中如有任何弹窗、提示框、权限请求或通知出现，自行寻找关闭、跳过、同意或确认按钮将其关闭，不需要请求用户协助，直到完全进入游戏主屏幕为止。如果遇到登录，优先选"QQ登录"
#
# 第二步：在屏幕中寻找与"活动"相关的入口，点击进入活动中心页面。
#
# 第三步：进入活动中心后，找到所有一级标签页，逐一点击每个一级标签，收集该标签下的所有内容，包括限时活动、定时开启的固定玩法、副本任务等，不做过滤，全部记录。所有一级标签都必须依次检查，不能跳过。
#
# 第四步：在每个含有活动内容的一级标签下，逐个查看所有活动。每进入一个活动的详情页并加载完成后，立即输出一条 Note 记录该活动，格式严格如下：
#
# 【一级标签名称 - 活动名称】
# 活动起始时间：xxx
# 活动结束时间：xxx
# 规则：xxx
# 奖励：xxx
#
# 注意：
# - 每看到一个活动就立刻输出一条独立的 Note，不要把多个活动塞进同一条 Note，也不要等全部看完再统一汇总。
# - 活动起始时间、活动结束时间都要从该活动详情页的实际内容中读取，只写日期（写到日），写不出的填"无"。不要把日期和钟点写成一个范围字符串，分开填到两个字段。例如详情页写"07.10 00:00-07.30 23:59"时，活动起始时间填"07.10 00:00"，活动结束时间填"07.30 23:59"。
# - Note 里的活动名称、规则、奖励都要从该活动详情页的实际内容中读取，未写明的字段填"无"。
# - 同一个活动不要重复输出 Note。
# - 输出 Note 后继续查看下一个活动；列表要从顶部持续向下滚动直到底部，确保所有活动都被加载并记录，不能遗漏。每次滚动后需等待内容加载完成再继续。
#
# 第五步：所有一级标签下的活动都逐条 Note 完毕后，结束游戏回到手机桌面，再执行 finish。不要在最后再输出一条汇总 Note。
# """.strip()


# task = TASK_WANGZHE
msgs = get_messages("cn")
output_dir = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(output_dir, exist_ok=True)

# --- Create k2av stub once ---
k2av_stub = create_k2av_stub(server="k2av-ag-alishh.umlife.net:31400", channel_options=[("grpc.default_authority", "k2av.ag.k8s.y.cn")])

# ============================================================
# 设备映射：物理手机（adb device_id）→ 逻辑配置（prompts/phone0~7）
# 从 run_config.json 的 devices 读取，串行轮流跑
# ============================================================
_devices = _run_cfg.get("devices", [])

# --- 检测当前实际连接的设备 ---
_connected_ids = {
    d.device_id for d in get_device_factory().list_devices() if d.status == "device"
}


def build_device_tasks():
    """构建待执行的 (device_id, phone_no) 列表。

    - 配置了 devices：按 run_config.json 顺序串行，跳过未连接设备，支持 --device 过滤。
    - 未配置 devices：回退到 --phone 单设备模式（device_id=None，操作 adb 默认设备）。
    """
    if _devices:
        tasks = []
        for entry in _devices:
            device_id = entry.get("device_id")
            phone_no = entry.get("phone")
            if phone_no not in PHONES:
                print(f"⚠️ 未知 phone 编号 {phone_no}（{device_id}），跳过")
                continue
            if _args.device and device_id != _args.device:
                continue
            if device_id not in _connected_ids:
                print(f"⚠️ 设备 {device_id} 未连接，跳过")
                continue
            tasks.append((device_id, phone_no))
        return tasks
    # 回退：单设备（不指定 device_id）
    return [(None, _args.phone)]


def run_one_game(agent, game, phone_cfg, device_output_dir):
    """在指定设备上跑一个游戏，解析 Note、保存 JSON 并发送 k2av。"""
    task = phone_cfg["get_prompt"](game)
    print(f"\n{'='*40}")
    print(f"开始处理: {game}")
    print(f"{'='*40}\n")

    # --- 清空该游戏目录下旧的截图，避免与新截图混在一起 ---
    game_shot_dir = os.path.join(device_output_dir, game, "screenshots")
    if os.path.isdir(game_shot_dir):
        for old_name in os.listdir(game_shot_dir):
            if old_name.lower().endswith(".png"):
                try:
                    os.remove(os.path.join(game_shot_dir, old_name))
                except OSError as e:
                    print(f"⚠️ 删除旧截图失败 {old_name}: {e}")

    result = agent.run(task)
    print(f"\n--- {game} 结果 ---")
    print(f"{msgs['result']}: {result}")

    # --- Parse Note output and save as proto-compatible JSON ---
    notes = agent.collected_notes
    if notes:
        all_events = activity_notes_to_game_events(notes, app_name=game)
        if all_events:
            print(f"\n📋 解析到 {len(all_events)} 条 GameEvent:")
            print(json.dumps(all_events[:3], ensure_ascii=False, indent=2))
            if len(all_events) > 3:
                print(f"... 及其他 {len(all_events) - 3} 条")
        else:
            print(f"\n⚠️ 无法解析 Note，保留原始文本")

        # Save to <device_output_dir>/<game>_activities.json
        output_path = os.path.join(device_output_dir, f"{game}_activities.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_events, f, ensure_ascii=False, indent=2)
        print(f"\n💾 已保存 {len(all_events)} 条 GameEvent → {output_path}")

        # --- Send to k2av ---
        for event in all_events:
            screenshot_bytes = b""
            screenshot_path = event.get("screenshot")
            if screenshot_path and os.path.isfile(screenshot_path):
                try:
                    with open(screenshot_path, "rb") as img_f:
                        screenshot_bytes = base64.b64encode(img_f.read())
                except OSError as e:
                    print(f"⚠️ 读取活动截图失败 {screenshot_path}: {e}")
            ge = GameEvent(
                app_id=event.get("app_id", ""),
                package=event.get("package", ""),
                app_name=event.get("app_name", ""),
                title=event.get("title", ""),
                content=event.get("content", ""),
                reward=event.get("reward", ""),
               event_date=event.get("event_date", ""),
               start_date=event.get("start_date", ""),
               end_data=event.get("end_data", ""),
               ts_crawl=event.get("ts_crawl", 0),
               screenshot=screenshot_bytes,
            )
            request = k2av_pb2.Request(topic="game_event", value=ge.SerializeToString())
            send_k2av(k2av_stub, request)
        print(f"📤 已发送 {len(all_events)} 条 GameEvent → k2av")

    # Reset Agent state
    agent.reset()
    print(f"\n{'='*40}")
    print(f"完成: {game}")
    print(f"{'='*40}\n")


# ============================================================
# 主循环：串行轮流跑每台设备（每台设备跑完它的全部游戏再换下一台）
# 原写法：for game in ACTIVE_GAME_LIST（单设备，已改为多设备串行）
# ============================================================
device_tasks = build_device_tasks()

if not device_tasks:
    print("⚠️ 没有可执行的设备，请检查 run_config.json 的 devices 配置或 adb 连接")
else:
    print(f"📱 共 {len(device_tasks)} 台设备待执行")

for device_id, phone_no in device_tasks:
    phone_cfg = PHONES[phone_no]
    game_list = phone_cfg["games"]
    # 每台设备独立输出目录，避免截图/结果互相覆盖
    device_output_dir = os.path.join(output_dir, device_id) if device_id else output_dir
    os.makedirs(device_output_dir, exist_ok=True)

    print(f"\n{'#'*40}")
    print(f"📱 设备 {device_id or '(默认设备)'} → phone{phone_no}，共 {len(game_list)} 个游戏")
    print(f"{'#'*40}\n")

    # 每台设备一个独立 Agent（device_id 区分底层 adb 操作）
    device_agent = PhoneAgent(
        model_config=model_config,
        agent_config=AgentConfig(lang="cn", verbose=True, max_steps=1000, device_id=device_id),
        memory_manager=memory,
        output_dir=device_output_dir,
    )

    for game in game_list:
        run_one_game(device_agent, game, phone_cfg, device_output_dir)

    print(f"\n✅ 设备 {device_id or '(默认设备)'} 全部游戏跑完\n")
