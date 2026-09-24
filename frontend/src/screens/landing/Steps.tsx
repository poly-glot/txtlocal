import styles from "./Steps.module.css";

const EYEBROW = "How it works";
const LEAD = "Five steps, no sales call and no contract.";
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
        <div className={styles.intro}>
          <span className={styles.eyebrow}>{EYEBROW}</span>
          <h2 className={styles.title}>{TITLE}</h2>
          <p className={styles.lead}>{LEAD}</p>
        </div>
        <ol className={styles.list}>
          {STEPS.map((step, index) => (
            <li className={styles.step} key={step.title}>
              <span aria-hidden="true" className={styles.number}>
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className={styles.text}>
                <h3 className={styles.name}>{step.title}</h3>
                <p className={styles.body}>{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
