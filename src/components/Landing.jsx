import "../styles/Landing.css";

export default function Landing({ onSend }) {
  return (
    <div className="landing">
      <div className="landing-center">
        <h1 className="brand">
          <span className="spark">✳</span> Let’s find what you’ll love
        </h1>

        <div className="landing-input">
          <input
            placeholder="Search products, brands, or deals…"
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.target.value.trim()) {
                onSend(e.target.value);
              }
            }}
          />
          <button onClick={() => onSend("Show me popular products")}>↑</button>
        </div>

        <div className="suggestions">
          <span>Headphones</span>
          <span>Watches</span>
          <span>Shoes</span>
          <span>Gifts</span>
        </div>
      </div>
    </div>
  );
}
