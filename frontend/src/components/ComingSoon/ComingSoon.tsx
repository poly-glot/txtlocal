const COMING_SOON_MSG = "Coming soon.";

interface Props {
  name: string;
}

export function ComingSoon({ name }: Props) {
  return (
    <section>
      <h2>{name}</h2>
      <p>{COMING_SOON_MSG}</p>
    </section>
  );
}
