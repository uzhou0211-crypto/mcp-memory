import express from "express";
import cors from "cors";

const app = express();

app.use(cors());
app.use(express.json());

// 👉 你的API
app.post("/chat", (req, res) => {
  const userMessage = req.body.message;

  const reply = "你刚刚说的是：" + userMessage;

  res.json({
    reply: reply
  });
});

// 👉 测试用
app.get("/", (req, res) => {
  res.send("API is running");
});

app.listen(3000, () => {
  console.log("Server running");
});
