import express from "express";
import cors from "cors";

const app = express();

app.use(cors());
app.use(express.json());

// 🔐 只有后端知道的密码（前端完全看不到）
const TOKEN = "shunshun110";

app.post("/chat", async (req, res) => {

  const auth = req.headers.authorization;

  if (auth !== TOKEN) {
    return res.status(403).json({ error: "No permission" });
  }

  const message = req.body.message;

  if (!message) {
    return res.status(400).json({ error: "No message" });
  }

  // 🧠 这里以后接 Claude / GPT（现在先模拟）
  const reply = `我已经安全收到你的消息：${message}`;

  res.json({ reply });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("running"));
