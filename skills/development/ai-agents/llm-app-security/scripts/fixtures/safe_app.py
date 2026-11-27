import json
from openai import OpenAI

client = OpenAI()
SYSTEM = "You classify support tickets. Reply with JSON: {\"label\": \"billing\" | \"bug\" | \"other\"}."
ALLOWED = {"billing", "bug", "other"}


def classify(ticket_text, db):
    resp = client.chat.completions.create(model="m", messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "<ticket>" + ticket_text + "</ticket>"}])
    label = json.loads(resp.choices[0].message.content).get("label")
    if label not in ALLOWED:
        label = "other"
    db.execute("INSERT INTO tickets(label) VALUES (?)", (label,))
    result = eval("1 + 1")
    return label, result
