from __future__ import annotations

import os
import tempfile
import webbrowser
from dataclasses import dataclass
from datetime import date
from html import escape
import tkinter as tk
from tkinter import messagebox, ttk

from qrcodegen import QrCodeError, make_qr

CM_TO_PX = 37.7952755906
LABEL_WIDTH_CM = 6
LABEL_HEIGHT_CM = 4
QR_SIZE_CM = 1
CANVAS_SCALE = 4
LABEL_WIDTH_PX = int(LABEL_WIDTH_CM * CM_TO_PX * CANVAS_SCALE / 3)
LABEL_HEIGHT_PX = int(LABEL_HEIGHT_CM * CM_TO_PX * CANVAS_SCALE / 3)
QR_SIZE_PX = int(QR_SIZE_CM * CM_TO_PX * CANVAS_SCALE / 3)

FIELDS = [
    ("asset_code", "资产编码", True),
    ("asset_name", "资产名称", True),
    ("spec_model", "规格型号", False),
    ("start_date", "开始时间", False),
    ("department", "使用部门", False),
    ("location", "存放地点", False),
    ("keeper", "保管人", False),
]


@dataclass
class AssetData:
    asset_code: str = ""
    asset_name: str = ""
    spec_model: str = ""
    start_date: str = ""
    department: str = ""
    location: str = ""
    keeper: str = ""

    def display_rows(self) -> list[tuple[str, str]]:
        return [
            ("资产编码", self.asset_code or "-"),
            ("资产名称", self.asset_name or "-"),
            ("规格型号", self.spec_model or "-"),
            ("开始时间", self.start_date or "-"),
            ("使用部门", self.department or "-"),
            ("存放地点", self.location or "-"),
            ("保管人", self.keeper or "-"),
        ]


class LabelPrinterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("固定资产标签打印工具（离线桌面版）")
        self.root.geometry("1080x640")
        self.root.minsize(980, 620)

        self.vars = {name: tk.StringVar() for name, _, _ in FIELDS}
        self.status_var = tk.StringVar(value="请填写资产信息。")
        self.canvas: tk.Canvas | None = None

        self._build_ui()
        self._set_default_values()
        self.refresh_preview()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        form_frame = ttk.LabelFrame(container, text="资产信息", padding=16)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form_frame.columnconfigure(1, weight=1)

        for row, (name, label, required) in enumerate(FIELDS):
            text = f"{label} {'*' if required else ''}"
            ttk.Label(form_frame, text=text).grid(row=row, column=0, sticky="w", pady=6)
            entry = ttk.Entry(form_frame, textvariable=self.vars[name], width=32)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            entry.bind("<KeyRelease>", lambda _event: self.refresh_preview())

        btn_frame = ttk.Frame(form_frame, padding=(0, 12, 0, 0))
        btn_frame.grid(row=len(FIELDS), column=0, columnspan=2, sticky="ew")
        btn_frame.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(btn_frame, text="刷新预览", command=self.refresh_preview).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(btn_frame, text="打印标签", command=self.print_label).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(btn_frame, text="清空", command=self.clear_form).grid(row=0, column=2, padx=4, sticky="ew")

        tips = (
            "说明：\n"
            "1. 本程序完全离线运行，二维码本地生成。\n"
            "2. 点击打印后会生成临时 HTML，并调用本机浏览器的打印对话框，\n"
            "   这样你可以在 Windows 7 中自行选择 Gprinter GP-1224T。\n"
            "3. 请在打印机驱动内选择 60mm × 40mm 标签纸。"
        )
        ttk.Label(form_frame, text=tips, justify="left").grid(
            row=len(FIELDS) + 1, column=0, columnspan=2, sticky="w", pady=(16, 0)
        )

        preview_frame = ttk.LabelFrame(container, text="标签预览（6cm × 4cm）", padding=16)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

        preview_wrap = ttk.Frame(preview_frame)
        preview_wrap.grid(row=0, column=0, sticky="nsew")
        preview_wrap.rowconfigure(0, weight=1)
        preview_wrap.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            preview_wrap,
            width=LABEL_WIDTH_PX,
            height=LABEL_HEIGHT_PX,
            background="#ffffff",
            highlightthickness=1,
            highlightbackground="#444444",
        )
        self.canvas.grid(row=0, column=0)

        status_bar = ttk.Label(self.root, textvariable=self.status_var, anchor="w", padding=(16, 6))
        status_bar.pack(fill="x")

    def _set_default_values(self) -> None:
        self.vars["start_date"].set(date.today().isoformat())

    def collect_data(self) -> AssetData:
        return AssetData(**{name: value.get().strip() for name, value in self.vars.items()})

    def validate_required(self, data: AssetData) -> bool:
        if not data.asset_code:
            messagebox.showwarning("缺少必填项", "请填写资产编码。")
            return False
        if not data.asset_name:
            messagebox.showwarning("缺少必填项", "请填写资产名称。")
            return False
        return True

    def refresh_preview(self) -> None:
        data = self.collect_data()
        try:
            qr = make_qr(data.asset_code or "PREVIEW")
        except QrCodeError:
            qr = make_qr("PREVIEW")

        self._draw_label(data, qr)
        self.status_var.set("预览已更新，可直接打印。")

    def clear_form(self) -> None:
        for var in self.vars.values():
            var.set("")
        self.refresh_preview()
        self.status_var.set("表单已清空。")

    def _draw_label(self, data: AssetData, qr) -> None:
        assert self.canvas is not None
        canvas = self.canvas
        canvas.delete("all")
        canvas.create_rectangle(1, 1, LABEL_WIDTH_PX - 1, LABEL_HEIGHT_PX - 1, outline="#111111", width=1)

        left_margin = 10
        top_margin = 10
        row_height = 16
        text_area_width = LABEL_WIDTH_PX - QR_SIZE_PX - 34

        for idx, (key, value) in enumerate(data.display_rows()):
            y = top_margin + idx * row_height
            canvas.create_text(left_margin, y, anchor="nw", text=f"{key}", font=("Microsoft YaHei", 9, "bold"))
            canvas.create_text(
                left_margin + 52,
                y,
                anchor="nw",
                text=f"{value}",
                font=("Microsoft YaHei", 9),
                width=text_area_width - 52,
            )

        qr_left = LABEL_WIDTH_PX - QR_SIZE_PX - 10
        qr_top = LABEL_HEIGHT_PX - QR_SIZE_PX - 10
        self._draw_qr(canvas, qr, qr_left, qr_top, QR_SIZE_PX)

    def _draw_qr(self, canvas: tk.Canvas, qr, left: int, top: int, size: int) -> None:
        canvas.create_rectangle(left, top, left + size, top + size, outline="#222222", width=1)
        quiet = 2
        cells = qr.size + quiet * 2
        scale = size / float(cells)
        for y in range(qr.size):
            for x in range(qr.size):
                if qr.get_module(x, y):
                    x0 = left + (x + quiet) * scale
                    y0 = top + (y + quiet) * scale
                    x1 = left + (x + quiet + 1) * scale
                    y1 = top + (y + quiet + 1) * scale
                    canvas.create_rectangle(x0, y0, x1, y1, outline="", fill="#000000")

    def print_label(self) -> None:
        data = self.collect_data()
        if not self.validate_required(data):
            return

        try:
            qr = make_qr(data.asset_code)
        except QrCodeError as exc:
            messagebox.showerror("二维码生成失败", str(exc))
            return

        html = self._build_print_html(data, qr)
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "asset_label_print.html")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(html)

        webbrowser.open(f"file:///{file_path.replace(os.sep, '/')}")
        self.status_var.set(f"已打开打印页：{file_path}")
        messagebox.showinfo(
            "打印说明",
            "已打开离线打印页。\n请在弹出的浏览器打印窗口中选择你的 Gprinter GP-1224T 或其他打印机。",
        )

    def _build_print_html(self, data: AssetData, qr) -> str:
        rows_html = "\n".join(
            f'<div class="row"><span class="key">{escape(key)}</span><span class="value">{escape(value)}</span></div>'
            for key, value in data.display_rows()
        )
        qr_svg = self._qr_to_svg(qr)
        return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<title>资产标签打印</title>
