from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.model import ModelConfig
from phone_agent.config import get_messages
from phone_agent.memory import MemoryManager
from phone_agent.results import activity_notes_to_game_events
from commonproto.pb4.proto.grpc import k2av_pb2
from commonproto.pb4.proto.ad.ad_pb2 import GameEvent
from utils.k2av_util import create_k2av_stub, send_k2av

import base64
import json
import os

# Gemini
model_config = ModelConfig(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_name="gemini-3.5-flash",
    api_key=os.environ.get("GEMINI_API_KEY", ""),
    extra_body={
        "reasoning_effort": "low",   # 关闭思考；也可 "low" / "medium" / "high"
    },
)


# --- Memory: enable knowledge base learning ---
memory = MemoryManager()

agent = PhoneAgent(
    model_config=model_config,
    agent_config=AgentConfig(lang="cn", verbose=True, max_steps=1000),
    memory_manager=memory,
)

APP_LIST = ["和平精英", "王者荣耀", "蛋仔派对", "小小蚁国", "破晓的曙光", "完美世界", "三角洲行动"]
APP_LIST = ["蛋仔派对"]

TASK_HEPING = """
第一步：在屏幕中找到《%s》游戏图标并点击启动，等待游戏加载完成并进入主屏幕。加载过程中如有任何弹窗、提示框、权限请求或通知出现，自行寻找关闭、跳过、同意或确认按钮将其关闭，不需要请求用户协助，直到完全进入游戏主屏幕为止。如果遇到登录，优先选“QQ登录”

第二步：在屏幕中寻找与"活动"相关的入口，点击进入活动中心页面。

第三步：进入活动中心后，找到所有一级标签页，逐一点击每个一级标签，收集该标签下的所有内容，包括限时活动、定时开启的固定玩法、副本任务等，不做过滤，全部记录。所有一级标签都必须依次检查，不能跳过。

第四步：在每个含有活动内容的一级标签下，逐个查看所有活动。每进入一个活动的详情页并加载完成后，立即输出一条 Note 记录该活动，格式严格如下：

【一级标签名称 - 活动名称】
活动起始时间：xxx
活动结束时间：xxx
规则：xxx
奖励：xxx

注意：
- 每看到一个活动就立刻输出一条独立的 Note，不要把多个活动塞进同一条 Note，也不要等全部看完再统一汇总。
- 活动起始时间、活动结束时间都要从该活动详情页的实际内容中读取，只写日期（写到日），写不出的填"无"。不要把日期和钟点写成一个范围字符串，分开填到两个字段。例如详情页写"07.10 00:00-07.30 23:59"时，活动起始时间填"07.10 00:00"，活动结束时间填"07.30 23:59"。
- Note 里的活动名称、规则、奖励都要从该活动详情页的实际内容中读取，未写明的字段填"无"。
- 同一个活动不要重复输出 Note。
- 输出 Note 后继续查看下一个活动；列表要从顶部持续向下滚动直到底部，确保所有活动都被加载并记录，不能遗漏。每次滚动后需等待内容加载完成再继续。

第五步：所有一级标签下的活动都逐条 Note 完毕后，结束游戏回到手机桌面，再执行 finish。不要在最后再输出一条汇总 Note。
""".strip()


# task = TASK_WANGZHE
msgs = get_messages("cn")
output_dir = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(output_dir, exist_ok=True)

# --- Create k2av stub once ---
k2av_stub = create_k2av_stub(server="k2av-ag-alishh.umlife.net:31400", channel_options=[("grpc.default_authority", "k2av.ag.k8s.y.cn")])

for game in APP_LIST:
    task = TASK_HEPING % game
    print(f"\n{'='*40}")
    print(f"开始处理: {game}")
    print(f"{'='*40}\n")

    # --- 清空该游戏目录下旧的截图，避免与新截图混在一起 ---
    game_shot_dir = os.path.join(output_dir, game, "screenshots")
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

        # Save to output/<game>_activities.json
        output_path = os.path.join(output_dir, f"{game}_activities.json")
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
