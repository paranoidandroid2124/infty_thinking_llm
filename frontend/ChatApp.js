import React, { useState, useEffect } from "react";
import io from "socket.io-client";

const socket = io("http://localhost:5000"); // Flask 백엔드 주소

const ChatApp = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  useEffect(() => {
    socket.on("result", (data) => {
      setMessages((prevMessages) => [...prevMessages, { sender: "AI", text: data.solution }]);
    });
  }, []);

  const sendMessage = () => {
    if (input.trim() !== "") {
      setMessages((prevMessages) => [...prevMessages, { sender: "User", text: input }]);
      socket.emit("user_message", { message: input });
      setInput("");
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white">
      <div className="flex-1 p-6 overflow-auto">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`p-3 my-2 rounded-lg ${
              msg.sender === "User" ? "bg-blue-500 self-end" : "bg-gray-700 self-start"
            }`}
          >
            <strong>{msg.sender}:</strong> {msg.text}
          </div>
        ))}
      </div>
      <div className="flex p-4 bg-gray-800">
        <input
          className="flex-1 p-2 rounded-lg bg-gray-700 text-white"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
        />
        <button className="ml-2 p-2 bg-blue-500 rounded-lg" onClick={sendMessage}>
          Send
        </button>
      </div>
    </div>
  );
};

export default ChatApp;
