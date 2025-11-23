import asyncio
import os
import torch
import numpy as np
import joblib

from aiogram.types import Message
from aiogram import Dispatcher, Bot
from transformers import AutoTokenizer, AutoModel

# Optional: silence warnings here too
os.environ["TOKENIZERS_PARALLELISM"] = "false"

HF_SAVE_DIR = "hf_rubert_spam"
CLF_PATH = "spam_classifier.joblib"
MAX_LENGTH = 96
print(torch.cuda.is_available())
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("Loading HF model...")
tokenizer = AutoTokenizer.from_pretrained(HF_SAVE_DIR)
model = AutoModel.from_pretrained(HF_SAVE_DIR).to(device)
model.eval()

print("Loading classifier...")
artifact = joblib.load(CLF_PATH)
clf = artifact["classifier"]
threshold = artifact.get("threshold", 0.35)

@torch.no_grad()
def embed_one(text: str) -> np.ndarray:
    enc = tokenizer(
        [text],
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    enc = {k: v.to(device) for k, v in enc.items()}
    outputs = model(**enc)
    cls_emb = outputs.last_hidden_state[:, 0, :]  # (1, hidden)
    return cls_emb.cpu().numpy()


def is_spam(text: str) -> tuple[bool, float]:
    # TODO: вставь сюда твой VisualNormalizer, типо:
    # text = normalizer.normalize(text)

    emb = embed_one(text)
    proba_spam = float(clf.predict_proba(emb)[0, 1])
    return proba_spam >= threshold, proba_spam

bot = Bot(token="8576058669:AAH9i9teGWxU4KOPBzOoBjKQRS2wtZQDLJc")
dp = Dispatcher()

@dp.message()
async def handle_message(message: Message):
    result, p = is_spam(message.text)
    await message.reply(f'{result}: {p}')

asyncio.run(dp.start_polling(bot))