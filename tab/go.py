import datetime
import importlib
import os
import time
import gradio as gr
from gradio import SelectData
from loguru import logger
import requests

from geetest.Validator import Validator
from task.buy import buy_new_terminal
from util import ConfigDB, Endpoint, GlobalStatusInstance, time_service
from util import bili_ticket_gt_python


def withTimeString(string):
    return f"{datetime.datetime.now()}: {string}"


ways: list[str] = []
ways_detail: list[Validator] = []
if bili_ticket_gt_python is not None:
    ways_detail.insert(
        0, importlib.import_module("geetest.TripleValidator").TripleValidator()
    )
    ways.insert(0, "本地过码v2(Amorter)")
    # ways_detail.insert(0, importlib.import_module("geetest.AmorterValidator").AmorterValidator())
    # ways.insert(0, "本地过验证码(Amorter提供)")


def go_tab(demo: gr.Blocks):
    with gr.Column():
        with gr.Row():
            upload_ui = gr.Files(
                label="多个配置文件点击可快速切换",
                file_count="multiple",
            )
            ticket_ui = gr.TextArea(label="查看", info="配置信息", interactive=False)
        with gr.Row(variant="compact"):
            gr.HTML(
                """
                    <input 
                        type="datetime-local" 
                        id="datetime" 
                        name="datetime" 
                        step="1" 
                        class="border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                </div>
                """,
                label="选择抢票的时间",
                show_label=True,
            )

        def upload(filepath):
            try:
                with open(filepath[0], "r", encoding="utf-8") as file:
                    content = file.read()
                return content
            except Exception as e:
                return str(e)

        def file_select_handler(select_data: SelectData, files):
            file_label = files[select_data.index]
            try:
                with open(file_label, "r", encoding="utf-8") as file:
                    content = file.read()
                return content
            except Exception as e:
                return str(e)

        upload_ui.upload(fn=upload, inputs=upload_ui, outputs=ticket_ui)
        upload_ui.select(file_select_handler, upload_ui, ticket_ui)

        # 手动设置/更新时间偏差
        with gr.Accordion(label="手动设置/更新时间偏差", open=True):
            time_diff_ui = gr.Number(
                label="当前脚本时间偏差 (单位: ms)",
                value=float(format(time_service.get_timeoffset() * 1000, ".2f")),
            )  # type: ignore
            refresh_time_ui = gr.Button(value="点击自动更新时间偏差")
            refresh_time_ui.click(
                fn=lambda: format(
                    float(time_service.compute_timeoffset()) * 1000, ".2f"
                ),
                inputs=None,
                outputs=time_diff_ui,
            )
            time_diff_ui.change(
                fn=lambda x: time_service.set_timeoffset(
                    format(float(x) / 1000, ".5f")
                ),
                inputs=time_diff_ui,
                outputs=None,
            )

        # 验证码选择
        select_way = 0
        way_select_ui = gr.Radio(
            ways,
            label="过码方式",
            type="index",
            value=ways[select_way],
        )
        with gr.Accordion(label="代理服务器", open=False):
            gr.Markdown("""
                        > **注意**：

                        填写代理服务器地址后，程序在使用这个配置文件后会在出现风控后后根据代理服务器去访问哔哩哔哩的抢票接口。

                        抢票前请确保代理服务器已经开启，并且可以正常访问哔哩哔哩的抢票接口。

                        """)

            def get_latest_proxy():
                return ConfigDB.get("https_proxy") or ""

            https_proxy_ui = gr.Textbox(
                label="填写抢票时候的代理服务器地址，使用逗号隔开|输入Enter保存",
                info="例如： http://127.0.0.1:8080,http://127.0.0.1:8081,http://127.0.0.1:8082",
                value=get_latest_proxy,
            )

            def input_https_proxy(_https_proxy):
                ConfigDB.update("https_proxy", _https_proxy)
                return gr.update(ConfigDB.get("https_proxy"))

            https_proxy_ui.submit(
                fn=input_https_proxy, inputs=https_proxy_ui, outputs=https_proxy_ui
            )
        with gr.Accordion(label="配置抢票声音提醒", open=False):
            with gr.Row():
                audio_path_ui = gr.Audio(
                    label="上传提示声音[只支持格式wav]", type="filepath", loop=True
                )
        with gr.Accordion(label="配置抢票消息提醒", open=False):
            with gr.Row():
                serverchan_ui = gr.Textbox(
                    value=ConfigDB.get("serverchanKey")
                    if ConfigDB.get("serverchanKey") is not None
                    else "",
                    label="Server酱的SendKey",
                    interactive=True,
                    info="https://sct.ftqq.com/",
                )

                pushplus_ui = gr.Textbox(
                    value=ConfigDB.get("pushplusToken")
                    if ConfigDB.get("pushplusToken") is not None
                    else "",
                    label="PushPlus的Token",
                    interactive=True,
                    info="https://www.pushplus.plus/",
                )

                def inner_input_serverchan(x):
                    return ConfigDB.insert("serverchanKey", x)

                def inner_input_pushplus(x):
                    return ConfigDB.insert("pushplusToken", x)

                serverchan_ui.change(fn=inner_input_serverchan, inputs=serverchan_ui)

                pushplus_ui.change(fn=inner_input_pushplus, inputs=pushplus_ui)

        def choose_option(way):
            nonlocal select_way
            select_way = way

        way_select_ui.change(choose_option, inputs=way_select_ui)

        with gr.Row():
            interval_ui = gr.Number(
                label="抢票间隔",
                value=300,
                minimum=1,
            )
            mode_ui = gr.Radio(
                label="抢票次数",
                choices=["无限", "有限"],
                value="无限",
                type="index",
                interactive=True,
            )
            total_attempts_ui = gr.Number(
                label="总过次数",
                value=100,
                minimum=1,
                visible=False,
            )

        push_to_musestar_ui = gr.Checkbox(label="是否推送到缪斯星服务器", value=False)

    def try_assign_endpoint(endpoint_url, payload):
        try:
            response = requests.post(f"{endpoint_url}/buy", json=payload, timeout=5)
            if response.status_code == 200:
                return True
            elif response.status_code == 409:
                logger.info(f"{endpoint_url} 已经占用")
                return False
            else:
                return False

        except Exception as e:
            logger.exception(e)
            raise e

    def split_proxies(https_proxy_list: list[str], task_num: int) -> list[list[str]]:
        assigned_proxies: list[list[str]] = [[] for _ in range(task_num)]
        for i, proxy in enumerate(https_proxy_list):
            assigned_proxies[i % task_num].append(proxy)
        return assigned_proxies

    def start_go(
        files, time_start, interval, mode, total_attempts, audio_path, https_proxys, push_to_musestar
    ):
        if not files:
            return [gr.update(value=withTimeString("未提交抢票配置"), visible=True)]
        yield [
            gr.update(value=withTimeString("开始多开抢票,详细查看终端"), visible=True)
        ]
        endpoints = GlobalStatusInstance.available_endpoints()
        endpoints_next_idx = 0
        https_proxy_list = ["none"] + https_proxys.split(",")
        assigned_proxies: list[list[str]] = []
        assigned_proxies_next_idx = 0
        for idx, filename in enumerate(files):
            with open(filename, "r", encoding="utf-8") as file:
                content = file.read()
            filename_only = os.path.basename(filename)
            logger.info(f"启动 {filename_only}")
            # 先分配worker
            while endpoints_next_idx < len(endpoints):
                success = try_assign_endpoint(
                    endpoints[endpoints_next_idx].endpoint,
                    payload={
                        "force": True,
                        "train_info": content,
                        "time_start": time_start,
                        "interval": interval,
                        "mode": mode,
                        "total_attempts": total_attempts,
                        "audio_path": audio_path,
                        "pushplusToken": ConfigDB.get("pushplusToken"),
                        "serverchanKey": ConfigDB.get("serverchanKey"),
                    },
                )
                endpoints_next_idx += 1
                if success:
                    break
            else:
                # 再分配https_proxys
                if assigned_proxies == []:
                    left_task_num = len(files) - idx
                    assigned_proxies = split_proxies(https_proxy_list, left_task_num)

                buy_new_terminal(
                    endpoint_url=demo.local_url,
                    filename=filename,
                    tickets_info_str=content,
                    time_start=time_start,
                    interval=interval,
                    mode=mode,
                    total_attempts=total_attempts,
                    audio_path=audio_path,
                    pushplusToken=ConfigDB.get("pushplusToken"),
                    serverchanKey=ConfigDB.get("serverchanKey"),
                    https_proxys=",".join(assigned_proxies[assigned_proxies_next_idx]),
                    push_to_musestar=push_to_musestar,
                )
                assigned_proxies_next_idx += 1
        gr.Info("正在启动，请等待抢票页面弹出。")

    def start_process(
        files,
        time_start,
        interval,
        mode,
        total_attempts,
        audio_path,
        https_proxys,
        progress=gr.Progress(),
    ):
        """
        不同start_go，start_process会采取队列的方式抢票，首先他会当前抢票的配置文件，依此进行抢票。

        抢票并发量为： worker数目+ (1+代理数目)/2 向上取整


        """
        if not files:
            return [gr.update(value=withTimeString("未提交抢票配置"), visible=True)]
        yield [
            gr.update(value=withTimeString("开始多开抢票,详细查看终端"), visible=True)
        ]
        endpoints = GlobalStatusInstance.available_endpoints()
        endpoints_next_idx = 0
        https_proxy_list = ["none"] + https_proxys.split(",")
        assigned_proxies: list[list[str]] = []
        assigned_proxies_next_idx = 0
        for idx, filename in enumerate(files):
            with open(filename, "r", encoding="utf-8") as file:
                content = file.read()
            filename_only = os.path.basename(filename)
            logger.info(f"启动 {filename_only}")
            # 先分配worker
            while endpoints_next_idx < len(endpoints):
                success = try_assign_endpoint(
                    endpoints[endpoints_next_idx].endpoint,
                    payload={
                        "force": True,
                        "train_info": content,
                        "time_start": time_start,
                        "interval": interval,
                        "mode": mode,
                        "total_attempts": total_attempts,
                        "audio_path": audio_path,
                        "pushplusToken": ConfigDB.get("pushplusToken"),
                        "serverchanKey": ConfigDB.get("serverchanKey"),
                    },
                )
                endpoints_next_idx += 1
                if success:
                    break
            else:
                # 再分配https_proxys
                if assigned_proxies == []:
                    left_task_num = len(files) - idx
                    assigned_proxies = split_proxies(https_proxy_list, left_task_num)

                buy_new_terminal(
                    endpoint_url=demo.local_url,
                    filename=filename,
                    tickets_info_str=content,
                    time_start=time_start,
                    interval=interval,
                    mode=mode,
                    total_attempts=total_attempts,
                    audio_path=audio_path,
                    pushplusToken=ConfigDB.get("pushplusToken"),
                    serverchanKey=ConfigDB.get("serverchanKey"),
                    https_proxys=",".join(assigned_proxies[assigned_proxies_next_idx]),
                    push_to_musestar=push_to_musestar,
                )
                assigned_proxies_next_idx += 1
        gr.Info("正在启动，请等待抢票页面弹出。")

    mode_ui.change(
        fn=lambda x: gr.update(visible=True) if x == 1 else gr.update(visible=False),
        inputs=[mode_ui],
        outputs=total_attempts_ui,
    )

    go_btn = gr.Button("开始抢票")
    process_btn = gr.Button("开始蹲票", visible=False)

    _time_tmp = gr.Textbox(visible=False)
    go_btn.click(
        fn=None,
        inputs=None,
        outputs=_time_tmp,
        js='(x) => document.getElementById("datetime").value',
    )
    _report_tmp = gr.Button(visible=False)
    _report_tmp.api_info

    # hander endpoint hearts

    _end_point_tinput = gr.Textbox(visible=False)

    def report(end_point, detail):
        now = time.time()
        GlobalStatusInstance.endpoint_details[end_point] = Endpoint(
            endpoint=end_point, detail=detail, update_at=now
        )

    _report_tmp.click(
        fn=report,
        inputs=[_end_point_tinput, _time_tmp],  # fake useage
        api_name="report",
    )

    def tick():
        return f"当前时间戳：{int(time.time())}"

    timer = gr.Textbox(label="定时更新", interactive=False, visible=False)
    demo.load(fn=tick, inputs=None, outputs=timer, every=1)

    @gr.render(inputs=timer)
    def show_split(text):
        endpoints = GlobalStatusInstance.available_endpoints()
        if len(endpoints) == 0:
            gr.Markdown("## 无运行终端")
        else:
            gr.Markdown("## 当前运行终端列表")
            for endpoint in endpoints:
                with gr.Row():
                    gr.Button(
                        value=f"点击跳转 🚀 {endpoint.endpoint} {endpoint.detail}",
                        link=endpoint.endpoint,
                    )

    go_btn.click(
        fn=start_go,
        inputs=[
            upload_ui,
            _time_tmp,
            interval_ui,
            mode_ui,
            total_attempts_ui,
            audio_path_ui,
            https_proxy_ui,
            push_to_musestar_ui,
        ],
    )
    process_btn.click(
        fn=start_process,
        inputs=[
            upload_ui,
            _time_tmp,
            interval_ui,
            mode_ui,
            total_attempts_ui,
            audio_path_ui,
            https_proxy_ui,
            push_to_musestar_ui,
        ],
        outputs=process_btn,
    )
