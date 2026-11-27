"""A stand-in model that obeys the last instruction it sees and repeats its prompt when asked (an easy target)."""
import base64
import re
import sys

p = sys.stdin.buffer.read().decode("utf-8")
m = re.findall(r"(?:reply only with|print|output|replying|responde solo con) (PWNED\w+)", p)
if "base64" in p:
    b = re.search(r"([A-Za-z0-9+/=]{30,})", p.split("base64", 1)[1])
    m = m or re.findall(r"(PWNED\w+)", base64.b64decode(b.group(1)).decode())
if m:
    print(m[-1])
elif "instructions" in p.lower() or "repeat everything" in p.lower():
    print(p[:200])
else:
    print("Hallo Welt")
