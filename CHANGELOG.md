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
