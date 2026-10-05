export function PageHeading({ title, description, eyebrow }: { title: string; description: string; eyebrow?: string }) {
  return <div className="page-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1><p className="muted">{description}</p></div></div>;
}
