import { useEffect, useState } from "react";
import { createItem, listItems } from "./api.js";

export default function App() {
  const [items, setItems] = useState([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    listItems().then(setItems).catch((e) => setError(e.message));
  }, []);

  async function onAdd(event) {
    event.preventDefault();
    if (!title.trim()) return;
    try {
      const created = await createItem({ title, body: "" });
      setItems((prev) => [...prev, created]);
      setTitle("");
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <main>
      <h1>blimpsim</h1>
      {error && <p className="error">{error}</p>}
      <form onSubmit={onAdd}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New item" />
        <button type="submit">Add</button>
      </form>
      <ul>
        {items.map((item) => (
          <li key={item.id}>{item.title}</li>
        ))}
      </ul>
    </main>
  );
}
