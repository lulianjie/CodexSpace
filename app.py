from __future__ import annotations

import os
import tempfile
import webbrowser
from dataclasses import dataclass
from datetime import date
from html import escape
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

from qrcodegen import QrCodeError, make_qr

CM_TO_PX = 37.7952755906
LABEL_WIDTH_CM = 6
LABEL_HEIGHT_CM = 4
QR_SIZE_CM = 1
CANVAS_SCALE = 4
LABEL_WIDTH_PX = int(LABEL_WIDTH_CM * CM_TO_PX * CANVAS_SCALE / 3)
LABEL_HEIGHT_PX = int(LABEL_HEIGHT_CM * CM_TO_PX * CANVAS_SCALE / 3)
QR_SIZE_PX = int(QR_SIZE_CM * CM_TO_PX * CANVAS_SCALE / 3)
FONT_FAMILY = "SimHei"
KEY_FONT_SIZE = 9
VALUE_FONT_SIZE = 9
HTML_FONT_SIZE_PT = 9
TITLE_FONT_SIZE = 11

FIELDS = [
    ("asset_code", "资产编码", True),
    ("asset_name", "资产名称", True),
    ("spec_model", "规格型号", False),
    ("start_date", "开始时间", False),
    ("department", "使用部门", False),
    ("location", "存放地点", False),
    ("keeper", "保管人", False),
]
FIELD_LABELS = {name: label for name, label, _ in FIELDS}
FIELD_ORDER = [name for name, _, _ in FIELDS]
XML_NS = {
    "ss": "urn:schemas-microsoft-com:office:spreadsheet",
    "o": "urn:schemas-microsoft-com:office:office",
    "x": "urn:schemas-microsoft-com:office:excel",
}


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

    @classmethod
    def from_mapping(cls, mapping: dict[str, str]) -> "AssetData":
        return cls(**{name: (mapping.get(name, "") or "").strip() for name in FIELD_ORDER})

    def to_mapping(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in FIELD_ORDER}


class ExcelTemplateService:
    @staticmethod
    def build_template_xml() -> str:
        headers = [FIELD_LABELS[name] for name in FIELD_ORDER]
        sample = [
            "FA-2026-001",
            "办公电脑",
            "ThinkPad E14",
            date.today().isoformat(),
            "信息部",
            "三楼办公室",
            "张三",
        ]
        rows = [headers, sample]
        row_xml = []
        for row in rows:
            cells = "".join(
                f'<Cell><Data ss:Type="String">{escape(value)}</Data></Cell>' for value in row
            )
            row_xml.append(f"<Row>{cells}</Row>")
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="资产标签模板">
  <Table>
   {''.join(row_xml)}
  </Table>
 </Worksheet>
