import styles from "./Steps.module.css";

const EYEBROW = "How it works";
const TITLE = "From sign-up to sent in five steps";
const STEPS = [
  {
    body: "Every new account gets £2 of trial credit to use within 14 days.",
    title: "Create your account",
  },
  { body: "Register an alpha tag or buy a dedicated number.", title: "Add a sender" },
  { body: "Upload a CSV and txtlocal checks every number.", title: "Import your contacts" },
  {
    body: "Write once and personalise each message with fields like {first_name}.",
    title: "Compose and send",
  },
  {
    body: "Pay by card through Stripe, or let auto recharge top you up.",
    title: "Top up as you go",
  },
] as const;

export function Steps() {
  return (
    <section className={styles.steps} id="how-it-works">
      <div className={styles.inner}>
        <div className={styles.heading}>
          <span className={styles.eyebrow}>{EYEBROW}</span>
          <h2 className={styles.title}>{TITLE}</h2>
        </div>
        <ol className={styles.grid}>
          {STEPS.map((step, index) => (
            <li className={styles.step} key={step.title}>
              <span aria-hidden="true" className={styles.number}>
                {index + 1}
              </span>
              <h3 className={styles.name}>{step.title}</h3>
              <p className={styles.body}>{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
