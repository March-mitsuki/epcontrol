from PIL import Image, ImageDraw, ImageFont
import qrcode
import dataclasses
import sys

from const import PAPER_WIDTH, FONT_SIZES


@dataclasses.dataclass
class PrinterConfig:
    """
    打印机配置类

    :param printer_name: 打印机名称
        - 在 Windows 中是 `win32print.OpenPrinter` 的参数
        - 在 Linux 中是 `/dev/usb/lp0` 或 `/dev/usb/lp1` 等设备文件, 会通过 `open` 打开

    :param paper_width: 纸张宽度, 详见`const.PAPER_WIDTH`

    :param default_font: 默认字体路径

    :param platform: 打印机平台 ("windows" | "linux")
        - default: 自动检测
    """

    printer_name: str
    paper_width: str
    default_font: str
    platform: str | None = None


@dataclasses.dataclass
class Text:
    text: str
    align: str
    font_size: int
    font: str


@dataclasses.dataclass
class BetweenText:
    left: str
    right: str
    left_font_size: int
    right_font_size: int
    left_font: str
    right_font: str


@dataclasses.dataclass
class QrCode:
    data: str
    box_size: int
    border: int


@dataclasses.dataclass
class NewLine:
    height: int
    lines: int


@dataclasses.dataclass
class ImageContent:
    image: Image.Image
    max_width: int | None = None


ContentUnion = Text | BetweenText | QrCode | NewLine | ImageContent