</Workbook>
'''

    @staticmethod
    def save_template(file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(ExcelTemplateService.build_template_xml())

    @staticmethod
    def import_records(file_path: str) -> list[AssetData]:
        suffix = os.path.splitext(file_path)[1].lower()
        if suffix == ".csv":
            return ExcelTemplateService._import_csv(file_path)
        return ExcelTemplateService._import_excel_xml(file_path)

    @staticmethod
    def _import_excel_xml(file_path: str) -> list[AssetData]:
        tree = ET.parse(file_path)
        rows = tree.findall(".//ss:Worksheet/ss:Table/ss:Row", XML_NS)
        if not rows:
            raise ValueError("未找到可导入的数据行。")

        table = [ExcelTemplateService._extract_row(row) for row in rows]
        headers = [cell.strip() for cell in table[0]]
        if headers != [FIELD_LABELS[name] for name in FIELD_ORDER]:
            raise ValueError("Excel 模板表头不匹配，请先下载系统模板再填写。")

        records: list[AssetData] = []
        for values in table[1:]:
            if not any(cell.strip() for cell in values):
                continue
            padded = values + [""] * (len(FIELD_ORDER) - len(values))
            mapping = {name: padded[index].strip() for index, name in enumerate(FIELD_ORDER)}
            record = AssetData.from_mapping(mapping)
            ExcelTemplateService._validate_record(record)
            records.append(record)

        if not records:
            raise ValueError("导入文件中没有有效数据。")
        return records

    @staticmethod
    def _extract_row(row: ET.Element) -> list[str]:
        values: list[str] = []
        current_index = 1
        for cell in row.findall("ss:Cell", XML_NS):
            index_attr = cell.attrib.get(f'{{{XML_NS["ss"]}}}Index')
            if index_attr:
                target_index = int(index_attr)
                while current_index < target_index:
                    values.append("")
                    current_index += 1
            data = cell.find("ss:Data", XML_NS)
            values.append(data.text or "" if data is not None else "")
            current_index += 1
        return values

    @staticmethod
    def _import_csv(file_path: str) -> list[AssetData]:
        import csv

        with open(file_path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = list(csv.reader(handle))
        if not reader:
            raise ValueError("CSV 文件为空。")
        headers = [cell.strip() for cell in reader[0]]
        if headers != [FIELD_LABELS[name] for name in FIELD_ORDER]:
            raise ValueError("CSV 表头不匹配，请使用导出的模板标题。")
        records: list[AssetData] = []
        for values in reader[1:]:
            if not any(cell.strip() for cell in values):
                continue
            padded = values + [""] * (len(FIELD_ORDER) - len(values))
            record = AssetData.from_mapping({name: padded[i] for i, name in enumerate(FIELD_ORDER)})
            ExcelTemplateService._validate_record(record)
            records.append(record)
        if not records:
            raise ValueError("CSV 文件中没有有效数据。")
        return records

    @staticmethod
    def _validate_record(record: AssetData) -> None:
        if not record.asset_code:
            raise ValueError("导入数据存在空的资产编码。")
        if not record.asset_name:
            raise ValueError(f"资产编码 {record.asset_code or '(空)'} 缺少资产名称。")


class LabelPrinterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("固定资产标签打印工具（离线桌面版）")
        self.root.geometry("1180x700")
        self.root.minsize(1080, 660)

        self.vars = {name: tk.StringVar() for name, _, _ in FIELDS}
        self.status_var = tk.StringVar(value="请填写资产信息。")
        self.batch_records: list[AssetData] = []
        self.batch_index = 0
        self.batch_info_var = tk.StringVar(value="当前未导入批量数据。")
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
            entry = ttk.Entry(form_frame, textvariable=self.vars[name], width=34)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            entry.bind("<KeyRelease>", lambda _event: self._manual_edit_refresh())

        btn_row = len(FIELDS)
        actions = ttk.Frame(form_frame, padding=(0, 12, 0, 0))
        actions.grid(row=btn_row, column=0, columnspan=2, sticky="ew")
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        ttk.Button(actions, text="刷新预览", command=self.refresh_preview).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(actions, text="打印当前", command=self.print_current_label).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(actions, text="清空", command=self.clear_form).grid(row=0, column=2, padx=4, sticky="ew")

        batch_actions = ttk.Frame(form_frame, padding=(0, 10, 0, 0))
        batch_actions.grid(row=btn_row + 1, column=0, columnspan=2, sticky="ew")
        for column in range(3):
            batch_actions.columnconfigure(column, weight=1)
        ttk.Button(batch_actions, text="下载Excel模板", command=self.download_excel_template).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(batch_actions, text="导入Excel批量", command=self.import_excel_batch).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(batch_actions, text="打印导入批量", command=self.print_batch_labels).grid(row=0, column=2, padx=4, sticky="ew")

        nav_actions = ttk.Frame(form_frame, padding=(0, 10, 0, 0))
        nav_actions.grid(row=btn_row + 2, column=0, columnspan=2, sticky="ew")
        nav_actions.columnconfigure(1, weight=1)
        ttk.Button(nav_actions, text="上一条", command=lambda: self.show_batch_record(-1)).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Label(nav_actions, textvariable=self.batch_info_var, anchor="center").grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(nav_actions, text="下一条", command=lambda: self.show_batch_record(1)).grid(row=0, column=2, padx=4, sticky="ew")

        tips = (
            f"说明：\n"
            f"1. 本程序完全离线运行，二维码本地生成。\n"
            f"2. 当前字体固定为黑体（{FONT_FAMILY}），标签名和值之间已加入“： ”。\n"
            f"3. 当前标题字号为 {TITLE_FONT_SIZE}pt，正文打印字号为 {HTML_FONT_SIZE_PT}pt；若实际打印偏大/偏小，可调整 app.py 中的\n"
            f"   TITLE_FONT_SIZE / KEY_FONT_SIZE / VALUE_FONT_SIZE / HTML_FONT_SIZE_PT 常量。\n"
            f"4. 当前标签已关闭换行逻辑，字段内容会单行显示。\n"
            f"5. 点击打印后会生成本地 HTML 打印页，并调用浏览器打印对话框，\n"
            f"   这样你可以在 Windows 7 中自行选择 Gprinter GP-1224T。"
        )
        ttk.Label(form_frame, text=tips, justify="left").grid(
            row=btn_row + 3, column=0, columnspan=2, sticky="w", pady=(16, 0)
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

    def _manual_edit_refresh(self) -> None:
        if self.batch_records:
            self.batch_info_var.set("你正在手动修改当前表单，批量记录仍保留，可继续打印导入批量。")
        self.refresh_preview()

    def collect_data(self) -> AssetData:
        return AssetData(**{name: value.get().strip() for name, value in self.vars.items()})

    def load_data_to_form(self, data: AssetData) -> None:
        for name in FIELD_ORDER:
            self.vars[name].set(getattr(data, name))
        self.refresh_preview()

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
        self.batch_records = []
        self.batch_index = 0
        self.batch_info_var.set("当前未导入批量数据。")
        self.refresh_preview()
        self.status_var.set("表单已清空。")

    def download_excel_template(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="保存 Excel 模板",
            defaultextension=".xls",
            filetypes=[("Excel 2003 XML", "*.xls"), ("CSV 文件", "*.csv")],
            initialfile="资产标签导入模板.xls",
        )
        if not file_path:
            return
        try:
            if file_path.lower().endswith(".csv"):
                self._save_csv_template(file_path)
            else:
                ExcelTemplateService.save_template(file_path)
        except OSError as exc:
            messagebox.showerror("模板保存失败", str(exc))
            return
        self.status_var.set(f"模板已保存：{file_path}")
        messagebox.showinfo("模板已保存", f"Excel 模板已保存到：\n{file_path}")

    def _save_csv_template(self, file_path: str) -> None:
        import csv

        with open(file_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([FIELD_LABELS[name] for name in FIELD_ORDER])
            writer.writerow(["FA-2026-001", "办公电脑", "ThinkPad E14", date.today().isoformat(), "信息部", "三楼办公室", "张三"])

    def import_excel_batch(self) -> None:
        file_path = filedialog.askopenfilename(
            title="导入 Excel 批量数据",
            filetypes=[("Excel 2003 XML 或 CSV", "*.xls *.xml *.csv")],
        )
        if not file_path:
            return
        try:
            records = ExcelTemplateService.import_records(file_path)
        except (OSError, ET.ParseError, ValueError) as exc:
            messagebox.showerror("导入失败", str(exc))
            return

        self.batch_records = records
        self.batch_index = 0
        self.load_data_to_form(records[0])
        self._refresh_batch_info(file_path)
        self.status_var.set(f"已导入 {len(records)} 条批量数据。")
        messagebox.showinfo("导入成功", f"已导入 {len(records)} 条记录。\n可点击“打印导入批量”一次性生成全部标签。")

    def _refresh_batch_info(self, source: str | None = None) -> None:
        if not self.batch_records:
            self.batch_info_var.set("当前未导入批量数据。")
            return
        prefix = f"已导入 {len(self.batch_records)} 条"
        if source:
            prefix += f"（{os.path.basename(source)}）"
        self.batch_info_var.set(f"{prefix}，当前查看第 {self.batch_index + 1} 条")

    def show_batch_record(self, offset: int) -> None:
        if not self.batch_records:
            messagebox.showinfo("没有批量数据", "请先导入 Excel 批量数据。")
            return
        self.batch_index = (self.batch_index + offset) % len(self.batch_records)
        self.load_data_to_form(self.batch_records[self.batch_index])
        self._refresh_batch_info()
        self.status_var.set(f"当前查看批量记录第 {self.batch_index + 1} 条。")

    def _draw_label(self, data: AssetData, qr) -> None:
        assert self.canvas is not None
        canvas = self.canvas
        canvas.delete("all")
        canvas.create_rectangle(1, 1, LABEL_WIDTH_PX - 1, LABEL_HEIGHT_PX - 1, outline="#111111", width=1)

        left_margin = 10
        title_y = 8
        row_start_y = 28
        row_height = 14
        text_x = left_margin
        value_x = left_margin + 62

        canvas.create_text(
            LABEL_WIDTH_PX / 2,
            title_y,
            anchor="n",
            text="固定资产",
            font=(FONT_FAMILY, TITLE_FONT_SIZE, "bold"),
        )

        for idx, (key, value) in enumerate(data.display_rows()):
            y = row_start_y + idx * row_height
            canvas.create_text(
                text_x,
                y,
                anchor="nw",
                text=f"{key}： ",
                font=(FONT_FAMILY, KEY_FONT_SIZE, "bold"),
            )
            canvas.create_text(
                value_x,
                y,
                anchor="nw",
                text=value,
                font=(FONT_FAMILY, VALUE_FONT_SIZE),
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

    def print_current_label(self) -> None:
        data = self.collect_data()
        if not self.validate_required(data):
            return
        self._print_records([data], title="当前标签")

    def print_batch_labels(self) -> None:
        if not self.batch_records:
            messagebox.showinfo("没有批量数据", "请先导入 Excel 批量数据。")
            return
        self._print_records(self.batch_records, title=f"批量标签（共 {len(self.batch_records)} 条）")

    def _print_records(self, records: list[AssetData], title: str) -> None:
        html = self._build_print_html(records, title)
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

    def _build_print_html(self, records: list[AssetData], title: str) -> str:
        labels_html = []
        for data in records:
            qr = make_qr(data.asset_code)
            rows_html = "\n".join(
                f'<div class="row"><span class="key">{escape(key)}： </span><span class="value">{escape(value)}</span></div>'
                for key, value in data.display_rows()
            )
            qr_svg = self._qr_to_svg(qr)
            labels_html.append(
                f'<div class="label"><div class="title">固定资产</div><div class="content">{rows_html}</div><div class="qr">{qr_svg}</div></div>'
            )
        joined = "\n".join(labels_html)
        return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<title>{escape(title)}</title>
<style>
  @page {{ size: 6cm 4cm; margin: 0; }}
  html, body {{ margin: 0; padding: 0; background: #fff; }}
  body {{ font-family: {FONT_FAMILY}, SimSun, Arial, sans-serif; }}
  .label {{
    width: 6cm;
    height: 4cm;
    border: 1px solid #111;
    box-sizing: border-box;
    padding: 0.22cm 0.2cm 0.18cm 0.2cm;
    position: relative;
    overflow: hidden;
    page-break-after: always;
  }}
  .label:last-child {{ page-break-after: auto; }}
  .title {{ font-size: {TITLE_FONT_SIZE}pt; font-weight: bold; text-align: center; line-height: 1; margin-bottom: 0.08cm; }}
  .content {{ padding-right: 1.1cm; }}
  .row {{ font-size: {HTML_FONT_SIZE_PT}pt; line-height: 1.05; margin-bottom: 0.03cm; white-space: nowrap; overflow: hidden; }}
  .key {{ display: inline-block; width: 1.35cm; font-weight: bold; vertical-align: top; white-space: nowrap; }}
  .value {{ display: inline-block; width: 3.45cm; white-space: nowrap; overflow: hidden; vertical-align: top; }}
  .qr {{ position: absolute; right: 0.2cm; bottom: 0.18cm; width: 1cm; height: 1cm; border: 1px solid #333; }}
  .qr svg {{ width: 100%; height: 100%; display: block; }}
</style>
</head>
<body onload=\"window.print()\">{joined}</body>
</html>"""

    def _qr_to_svg(self, qr) -> str:
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {qr.size + 4} {qr.size + 4}" shape-rendering="crispEdges">']
        parts.append('<rect width="100%" height="100%" fill="#fff"/>')
        for y in range(qr.size):
            for x in range(qr.size):
                if qr.get_module(x, y):
                    parts.append(f'<rect x="{x + 2}" y="{y + 2}" width="1" height="1" fill="#000"/>')
        parts.append("</svg>")
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
