# About escpos_printer_control
⚠ 目前只支持通过 USB 连接的打印机。欢迎高人贡献代码让这个破东西支持串口和网络打印机。

一个小库让你用 python 控制支持 ESC/POS 指令集的打印机。

通过把字体转化为图像 (使用Pillow) 再发给打印机实现打印不支持的字体。

## Features
- QRCode
  - 通过第三方库 `qrcode` 提供支持
  - 支持自定义大小, 但不支持周围浮动字体
- 多国语言 (目前只支持从左到右排版的语言)
- 自定义字体
- 字体排版
  - 支持自动换行
- Flex Layout
  - 支持嵌套, 嵌套时需要使用 `printer.FlexItem.flex()`
- 图片
  - 通过 `Pillow` 支持, 只支持黑白, 非黑白图像会被转为黑白, 不保证打印效果。
- 多操作系统
  - Linux
    - 在 Linux 中这个库直接使用 `open` + `write` 向打印机发送 ESC/POS 指令
  - Windows
    - 在 Windows 上这个库使用 `win32print` 来寻找打印机以及发送 ESC/POS 指令
  - 目前在 RaspberryOS 和 Windows 11 中做了测试。按理来说 macOS 也能用, 但没测过。

## 在 Linux / RaspberryPi 中使用

- 你的打印机支持连接 Linux
- 能运行 python3.11 以上并且有足够内存运行 Pillow (经测试 Raspberry Pi zero 2 可以稳定运行)
- 需要自己安装需要打印的字体到 OS 中
- 当前用户有权限操作 USB 设备

按理来说 macOS 也能和 Linux 一样使用, 但未经测试

使用 Raspberry Pi zero 2 W + 汉印 HPRT TP582 测试

### Linux Setup
首先克隆这个库, 或者用 git submodule 或者用别的方法下载下来都行。(可能之后会分发到 pip, 有点懒)
```sh
git clone <this-repo-url>
```

这个库有依赖, 所以你需要先安装依赖库
```sh
pip install pillow qrcode
```

然后按照 python 导入方式导进去就行了。

**注意:**

在 Linux 中这个库直接使用 `open` + `write` 向打印机发送 ESC/POS 指令

因为很多打印机的机器名字和在 `lsusb` 中看到的 Device 名称不同, 所以目前你需要自己寻找你的设备连接到了哪个口。(一般是 `/dev/usb/lp0`)

下面我以 `汉印 HPRT TP582` + `RaspberryPi Zero 2 W` 作为例子展示如何看你的打印机连接到了哪个口

#### Find USB Device
首先把打印机的 USB 连上树莓派的 OTG 口 (数据口), 然后用输入下面的指令查看当前连接的 USB 设备
```sh
lsusb
```

然后应该会看到类似下面这类的输出。(下面这段是 TP582 的输出, 其他打印机不一样)
```txt
Bus 001 Device 001: ID 810y:1919 WinChipHead CH34x printer adapter cable
```

这就说明你的打印机成功被识别了。然后你需要找它被挂载到哪个口了, 你可以输下面这段指令来看最近 30 行的 dmesg。(如果你途中又连了其他设备可以先拔掉打印机然后再连一边, 让打印机成为最后一个连接到的电脑的设备)
```sh
dmesg | tail -n 30
```

然后你应该会看到类似下面的输出
```txt
[  434.677311] usb 1-1: USB disconnect, device number 2
[  434.677989] usblp0: removed
[  449.438553] Indeed it is in host mode hprt0 = 00021501
[  449.618484] usb 1-1: new full-speed USB device number 3 using dwc_otg
[  449.618691] Indeed it is in host mode hprt0 = 00021501
[  449.815702] usb 1-1: New USB device found, idVendor=1919, idProduct=8100, bcdDevice= 0.00
[  449.815735] usb 1-1: New USB device strings: Mfr=1, Product=2, SerialNumber=0
[  449.815752] usb 1-1: Product: TP582
[  449.815766] usb 1-1: Manufacturer: HPRT
[  449.817233] usblp 1-1:1.0: usblp0: USB Bidirectional printer dev 3 if 0 alt 0 proto 2 vid 0x1919 pid 0x8100
```

找到那行分配设备号的 log, 你会发现被分配到了 `usblp0`
```txt
[  449.817233] usblp 1-1:1.0: usblp0: USB Bidirectional printer dev 3 if 0 alt 0 proto 2 vid 0x1919 pid 0x8100
```

此时有可能在 `/dev/usblp0` 或者 `/dev/usb/lp0`, 用 `ls` 看一眼就知道在哪了。

最后把这个路径传递给 `printer_name` 就行

### Linux Example
以下代码在 RaspberryPi Zero 2 W + 汉印 HPRT TP582 上进行测试

你需要安装 NotoSansCJK 字体到 OS 中。如果你使用 Debian 系的 Linux 可以使用下面这串指令来安装。
```sh
sudo apt install fonts-noto-cjk
```

