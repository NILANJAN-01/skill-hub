const completion = await openai.chat.completions.create({messages});
const html = completion.choices[0].message.content;
document.getElementById("out").innerHTML = html;
const systemPrompt = `You are a helper for ${userName}`;
const messages2 = [{ role: "system", content: `Answer about ${req.body.topic}` }];
