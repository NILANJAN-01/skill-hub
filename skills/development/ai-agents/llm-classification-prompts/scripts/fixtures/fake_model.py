"""A stand-in model for tests: reads a prompt on stdin, labels the last 'Q:' input, answers in varied formats."""
import sys
import zlib

prompt = sys.stdin.buffer.read().decode("utf-8")
if prompt.rstrip().endswith(("Why?", "please explain why.")):
    print("Because the post says the writer feels trapped." if "trapped" in prompt.split("Q:")[-1]
          else "Because the post does not say the writer feels trapped.")
    sys.exit(0)
text = prompt.rsplit("Q:", 1)[-1].split("\nA:")[0].lower()
answer = "Yes" if ("trapped" in text or "no way out" in text) else "No"
if "tricky" in text:                       # the model gets these wrong
    answer = "No" if answer == "Yes" else "Yes"
style = zlib.crc32(text.encode()) % 4
if "silent" in text:
    print("I cannot help with that.")
elif style == 0:
    print(answer)
elif style == 1:
    print(f"Answer: {answer.lower()}.")
elif style == 2:
    print(f"No doubt about the label here. Final answer: {answer}")
else:
    print(f"{answer}, because of the wording.")
