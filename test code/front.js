import React, { useEffect, useState, useRef } from "react";

const socket = new WebSocket("ws://127.0.0.1:8000/ws");

const Game = () => {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [players, setPlayers] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");

  const lastKeyPressTime = useRef(0);

  const handleKeyPress = (event) => {
    const now = Date.now();
    if (now - lastKeyPressTime.current < 100) return; // 100ms 제한
    lastKeyPressTime.current = now;

    let newPosition = { ...position };
    if (event.key === "w") newPosition.y -= 1;
    if (event.key === "s") newPosition.y += 1;
    if (event.key === "a") newPosition.x -= 1;
    if (event.key === "d") newPosition.x += 1;
    setPosition(newPosition);
    socket.send(JSON.stringify({ type: "movement", position: newPosition }));
  };

  const handleChatSubmit = (event) => {
    event.preventDefault();
    socket.send(JSON.stringify({ type: "chat", content: chatInput }));
    setChatInput("");
  };

  useEffect(() => {
    const throttledKeyPress = (event) => handleKeyPress(event);
    window.addEventListener("keydown", throttledKeyPress);

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "chat") {
        setChatMessages((prev) => [...prev, data.content]);
      } else if (data.type === "movement") {
        setPlayers((prev) => [...prev.filter((p) => p.id !== data.id), data]);
      }
    };

    return () => {
      window.removeEventListener("keydown", throttledKeyPress);
      socket.close();
    };
  }, []);

  return (
    <div>
      <h1>Game</h1>
      <div>
        {players.map((player, index) => (
          <div key={index} style={{ position: "absolute", left: player.x * 10, top: player.y * 10 }}>
            Player {index + 1}
          </div>
        ))}
      </div>
      <div>
        <h2>Chat</h2>
        <div>
          {chatMessages.map((msg, index) => (
            <p key={index}>{msg}</p>
          ))}
        </div>
        <form onSubmit={handleChatSubmit}>
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
          />
          <button type="submit">Send</button>
        </form>
      </div>
    </div>
  );
};

export default Game;
