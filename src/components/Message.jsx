import "../styles/Message.css";

export default function Message({ role, text }) {
  return (
    <div className={`message-row ${role}`}>
      <div className="bubble">{text}</div>
    </div>
  );
}
