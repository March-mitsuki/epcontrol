from __future__ import annotations
import dataclasses
import sys

from PIL import Image, ImageDraw, ImageFont
import qrcode

from .const import PAPER_WIDTH, FONT_SIZES


@dataclasses.dataclass
class UsbInfo:
    """
    打印机连接类, 现在只用于 macOS

    :param vendor_id: USB 设备的供应商 ID
    :param product_id: USB 设备的产品 ID
    :param interface: USB 接口号
    :param in_ep: 输入端点
    :param out_ep: 输出端点
    """

    vendor_id: int
    product_id: int
    interface: int = 0
    in_ep: int = 0x81
    out_ep: int = 0x02


@dataclasses.dataclass
class PrinterConfig:
    """
    打印机配置类

    :param printer_name: 打印机名称
        - 在 Windows 中是 `win32print.OpenPrinter` 的参数
        - 在 Linux 中是 `/dev/usb/lp0` 或 `/dev/usb/lp1` 等设备文件, 会通过 `open` 打开

    :param paper_width: 纸张宽度, 详见`const.PAPER_WIDTH`

    :param default_font: 默认字体路径

    :param platform: 打印机平台 ("windows" | "linux" | "macos)
        - default: 自动检测
    """

    printer_name: str
    paper_width: str
    default_font: str
    platform: str | None = None
    padding_x: int = 10


@dataclasses.dataclass
class Text:
    text: str
    align: str
    font_size: int
    font: str
    line_spacing: int


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


@dataclasses.dataclass
class Flex:
    items: list[Text | QrCode | ImageContent | Flex]
    # Gap between items in same row
    item_gap: int
    # Gap between rows
    row_gap: int
    # Horizontal alignment: "left" | "right" | "between"
    horizontal_align: str
    # Vertical alignment: "top" | "center" | "bottom"
    vertical_align: str
    max_width: int | None = None


class FlexItemFactory:
    def __init__(self, default_font: str, paper_width: int):
        self.default_font = default_font
        self.paper_width = paper_width

    def text(
        self,
        *,
        text,
        aligin="left",
        font_size=FONT_SIZES["md"],
        font=None,
    ) -> Text:
        if font is None:
            font = self.default_font

        return Text(
            text=text,
            align=aligin,
            font_size=font_size,
            font=font,
            line_spacing=0,
        )

    def qrcode(self, *, data, size="lg") -> QrCode:
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

        return QrCode(data=data, box_size=box_size, border=border)

    def image(
        self,
        *,
        image=None,
        max_width=None,
    ):
        if max_width == "full":
            max_width = self.paper_width

        if image is None:
            raise ValueError("Image must be provided.")

        return ImageContent(image=image, max_width=max_width)

    def flex(
        self,
        *,
        items: list[Text | QrCode | ImageContent | Flex],
        item_gap: int = 0,
        row_gap: int = 0,
        horizontal_align: str = "left",
        vertical_align: str = "top",
        max_width: int | None = None,
    ) -> Flex:
        return Flex(
            items=items,
            item_gap=item_gap,
            row_gap=row_gap,
            horizontal_align=horizontal_align,
            vertical_align=vertical_align,
            max_width=max_width,
        )