```py
from escpos_printer import EscPosPrinter, PrinterConfig
from const import FONT_SIZES
from PIL import Image, ImageDraw


def draw_hollow_square(
    size: int,
    square_size: int,
    line_width: int = 2,
    corner_radius: int = 0,
    line_color: str = "black",
    background_color: str = "white",
):
    img = Image.new("RGB", (size, size), color=background_color)
    draw = ImageDraw.Draw(img)

    left = (size - square_size) // 2
    top = (size - square_size) // 2
    right = left + square_size
    bottom = top + square_size

    if corner_radius > 0:
        draw.rounded_rectangle(
            [left, top, right, bottom],
            radius=corner_radius,
            outline=line_color,
            width=line_width,
        )
    else:
        draw.rectangle([left, top, right, bottom], outline=line_color, width=line_width)

    return img

if __name__ == "__main__":
    # 示例：创建一个打印机对象，指定打印机名称和纸张宽度
    printer = EscPosPrinter(
        config=PrinterConfig(
            printer_name="/dev/usb/lp0",
            paper_width="58mm",
            default_font="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        )
    )
    checkbox = draw_hollow_square(size=20, square_size=16)

    # fmt: off
    printer \
        .text(
            text="Hello, World!",
            font_size=FONT_SIZES["sm"],
            align="right",
        ) \
        .text(
            text="こんにちは。この行は結構長いと思いますので、ご注意ください。",
            font_size=FONT_SIZES["md"],
            align="center",
        ) \
        .text(
            text="靠左对齐的文本",
            align="left",
            font_size=FONT_SIZES["lg"],
        ) \
        .flex(
            items=[
                printer.FlexItem.flex(
                    items=[
                        printer.FlexItem.image(
                            image=checkbox,
                        ),
                        printer.FlexItem.text(
                            text="可乐:"
                        ),
                    ],
                    vertical_align="center",
                    item_gap=5,
                ),
                printer.FlexItem.text(
                    text="12.00元"
                ),
            ],
            horizontal_align="between",
            vertical_align="center",
        ) \
        .qrcode(
            data="https://www.google.com",
            size="lg"
        ).print()
```

## 在 Windows 中使用

- 你的打印机支持连接 Windows, 并且你已经在 Windows 上安装了对应打印机的驱动

### Windows Setup
首先克隆这个库, 或者用 git submodule 或者用别的方法下载下来都行。(可能之后会分发到 pip, 有点懒)
```sh
git clone <this-repo-url>
```

这个库有依赖, 所以你需要先安装依赖库
```sh
pip install pillow qrcode
```

然后按照 python 导入方式导进去就行了。

在 Windows 上这个库使用 `win32print` 来寻找打印机以及发送 ESC/POS 指令

所以你只需要在 `printer_name` 中填写打印机的名字就行

### Windows Example
以下代码在 Windows 11 + 汉印 HPRT TP582 上进行测试。

使用 Windows 11 自带的默认字体, 应该能直接跑。

```py
from escpos_printer import EscPosPrinter, PrinterConfig
from const import FONT_SIZES
from PIL import Image, ImageDraw


def draw_hollow_square(
    size: int,
    square_size: int,
    line_width: int = 2,
    corner_radius: int = 0,
    line_color: str = "black",
    background_color: str = "white",
):
    img = Image.new("RGB", (size, size), color=background_color)
    draw = ImageDraw.Draw(img)

    left = (size - square_size) // 2
    top = (size - square_size) // 2
    right = left + square_size
    bottom = top + square_size

    if corner_radius > 0:
        draw.rounded_rectangle(
            [left, top, right, bottom],
            radius=corner_radius,
            outline=line_color,
            width=line_width,
        )
    else:
        draw.rectangle([left, top, right, bottom], outline=line_color, width=line_width)

    return img

if __name__ == "__main__":
    # 示例：创建一个打印机对象，指定打印机名称和纸张宽度
    printer = EscPosPrinter(
        config=PrinterConfig(
            printer_name="TP582",
            paper_width="58mm",
            default_font="C:/Windows/Fonts/msyh.ttc",
        )
    )
    checkbox = draw_hollow_square(size=20, square_size=16)

    # fmt: off
    printer \
        .text(
            text="Hello, World!",
            font_size=FONT_SIZES["sm"],
            align="right",
        ) \
        .text(
            text="こんにちは。この行は結構長いと思いますので、ご注意ください。",
            font_size=FONT_SIZES["md"],
            align="center",
        ) \
        .text(
            text="靠左对齐的文本",
            align="left",
            font_size=FONT_SIZES["lg"],
        ) \
        .flex(
            items=[
                printer.FlexItem.flex(
                    items=[
                        printer.FlexItem.image(
                            image=checkbox,
                        ),
                        printer.FlexItem.text(
                            text="可乐:"
                        ),
                    ],
                    vertical_align="center",
                    item_gap=5,
                ),
                printer.FlexItem.text(
                    text="12.00元"
                ),
            ],
            horizontal_align="between",
            vertical_align="center",
        ) \
        .qrcode(
            data="https://www.google.com",
            size="lg"
        ).print()
```