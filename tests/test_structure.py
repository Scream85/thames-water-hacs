import ast, pathlib, sys
bad = []
for f in pathlib.Path("custom_components/thames_water_meter").glob("*.py"):
    for n in ast.walk(ast.parse(f.read_text())):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.returns is not None:
            ann = ast.unparse(n.returns)
            if ann != "None" and not any(isinstance(x, ast.Return) and x.value is not None for x in ast.walk(n)) \
               and not any(isinstance(x, ast.Yield) for x in ast.walk(n)):
                bad.append(f"{f.name}:{n.name} -> {ann} has no return")
assert not bad, bad
print("structure ok")
