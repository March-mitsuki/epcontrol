# 0.7.0
## Changed
- EscPosPrinter.print()
  - 现在接受 padding_top: int 和 padding_bottom: int 来控制打印内容前后的进纸

# 0.6.1
font_sizes 从
```py
self.font_sizes = config.font_sizes or DEFAULT_FONT_SIZES
```
改为
```py
self.font_sizes = {
   **DEFAULT_FONT_SIZES,
   **(config.font_sizes if config.font_sizes else {}),
}
```
现在不会直接全部覆盖默认设定了

# 0.6.0
## Add
- PrinterConfig.font_sizes()

## Change
- EscPosPrinter.qrcode()
  - 现在 size 除了 str 还接受一个长度为 2 的 Tuple, 第一个是 box_size, 第二个是 border
- EscPosPrinter.text()
  - 现在 font_size 接受 int | str | None
    - 如果是 int 直接设置
    - 如果是 str 则从 self.font_sizes 中读取
    - 如果是 None 默认为 self.font_sizes["md"]

# v0.5.0
- printer.text()
  - 增加 line_spacing 参数, 当text长度大于一行时的行间距

# v0.4.0
## Add
Add macOS support

# v0.3.0
## Add
- PrinterConfig.padding_x

# v0.2.1
## Fix
- EscPosPrinter.text()
  - 修复了 align 不起作用的问题

# v0.2.0
## Remove
- EscPosPrinter.betweentext()

## Add
- EscPosPrinter.FlexItem
- EscPosPrinter.flex()

## Change
- EscPosPrinter.image()
```py
printer = EscPosPrinter(
   # ...
)

# Old
printer.image(
   path="/foo/bar.png"
)

# New
printer.image(
   image="/foo/bar.png"
)
printer.image(
   image=Image.open("/foo/bar.png").convert("L")
)
```


# v0.1.0
init
