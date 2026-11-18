export default function PlaceholderPage({ title, phase }) {
  return (
    <section className="card">
      <h1 className="page-title">{title}</h1>
      <p className="page-subtitle">
        Scheduled for <strong>{phase}</strong> in the gated build sequence.
      </p>
    </section>
  );
}
