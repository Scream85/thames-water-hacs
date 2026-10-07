import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "diagnostics", "custom_components/thames_water_meter/diagnostics.py"
)
d = importlib.util.module_from_spec(spec)
sys.modules["diagnostics"] = d
spec.loader.exec_module(d)


class R:  # minimal stand-in for requests.Response
    status_code = 200
    url = "https://login.thameswater.co.uk/identity/authorize?state=SECRETSTATE"
    history = []
    text = (
        "<!DOCTYPE html><html><head><title>Sign in</title><script>var t='x'*50</script></head><body>"
        "<div class='error'>Your account needs verification eyJhbGciOiJSUzI1NiIsImtpZCI6IlgifQabcdefghijklmnop</div>"
        "<form action='/SelfAsserted?tx=abc'><input name='password' type='password' value='hunter2'>"
        "<input id='id_token' type='hidden' value='SECRETTOKEN'></form></body></html>"
    )


out = d.describe_response(R())
print(out)
assert "SECRET" not in out and "hunter2" not in out and "eyJ" not in out
assert "Sign in" in out and "password:password" in out and "needs verification" in out
print("diag ok")
