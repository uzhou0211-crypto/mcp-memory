import express from "express";
import cors from "cors";

const app = express();

app.use(cors());
app.use(express.json());

// 👉 聊天接口
app.post("/chat", (req, res) => {
  const userMessage = req.body.message;

  const reply = "你刚刚说的是：" + userMessage;

  res.json({
    reply: reply
  });
});

// 👉 首页测试
app.get("/", (req, res) => {
  res.send("API is running");
});

// ❗关键：Railway端口
const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log("Server running on port " + PORT);
});