<style>
  @page {{ size: 6cm 4cm; margin: 0; }}
  html, body {{ margin: 0; padding: 0; background: #fff; }}
  body {{ font-family: Microsoft YaHei, SimSun, Arial, sans-serif; }}
  .label {{
    width: 6cm;
    height: 4cm;
    border: 1px solid #111;
    box-sizing: border-box;
    padding: 0.22cm 0.2cm 0.18cm 0.2cm;
    position: relative;
    overflow: hidden;
  }}
  .content {{ padding-right: 1.1cm; }}
  .row {{ font-size: 8.5pt; line-height: 1.2; margin-bottom: 0.06cm; white-space: nowrap; overflow: hidden; }}
  .key {{ display: inline-block; width: 1.15cm; font-weight: bold; vertical-align: top; }}
  .value {{ display: inline-block; width: 3.7cm; word-break: break-all; white-space: normal; vertical-align: top; }}
  .qr {{ position: absolute; right: 0.2cm; bottom: 0.18cm; width: 1cm; height: 1cm; border: 1px solid #333; }}
  .qr svg {{ width: 100%; height: 100%; display: block; }}
</style>
</head>
<body onload=\"window.print()\">
  <div class=\"label\">
    <div class=\"content\">{rows_html}</div>
    <div class=\"qr\">{qr_svg}</div>
  </div>
</body>
</html>"""

    def _qr_to_svg(self, qr) -> str:
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {qr.size + 4} {qr.size + 4}" shape-rendering="crispEdges">']
        parts.append('<rect width="100%" height="100%" fill="#fff"/>')
        for y in range(qr.size):
            for x in range(qr.size):
                if qr.get_module(x, y):
                    parts.append(f'<rect x="{x + 2}" y="{y + 2}" width="1" height="1" fill="#000"/>')
        parts.append('</svg>')
        return "".join(parts)


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    LabelPrinterApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