class EscPosPrinter:
    """
    ESC/POS 打印机类

    把所有打印内容渲染为图像，然后通过 ESC/POS 指令发送到打印机
    """

    def __init__(self, config: PrinterConfig):
        # Setup printer config
        self._validate_config(config)
        self.printer_name = config.printer_name
        self.paper_width = PAPER_WIDTH[config.paper_width]
        self.default_font = config.default_font
        if config.platform is None:
            if sys.platform.startswith("win"):
                self.platform = "windows"
            elif sys.platform.startswith("linux"):
                self.platform = "linux"
            else:
                raise ValueError(
                    "Unsupported platform. Only 'windows' and 'linux' are supported."
                )
        else:
            self.platform = config.platform

        self.contents: list[ContentUnion] = []
        # ESC/POS commands
        self.commands = bytearray()

    def _validate_config(self, config: PrinterConfig):
        if config.paper_width not in PAPER_WIDTH:
            raise ValueError("Invalid paper width. Choose '58mm' or '80mm'.")
        if config.platform not in ["windows", "linux"]:
            raise ValueError(
                "Unsupported platform. Only 'windows' and 'linux' are supported."
            )

    # ==================
    # ===== render =====
    # ==================
    def _convert_contents(self) -> Image.Image:
        """
        把 contents 渲染为图像
        """
        # 先生成每一段的 Image，收集所有高度
        rendered_blocks: list[Image.Image] = []
        total_height = 0

        for content in self.contents:
            if isinstance(content, Text):
                block = self._render_text(content)

                line_spacing = NewLine(lines=1, height=int(content.font_size / 2))
                spacing_block = self._render_newline(line_spacing)
                rendered_blocks.append(spacing_block)
                total_height += spacing_block.height

            elif isinstance(content, BetweenText):
                block = self._render_betweentext(content)

                max_font_size = max(content.left_font_size, content.right_font_size)
                line_spacing = NewLine(lines=1, height=int(max_font_size / 2))
                spacing_block = self._render_newline(line_spacing)
                rendered_blocks.append(spacing_block)
                total_height += spacing_block.height

            elif isinstance(content, QrCode):
                block = self._render_qrcode(content)

            elif isinstance(content, NewLine):
                block = self._render_newline(content)

            elif isinstance(content, ImageContent):
                block = self._render_image(content)

            else:
                raise ValueError(f"Unsupported content type. {content}")

            rendered_blocks.append(block)
            total_height += block.height

        # 创建最终图像
        result_img = Image.new("L", (self.paper_width, total_height), color=255)
        y_offset = 0
        for block in rendered_blocks:
            result_img.paste(block, (0, y_offset))
            y_offset += block.height

        return result_img

    def _render_text(self, text_obj: Text) -> Image.Image:
        try:
            font = ImageFont.truetype(text_obj.font, text_obj.font_size)
        except Exception:
            font = ImageFont.load_default()

        words = list(text_obj.text)
        lines = []
        current_line = ""
        dummy_img = Image.new("L", (self.paper_width, 1), color=255)
        draw = ImageDraw.Draw(dummy_img)

        for word in words:
            test_line = current_line + ("" if current_line == "" else " ") + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            test_width = bbox[2] - bbox[0]

            if test_width <= self.paper_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        line_height = font.getbbox("A")[3] + 4  # 加些padding
        img_height = line_height * len(lines)
        img = Image.new("L", (self.paper_width, img_height), color=255)
        draw = ImageDraw.Draw(img)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]

            # 对齐
            if text_obj.align == "center":
                x = (self.paper_width - line_width) // 2
            elif text_obj.align == "right":
                x = self.paper_width - line_width
            else:  # left
                x = 0

            draw.text((x, i * line_height), line, font=font, fill=0)

        return img

    def _render_betweentext(self, bt_obj: BetweenText) -> Image.Image:
        # 加载字体
        try:
            left_font = ImageFont.truetype(bt_obj.left_font, bt_obj.left_font_size)
        except Exception:
            left_font = ImageFont.load_default()

        try:
            right_font = ImageFont.truetype(bt_obj.right_font, bt_obj.right_font_size)
        except Exception:
            right_font = ImageFont.load_default()

        draw_dummy = ImageDraw.Draw(Image.new("L", (self.paper_width, 1), color=255))

        def text_width(text, font):
            bbox = draw_dummy.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]

        def wrap_text(text, font):
            lines = []
            line = ""
            for char in text:
                test_line = line + char
                if text_width(test_line, font) <= self.paper_width:
                    line = test_line
                else:
                    if line:
                        lines.append(line)
                    line = char
            if line:
                lines.append(line)
            return lines

        total_width = text_width(bt_obj.left, left_font) + text_width(
            bt_obj.right, right_font
        )

        if total_width <= self.paper_width:
            # 一行能容下，左对齐 + 右对齐 同一行
            line_height = max(left_font.getbbox("A")[3], right_font.getbbox("A")[3]) + 4
            img = Image.new("L", (self.paper_width, line_height), color=255)
            draw = ImageDraw.Draw(img)

            draw.text((0, 0), bt_obj.left, font=left_font, fill=0)
            right_x = self.paper_width - text_width(bt_obj.right, right_font)
            draw.text((right_x, 0), bt_obj.right, font=right_font, fill=0)

            return img
        else:
            # 分开渲染多行
            left_lines = wrap_text(bt_obj.left, left_font)
            right_lines = wrap_text(bt_obj.right, right_font)

            left_line_height = left_font.getbbox("A")[3] + 4
            right_line_height = right_font.getbbox("A")[3] + 4

            left_img = Image.new(
                "L", (self.paper_width, left_line_height * len(left_lines)), color=255
            )
            draw_left = ImageDraw.Draw(left_img)
            for i, line in enumerate(left_lines):
                draw_left.text((0, i * left_line_height), line, font=left_font, fill=0)

            right_img = Image.new(
                "L", (self.paper_width, right_line_height * len(right_lines)), color=255
            )
            draw_right = ImageDraw.Draw(right_img)
            for i, line in enumerate(right_lines):
                x = self.paper_width - text_width(line, right_font)
                draw_right.text(
                    (x, i * right_line_height), line, font=right_font, fill=0
                )

            # 合并上下
            total_height = left_img.height + right_img.height
            final_img = Image.new("L", (self.paper_width, total_height), color=255)
            final_img.paste(left_img, (0, 0))
            final_img.paste(right_img, (0, left_img.height))

            return final_img

    def _render_qrcode(self, qr_obj: QrCode) -> Image.Image:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=qr_obj.box_size,
            border=qr_obj.border,
        )
        qr.add_data(qr_obj.data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white").convert("L")

        # 居中处理
        qr_width, qr_height = qr_img.size
        if qr_width > self.paper_width:
            qr_img = qr_img.resize((self.paper_width, self.paper_width))

        final_img = Image.new("L", (self.paper_width, qr_img.height), color=255)
        x = (self.paper_width - qr_img.width) // 2
        final_img.paste(qr_img, (x, 0))
        return final_img

    def _render_newline(self, newline_obj: NewLine) -> Image.Image:
        height = newline_obj.height * newline_obj.lines
        return Image.new("L", (self.paper_width, height), color=255)

    def _render_image(self, img_obj: ImageContent) -> Image.Image:
        img = img_obj.image.convert("L")  # 转灰度

        if img_obj.max_width:
            if img_obj.max_width > self.paper_width:
                img_obj.max_width = self.paper_width
            if img.width > img_obj.max_width:
                ratio = img_obj.max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((img_obj.max_width, new_height))

        # 居中
        canvas = Image.new("L", (self.paper_width, img.height), color=255)
        x = (self.paper_width - img.width) // 2
        canvas.paste(img, (x, 0))
        return canvas

    # =============================
    # ====== ESC/POS command ======
    # =============================
    def _escpos_init(self):
        """
        初始化打印机
        """
        self.commands += b"\x1b\x40"
        return self

    def _escpos_feed(self, lines=1):
        """
        进纸
        """
        self.commands += b"\x1b\x64" + bytes([lines])
        return self

    def _escpos_cut(self):
        """
        切纸
        """
        self.commands += b"\x1d\x56\x00"
        return self

    def _image_to_escpos(self, image):
        """
        将 PIL 黑白图像转换为 ESC/POS 图像打印指令(单色)并添加到命令列表中
        """
        # 二值化图像
        threshold = 200
        image = image.point(lambda p: 0 if p < threshold else 255, mode="1")

        width = image.width
        height = image.height
        if width % 8 != 0:
            new_width = (width + 7) & ~7
            image = image.resize((new_width, height))
            width = new_width

        data = bytearray()
        data += b"\x1d\x76\x30\x00"  # GS v 0
        data += (width // 8).to_bytes(2, "little")
        data += height.to_bytes(2, "little")

        pixels = image.load()
        for y in range(height):
            for x_byte in range(width // 8):
                byte = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if pixels[x, y] == 0:
                        byte |= 1 << (7 - bit)
                data.append(byte)

        self.commands += data
        return self

    def _escpos_send_windows(self):
        import win32print

        printer = win32print.OpenPrinter(self.printer_name)
        try:
            win32print.StartDocPrinter(printer, 1, ("ESC/POS Job", None, "RAW"))
            win32print.StartPagePrinter(printer)
            win32print.WritePrinter(printer, self.commands)
            win32print.EndPagePrinter(printer)
            win32print.EndDocPrinter(printer)
        finally:
            win32print.ClosePrinter(printer)

    def _escpos_send_linux(self):
        try:
            with open(self.printer_name, "wb") as printer:
                printer.write(self.commands)
        except FileNotFoundError:
            raise ValueError(f"Printer '{self.printer_name}' not found.")
        except PermissionError:
            raise ValueError(
                f"Permission denied to access printer '{self.printer_name}'."
            )

    def _escpos_send(self):
        """
        发送命令到打印机
        """
        if self.platform == "windows":
            self._escpos_send_windows()
        elif self.platform == "linux":
            self._escpos_send_linux()
        else:
            raise ValueError(
                "Unsupported platform. Only 'windows' and 'linux' are supported."
            )

    # ==========================
    # ===== public methods =====
    # ==========================
    def text(
        self,
        *,
        text,
        align="left",
        font_size=FONT_SIZES["md"],
        font=None,
    ):
        """
        打印文本内容

        :param align: 对齐方式 ("left" | "center" | "right")
            - default: "left"
        :param bold: 是否加粗
        :param content: 文本内容
        """
        if font is None:
            font = self.default_font
        self.contents.append(
            Text(text=text, align=align, font_size=font_size, font=font)
        )
        return self

    def betweentext(
        self,
        *,
        left,
        right,
        left_font_size=FONT_SIZES["md"],
        right_font_size=FONT_SIZES["md"],
        left_font=None,
        right_font=None,
    ):
        """
        打印左右对齐的文本内容

        :param left: 左侧文本内容
        :param right: 右侧文本内容
        :param left_font_size: 左侧文本字体大小
        :param right_font_size: 右侧文本字体大小
        :param left_font: 左侧文本字体路径
        :param right_font: 右侧文本字体路径
        """
        if left_font is None:
            left_font = self.default_font
        if right_font is None:
            right_font = self.default_font
        self.contents.append(
            BetweenText(
                left=left,
                right=right,
                left_font_size=left_font_size,
                right_font_size=right_font_size,
                left_font=left_font,
                right_font=right_font,
            )
        )
        return self

    def newline(self, *, height=28, lines=1):
        """
        换行

        :param height: 换行高度
            - default: 28
        :param lines: 换行的行数
            - default: 1
        """
        self.contents.append(NewLine(lines=lines, height=height))
        return self

    def qrcode(self, *, data, size="lg"):
        """
        打印二维码

        :param data: 二维码内容
        :param size: 二维码大小 ("sm" | "md" | "lg")
        """
        if size == "sm":
            box_size = 8
            border = 2
        elif size == "md":
            box_size = 10
            border = 2
        elif size == "lg":
            box_size = 16
            border = 2
        else:
            raise ValueError("Invalid size. Choose 'sm', 'md', or 'lg'.")

        self.contents.append(QrCode(data=data, box_size=box_size, border=border))
        return self

    def image(
        self,
        *,
        image_path,
        max_width=None,
    ):
        """
        打印图片

        :param image_path: 图片路径
        :param max_width: 图片最大宽度 (int | None | "full")
            - int: 缩放到指定宽度
            - None: 不缩放 (大于纸张宽度时会自动缩放到纸张宽度)
            - "full": 缩放到纸张宽度
            - default: None
        """
        if max_width == "full":
            max_width = self.paper_width

        image = Image.open(image_path).convert("L")
        self.contents.append(ImageContent(image=image, max_width=max_width))
        return self

    def print(self):
        """
        打印所有内容
        """
        image = self._convert_contents()
        # fmt: off
        self \
            ._escpos_init() \
            ._escpos_feed(4) \
            ._image_to_escpos(image) \
            ._escpos_feed(4) \
            ._escpos_cut() \
            ._escpos_send()
        # fmt: on

    def clear(self):
        """
        清空内容和命令
        """
        self.contents.clear()
        self.commands.clear()
