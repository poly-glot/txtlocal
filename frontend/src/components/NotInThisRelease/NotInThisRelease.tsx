const NOT_IN_RELEASE_MSG = "Not in this release.";

interface Props {
  name: string;
}

export function NotInThisRelease({ name }: Props) {
  return (
    <section>
      <h2>{name}</h2>
      <p>{NOT_IN_RELEASE_MSG}</p>
    </section>
  );
}
