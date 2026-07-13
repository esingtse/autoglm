from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.model import ModelConfig
from phone_agent.config import get_messages
from phone_agent.memory import MemoryManager
from phone_agent.results import activity_summary_to_game_events
from commonproto.pb4.proto.grpc import k2av_pb2
from commonproto.pb4.proto.ad.ad_pb2 import GameEvent
from utils.k2av_util import create_k2av_stub, send_k2av

import json
import os

# Gemini
model_config = ModelConfig(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_name="gemini-3.5-flash",
    api_key='',
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
APP_LIST = ["王者荣耀"]

TASK_HEPING = """
第一步：在屏幕中找到《%s》游戏图标并点击启动，等待游戏加载完成并进入主屏幕。加载过程中如有任何弹窗、提示框、权限请求或通知出现，自行寻找关闭、跳过、同意或确认按钮将其关闭，不需要请求用户协助，直到完全进入游戏主屏幕为止。如果遇到登录，优先选“QQ登录”

第二步：在屏幕中寻找与"活动"相关的入口，点击进入活动中心页面。

第三步：进入活动中心后，找到所有一级标签页，逐一点击每个一级标签，判断该标签下是否包含活动内容。如果包含则收集，不包含则跳过，继续下一个。所有一级标签都必须依次检查，不能跳过。

第四步：在每个含有活动内容的一级标签下，逐个查看所有活动，获取每个活动的所属一级标签名称、活动名称、活动时间、参与规则和奖励内容。列表需要从顶部开始，持续向下滚动直到底部，确保所有活动都被加载并收集，不能遗漏。每次滚动后需等待内容加载完成再继续。

第五步：所有一级标签都检查完毕后，输出一条 Note，包含从所有标签下收集到的完整活动信息，格式如下：

=== 活动汇总 ===

【所属一级标签 - 活动名称】
活动时间：xxx
规则：xxx
奖励：xxx

（每个活动之间空一行）

输出完这条汇总 Note 之后
最后结束游戏，回到手机桌面，再执行 finish。。
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
    result = agent.run(task)
    print(f"\n--- {game} 结果 ---")
    print(f"{msgs['result']}: {result}")

    # --- Parse Note output and save as proto-compatible JSON ---
    notes = agent.collected_notes
    if notes:
        all_events = []
        for note_text in notes:
            events = activity_summary_to_game_events(
                text=note_text,
                app_name=game,
            )
            if events:
                all_events.extend(events)
                print(f"\n📋 解析到 {len(events)} 条 GameEvent:")
                print(json.dumps(events[:3], ensure_ascii=False, indent=2))
                if len(events) > 3:
                    print(f"... 及其他 {len(events) - 3} 条")
            else:
                print(f"\n⚠️ 无法解析 Note，保留原始文本")

        # Save to output/<game>_activities.json
        output_path = os.path.join(output_dir, f"{game}_activities.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_events, f, ensure_ascii=False, indent=2)
        print(f"\n💾 已保存 {len(all_events)} 条 GameEvent → {output_path}")

        # --- Send to k2av ---
        for event in all_events:
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
            )
            request = k2av_pb2.Request(topic="game_event", value=ge.SerializeToString())
            send_k2av(k2av_stub, request)
        print(f"📤 已发送 {len(all_events)} 条 GameEvent → k2av")

    # Reset Agent state
    agent.reset()
    print(f"\n{'='*40}")
    print(f"完成: {game}")
    print(f"{'='*40}\n")
