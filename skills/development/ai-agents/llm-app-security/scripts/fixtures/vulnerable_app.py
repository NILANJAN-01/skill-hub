import sqlite3
import subprocess
from openai import OpenAI

client = OpenAI()


def answer(user_question, db):
    resp = client.chat.completions.create(model="m", messages=[
        {"role": "system", "content": f"You help with orders. The user asked: {user_question}"},
        {"role": "user", "content": user_question}])
    sql = resp.choices[0].message.content
    db.execute(sql)
    subprocess.run(sql, shell=True)
    return eval(sql)