class FlexRenderer:
    def __init__(self, flex: Flex, max_width: int | None):
        self.flex_obj = flex
        self.max_width = max_width

    def _render_text(self, text_obj: Text, current_x: int) -> list[Image.Image]:
        """
        Render a Text object to a list of images, each representing a single line of text.
        Start rendering from the given current_x position.

        Will ignore the Text.align and Text.line_spacing attributes.
        You can use the Flex.row_gap and Flex.item_gap attributes to control the spacing.
        """
        try:
            font = ImageFont.truetype(text_obj.font, text_obj.font_size)
        except Exception:
            font = ImageFont.load_default()

        # Split text into lines based on container width and current_x
        lines = []
        current_line = ""
        line_images = []
        if self.max_width is None:
            available_width = float("inf")
        else:
            available_width = self.max_width - current_x

        for char in text_obj.text:
            test_line = current_line + char
            dummy_img = Image.new("L", (1, 1), color=255)
            draw = ImageDraw.Draw(dummy_img)
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] > available_width:  # If line exceeds available width
                lines.append((current_line, available_width))
                current_line = char
                available_width = self.max_width  # Reset available width for new line
            else:
                current_line = test_line
        if current_line:  # Add the last line
            lines.append((current_line, available_width))

        # Render each line as a separate image
        for line, line_width in lines:
            dummy_img = Image.new("L", (1, 1), color=255)
            draw = ImageDraw.Draw(dummy_img)
            actual_line_width = draw.textbbox((0, 0), line, font=font)[2]
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]  # Ensure height includes baseline content
            img = Image.new("L", (actual_line_width, line_height), color=255)
            draw = ImageDraw.Draw(img)
            draw.text((0, -bbox[1]), line, font=font, fill=0)  # Adjust for baseline
            line_images.append(img)

        return line_images

    def _render_qrcode(self, qr_obj: QrCode) -> Image.Image:
        """
        Render a QrCode object to an image.
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=qr_obj.box_size,
            border=qr_obj.border,
        )
        qr.add_data(qr_obj.data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white").convert("L")
        return qr_img

    def _render_image(self, img_obj: ImageContent) -> Image.Image:
        """
        Render an ImageContent object to an image.
        """
        img = img_obj.image.convert("L")
        if img_obj.max_width and img.width > img_obj.max_width:
            ratio = img_obj.max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((img_obj.max_width, new_height))

        return img

    def render(self) -> Image.Image:
        """
        Render a Flex object using Pillow, following CSS flexbox logic.

        :return: A rendered image.
        """
        items = self.flex_obj.items

        # Render each item and calculate positions with wrapping
        rendered_items = []
        item_positions = []
        current_x = 0
        current_y = 0
        max_row_height = 0
        rendered_width = 0

        for item in items:
            if isinstance(item, Text):
                line_images = self._render_text(item, current_x)
                for line_img in line_images:
                    item_width, item_height = line_img.size

                    # Check if the item fits in the current row
                    if self.max_width and current_x + item_width > self.max_width:
                        # Move to the next row
                        current_x = 0
                        current_y += max_row_height + self.flex_obj.row_gap
                        max_row_height = 0

                    # Update max_row_height for the current row
                    max_row_height = max(max_row_height, item_height)

                    # Store the position and rendered item
                    item_positions.append((current_x, current_y))
                    rendered_items.append(line_img)

                    # Update current_x for the next item, including item_gap
                    current_x += item_width + self.flex_obj.item_gap

                    # Update rendered_width
                    rendered_width = max(rendered_width, current_x)

            elif isinstance(item, QrCode):
                rendered_item = self._render_qrcode(item)
                item_width, item_height = rendered_item.size

                # Check if the item fits in the current row
                if self.max_width and current_x + item_width > self.max_width:
                    # Move to the next row
                    current_x = 0
                    current_y += max_row_height + self.flex_obj.row_gap
                    max_row_height = 0

                # Update max_row_height for the current row
                max_row_height = max(max_row_height, item_height)

                # Store the position and rendered item
                item_positions.append((current_x, current_y))
                rendered_items.append(rendered_item)

                # Update current_x for the next item, including item_gap
                current_x += item_width + self.flex_obj.item_gap

                # Update rendered_width
                rendered_width = max(rendered_width, current_x)

            elif isinstance(item, ImageContent):
                rendered_item = self._render_image(item)
                item_width, item_height = rendered_item.size

                # Check if the item fits in the current row
                if self.max_width and current_x + item_width > self.max_width:
                    # Move to the next row
                    current_x = 0
                    current_y += max_row_height + self.flex_obj.row_gap
                    max_row_height = 0

                # Update max_row_height for the current row
                max_row_height = max(max_row_height, item_height)

                # Store the position and rendered item
                item_positions.append((current_x, current_y))
                rendered_items.append(rendered_item)

                # Update current_x for the next item, including item_gap
                current_x += item_width + self.flex_obj.item_gap

                # Update rendered_width
                rendered_width = max(rendered_width, current_x)

            elif isinstance(item, Flex):
                # Recursively render nested Flex items
                nested_renderer = FlexRenderer(item, item.max_width)
                nested_img = nested_renderer.render()
                item_width, item_height = nested_img.size

                # Check if the item fits in the current row
                if current_x + item_width > self.max_width:
                    # Move to the next row
                    current_x = 0
                    current_y += max_row_height + self.flex_obj.row_gap
                    max_row_height = 0

                # Update max_row_height for the current row
                max_row_height = max(max_row_height, item_height)

                # Store the position and rendered item
                item_positions.append((current_x, current_y))
                rendered_items.append(nested_img)

                # Update current_x for the next item, including item_gap
                current_x += item_width + self.flex_obj.item_gap

            else:
                raise ValueError(f"Unsupported item type: {item}")

        # Calculate total height of the rendered content
        total_height = current_y + max_row_height

        # Adjust positions based on horizontal_align
        if self.flex_obj.horizontal_align == "right":
            row_widths = {}
            for (x, y), item_img in zip(item_positions, rendered_items):
                row_widths.setdefault(y, 0)
                row_widths[y] += item_img.size[0] + self.flex_obj.item_gap
            for i, ((x, y), item_img) in enumerate(zip(item_positions, rendered_items)):
                row_width = row_widths[y] - self.flex_obj.item_gap  # Remove extra gap
                offset = self.max_width - row_width
                item_positions[i] = (x + offset, y)
        elif self.flex_obj.horizontal_align == "between":
            row_items = {}
            for (x, y), item_img in zip(item_positions, rendered_items):
                row_items.setdefault(y, []).append((x, item_img))
            for y, items_in_row in row_items.items():
                total_row_width = sum(item.size[0] for _, item in items_in_row)
                total_gaps = len(items_in_row) - 1
                if total_gaps > 0:
                    extra_gap = (self.max_width - total_row_width) // total_gaps
                else:
                    extra_gap = 0
                current_x = 0
                for i, (original_x, item_img) in enumerate(items_in_row):
                    item_width = item_img.size[0]
                    for j, ((x, row_y), _) in enumerate(
                        zip(item_positions, rendered_items)
                    ):
                        if row_y == y and x == original_x:
                            item_positions[j] = (current_x, row_y)
                            break
                    current_x += item_width + extra_gap

        # Adjust positions based on vertical_align
        if self.flex_obj.vertical_align in ["center", "bottom"]:
            row_heights = {}
            for (x, y), item_img in zip(item_positions, rendered_items):
                row_heights.setdefault(y, 0)
                row_heights[y] = max(row_heights[y], item_img.size[1])
            for i, ((x, y), item_img) in enumerate(zip(item_positions, rendered_items)):
                row_height = row_heights[y]
                if self.flex_obj.vertical_align == "center":
                    offset = (row_height - item_img.size[1]) // 2
                elif self.flex_obj.vertical_align == "bottom":
                    offset = row_height - item_img.size[1]
                else:
                    offset = 0
                item_positions[i] = (x, y + offset)

        # Create the final image
        if self.max_width is None:
            image_width = rendered_width
        else:
            image_width = self.max_width

        final_img = Image.new("L", (image_width, total_height), color=255)
        for (x, y), item_img in zip(item_positions, rendered_items):
            final_img.paste(item_img, (x, y))

        return final_img


ContentUnion = Text | QrCode | NewLine | ImageContent | Flex


class Content:
    Text = Text
    QrCode = QrCode
    NewLine = NewLine
    ImageContent = ImageContent
    Flex = Flex


@dataclasses.dataclass
class _RenderedBlock:
    image: Image.Image
    x: int


class EscPosPrinter:
    """
    ESC/POS 打印机类

    把所有打印内容渲染为图像，然后通过 ESC/POS 指令发送到打印机
    """

    def __init__(self, config: PrinterConfig, usb_info: UsbInfo | None = None):
        # Setup printer config
        self._validate_config(config)
        self.printer_name = config.printer_name
        self.paper_width = PAPER_WIDTH[config.paper_width]
        self.default_font = config.default_font
        self.padding_x = config.padding_x
        if config.platform is None:
            if sys.platform.startswith("win"):
                self.platform = "windows"
            elif sys.platform.startswith("linux"):
                self.platform = "linux"
            elif sys.platform.startswith("darwin"):
                self.platform = "macos"
            else:
                raise ValueError(f"Unsupported platform: {sys.platform}")
        else:
            self.platform = config.platform

        self.usb_info = usb_info
        if config.platform == "macos" and usb_info is None:
            raise ValueError("macos_connect must be provided for macOS platform.")

        self.contents: list[ContentUnion] = []
        # ESC/POS commands
        self.commands = bytearray()

        # add helper
        self.FlexItem = FlexItemFactory(self.default_font, self.paper_width)

    def _validate_config(self, config: PrinterConfig):
        if config.paper_width not in PAPER_WIDTH:
            raise ValueError("Invalid Config: paper_width. Choose '58mm' or '80mm'.")
        if config.platform is not None and config.platform not in [
            "windows",
            "linux",
            "macos",
        ]:
            raise ValueError("Invalid Config: Unsupported platform.")

    # ==================
    # ===== render =====
    # ==================
    def _convert_contents(self) -> Image.Image:
        """
        把 contents 渲染为图像
        """
        # 先生成每一段的 Image，收集所有高度
        rendered_blocks: list[_RenderedBlock] = []
        total_height = 0

        for content in self.contents:
            if isinstance(content, Text):
                blocks = self._render_text(content)
                for index, _block in enumerate(blocks):
                    if len(blocks) > 1 and index > 0 and content.line_spacing > 0:
                        spacing_bloak = self._render_newline(
                            NewLine(lines=1, height=content.line_spacing)
                        )
                        rendered_blocks.append(_RenderedBlock(spacing_bloak, 0))
                        total_height += spacing_bloak.height

                    rendered_blocks.append(_RenderedBlock(_block, 0))
                    total_height += _block.height

            elif isinstance(content, QrCode):
                block = self._render_qrcode(content)
                rendered_blocks.append(_RenderedBlock(block, 0))
                total_height += block.height

            elif isinstance(content, NewLine):
                block = self._render_newline(content)
                rendered_blocks.append(_RenderedBlock(block, 0))
                total_height += block.height

            elif isinstance(content, ImageContent):
                block = self._render_image(content)
                rendered_blocks.append(_RenderedBlock(block, 0))
                total_height += block.height

            elif isinstance(content, Flex):
                renderer = FlexRenderer(content, self.paper_width - 2 * self.padding_x)
                block = renderer.render()
                rendered_blocks.append(_RenderedBlock(block, self.padding_x))
                total_height += block.height

            else:
                raise ValueError(f"Unsupported content type. {content}")
        # 创建最终图像
        result_img = Image.new("L", (self.paper_width, total_height), color=255)
        y_offset = 0
        for block in rendered_blocks:
            result_img.paste(block.image, (block.x, y_offset))
            y_offset += block.image.height

        return result_img

    def _render_text(self, text_obj: Text) -> list[Image.Image]:
        try:
            font = ImageFont.truetype(text_obj.font, text_obj.font_size)
        except Exception:
            font = ImageFont.load_default()

        # Split text into lines based on container width and current_x
        lines = []
        current_line = ""
        line_images = []

        for char in text_obj.text:
            test_line = current_line + char
            dummy_img = Image.new("L", (1, 1), color=255)
            draw = ImageDraw.Draw(dummy_img)
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] > (
                self.paper_width - 2 * self.padding_x
            ):  # Adjust for padding_x
                lines.append((current_line, self.paper_width - 2 * self.padding_x))
                current_line = char
            else:
                current_line = test_line
        if current_line:  # Add the last line
            lines.append((current_line, self.paper_width - 2 * self.padding_x))

        # Render each line as a separate image
        for line, line_width in lines:
            dummy_img = Image.new("L", (1, 1), color=255)
            draw = ImageDraw.Draw(dummy_img)
            actual_line_width = draw.textbbox((0, 0), line, font=font)[2]
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]  # Ensure height includes baseline content

            if text_obj.align == "left":
                x_offset = self.padding_x
            elif text_obj.align == "center":
                x_offset = (self.paper_width - actual_line_width) // 2
            elif text_obj.align == "right":
                x_offset = self.paper_width - actual_line_width - self.padding_x
            else:
                raise ValueError(f"Unsupported alignment: {text_obj.align}")

            img = Image.new("L", (self.paper_width, line_height), color=255)
            draw = ImageDraw.Draw(img)
            draw.text(
                (x_offset, -bbox[1]), line, font=font, fill=0
            )  # Adjust for baseline
            line_images.append(img)

        return line_images

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

        # Centering with padding_x
        qr_width, qr_height = qr_img.size
        if qr_width > (self.paper_width - 2 * self.padding_x):
            qr_img = qr_img.resize(
                (
                    self.paper_width - 2 * self.padding_x,
                    self.paper_width - 2 * self.padding_x,
                )
            )

        final_img = Image.new("L", (self.paper_width, qr_img.height), color=255)
        x = (self.paper_width - qr_img.width) // 2
        final_img.paste(qr_img, (x, 0))
        return final_img

    def _render_newline(self, newline_obj: NewLine) -> Image.Image:
        height = newline_obj.height * newline_obj.lines
        return Image.new("L", (self.paper_width, height), color=255)

    def _render_image(self, img_obj: ImageContent) -> Image.Image:
        img = img_obj.image.convert("L")  # Convert to grayscale

        if img_obj.max_width:
            if img_obj.max_width > (self.paper_width - 2 * self.padding_x):
                img_obj.max_width = self.paper_width - 2 * self.padding_x
            if img.width > img_obj.max_width:
                ratio = img_obj.max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((img_obj.max_width, new_height))
        else:
            if img.width > (self.paper_width - 2 * self.padding_x):
                ratio = (self.paper_width - 2 * self.padding_x) / img.width
                new_height = int(img.height * ratio)
                img = img.resize((self.paper_width - 2 * self.padding_x, new_height))

        # Centering with padding_x
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

    def _escpos_send_macos(self):
        from escpos.printer import Usb

        if not self.usb_info:
            raise ValueError("USB info is required for macOS platform.")

        p = Usb(
            self.usb_info.vendor_id,
            self.usb_info.product_id,
            interface=self.usb_info.interface,
            in_ep=self.usb_info.in_ep,
            out_ep=self.usb_info.out_ep,
        )
        p._raw(self.commands)

    def _escpos_send(self):
        """
        发送命令到打印机
        """
        if self.platform == "windows":
            self._escpos_send_windows()
        elif self.platform == "linux":
            self._escpos_send_linux()
        elif self.platform == "macos":
            self._escpos_send_macos()
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
        line_spacing=4,
    ):
        """
        打印文本内容

        :param text: 文本内容
        :param align: 对齐方式 ("left" | "center" | "right")
            - default: "left"
        :param font_size: 字体大小 (int)
        :param font: 字体路径
            - default: self.default_font
        :param line_spacing: 行间距 (int)
            - default: 4
        """
        if font is None:
            font = self.default_font
        self.contents.append(
            Text(
                text=text,
                align=align,
                font_size=font_size,
                font=font,
                line_spacing=line_spacing,
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
        image=None,
        max_width=None,
    ):
        """
        打印图片

        :param image: (str | Image.Image)
            - str: 图片路径
            - Image.Image: PIL 图像对象
        :param max_width: 图片最大宽度 (int | None | "full")
            - int: 缩放到指定宽度
            - None: 不缩放 (大于纸张宽度时会自动缩放到纸张宽度)
            - "full": 缩放到纸张宽度
            - default: None
        """
        if max_width == "full":
            max_width = self.paper_width

        if image is None:
            raise ValueError("Image must be provided.")

        if not isinstance(image, Image.Image) and not isinstance(image, str):
            raise ValueError("Image must be a PIL Image or a file path.")

        if isinstance(image, str):
            image = Image.open(image).convert("L")

        self.contents.append(ImageContent(image=image, max_width=max_width))
        return self

    def flex(
        self,
        *,
        items: list[Text | QrCode | ImageContent | Flex],
        item_gap: int = 0,
        row_gap: int = 0,
        horizontal_align: str = "left",
        vertical_align: str = "top",
    ):
        """
        打印 Flex 布局内容

        :param items: Flex 布局的内容列表
            - list[Text | QrCode | ImageContent]
        :param item_gap: 同一行内元素之间的间距 (int)
            - default: 0
        :param row_gap: 行与行之间的间距 (int)
            - default: 0
        :param horizontal_align: 水平对齐方式 ("left" | "right" | "between")
            - default: "left"
        :param vertical_align: 垂直对齐方式 ("top" | "center" | "bottom")
            - default: "top"
        """
        self.contents.append(
            Flex(
                items=items,
                item_gap=item_gap,
                row_gap=row_gap,
                horizontal_align=horizontal_align,
                vertical_align=vertical_align,
                max_width=self.paper_width,
            )
        )
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

    # =========================
    # ====== debugging ========
    # =========================
    def _debug_converted_image(self, hasgui=False):
        """
        显示转换后的图像

        :param hasgui: 是否有 GUI 环境 (用于调试)
            - default: False
            - 如果有 GUI 环境, 则显示图像
            - 如果没有 GUI 环境, 则转换为 jpeg base64 字符串并打印
        """
        image = self._convert_contents()
        if hasgui:
            image.show()
        else:
            import base64
            from io import BytesIO

            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            print(f"data:image/jpeg;base64,{img_str}")
