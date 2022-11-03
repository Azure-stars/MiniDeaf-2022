对于 step7 添加部分：

namer.py

```python
def visitBlock(self, block: Block, ctx: ScopeStack) -> None:
    new_score = Scope(ScopeKind.LOCAL)
    ctx.open(new_score)
    for child in block:
        child.accept(self, ctx)
    ctx.close()
```

cfg.py

```python
def judge(self, id: int):
    if id != 0:
        return self.getInDegree(id) != 0
    return True
```
