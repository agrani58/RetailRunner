import React from "react";
import "../styles/Landing.css";

export default function Landing({ onSend }) {
  const [inputValue, setInputValue] = React.useState("");

  const handleSend = () => {
    if (inputValue.trim()) {
      onSend(inputValue);
      setInputValue("");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && inputValue.trim()) {
      onSend(inputValue);
      setInputValue("");
    }
  };

  return (
    <div className="landing">
      <div className="landing-center">
        <h1 className="brand">
          <span className="spark">✳</span> Let's find what you'll love
        </h1>

        <div className="landing-input">
          <input
            placeholder="Search products, brands, or deals…"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button onClick={handleSend}>↑</button>
        </div>

        <div className="suggestions">
          <span onClick={() => onSend("Headphones")}>Headphones</span>
          <span onClick={() => onSend("Watches")}>Watches</span>
          <span onClick={() => onSend("Shoes")}>Shoes</span>
          <span onClick={() => onSend("Gifts")}>Gifts</span>
        </div>
      </div>
    </div>
  );
}