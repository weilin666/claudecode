import os
from flask import Flask, render_template, request, Response, stream_with_context
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/translate", methods=["POST"])
def translate():
    text = request.json.get("text", "").strip()
    if not text:
        return {"error": "No text provided"}, 400

    def generate():
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=4096,
            system="You are a professional English to Chinese (Simplified) translator. Translate the user's English text to Chinese. Output only the translation, nothing else — no explanations, no labels, no extra text.",
            messages=[{"role": "user", "content": text}],
        ) as stream:
            for text_chunk in stream.text_stream:
                yield text_chunk

    return Response(stream_with_context(generate()), mimetype="text/plain")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
