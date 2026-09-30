"""Gemini prompt orchestration + fallback recommendations for PocketSmart AI."""
import os, json
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # 1.5 models are retired; override in .env

DOMAINS = {"amazon": "amazon.in", "flipkart": "flipkart.com", "ikea": "ikea.com/in",
           "zomato": "zomato.com", "swiggy": "swiggy.com", "oyo": "oyorooms.com"}

INSTR = {
    "home": "Recommend cost-effective furniture, lighting and decor for the given rooms and quantities from IKEA, Amazon or Flipkart. Balance function, style and price.",
    "party": "Split the budget across catering, decoration and entertainment (plus venue/stay if asked) for the event type and guest count. Use Swiggy, Zomato, OYO or Amazon.",
    "jewelry": "Suggest jewelry matching the occasion and style (and the outfit image if provided) from Amazon or Flipkart.",
}
SCHEMA = ('Reply ONLY with JSON: {"summary": "1-2 sentences", "items": [{"name": "", "category": "", '
          '"platform": "", "price": 0, "why": ""}]}. Prices are integers in INR and their sum must not exceed the budget. 5-8 items.')

FALLBACK = {
    "home": [("Ceiling fan", "Amazon", .25), ("LED light fittings", "IKEA", .15), ("Dining table", "IKEA", .40), ("Wall decor set", "Flipkart", .20)],
    "party": [("Catering", "Zomato", .50), ("Decoration kit", "Amazon", .30), ("Entertainment / games", "Flipkart", .20)],
    "jewelry": [("Statement necklace set", "Amazon", .50), ("Earrings", "Flipkart", .30), ("Bangles", "Amazon", .20)],
}


def _link(platform, name):
    d = DOMAINS.get(platform.lower().split()[0], "")
    return "https://www.google.com/search?q=" + quote_plus(f"site:{d} {name}" if d else f"{platform} {name}")


def _ask(kind, data, budget, image):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    prompt = f"You are PocketSmart AI, a budget planner for shoppers in India.\n{INSTR[kind]}\nBudget: INR {budget}.\nUser inputs: {json.dumps(data)}\n{SCHEMA}"
    parts = [prompt]
    if image:
        parts.append(types.Part.from_bytes(data=image[0], mime_type=image[1] or "image/jpeg"))
    r = client.models.generate_content(model=MODEL, contents=parts,
                                       config=types.GenerateContentConfig(response_mime_type="application/json"))
    return json.loads(r.text)


def recommend(kind, data, budget, image=None):
    fallback = False
    try:
        res = _ask(kind, data, budget, image)
        items = res["items"]
    except Exception as e:  # missing key, quota, bad JSON -> default suggestions
        print("Gemini fallback:", e)
        fallback = True
        items = [{"name": n, "category": kind, "platform": p, "price": int(budget * s),
                  "why": "Default suggestion (AI unavailable)."} for n, p, s in FALLBACK[kind]]
        res = {"summary": "Showing default suggestions split across your budget."}
    for it in items:
        it["price"] = int(it.get("price", 0))
        it["link"] = _link(it.get("platform", ""), it.get("name", ""))
    total = sum(i["price"] for i in items)
    return {"summary": res.get("summary", ""), "items": items, "budget": budget,
            "total": total, "over": total > budget, "fallback": fallback}
