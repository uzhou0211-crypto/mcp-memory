import express from "express";
import cors from "cors";

const app = express();

app.use(cors());
app.use(express.json());

// 🔐 固定密码（前后端必须一样）
const TOKEN = "123456";

// 聊天接口
app.post("/chat", (req, res) => {
  const auth = req.headers.authorization;

  // ❌ 没带对密码就拒绝
  if (auth !== TOKEN) {
    return res.status(403).json({ error: "No permission" });
  }

  const message = req.body.message;

  if (!message) {
    return res.status(400).json({ error: "No message" });
  }

  // 🧠 模拟AI回复
  const reply = "我收到了：" + message;

  res.json({ reply });
});

// 启动
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log("running on " + PORT);
});
