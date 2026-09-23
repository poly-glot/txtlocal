import { Icon } from "@/components/Icon/Icon";

import styles from "./WelcomeCard.module.css";

const VIDEO_LENGTH = "2 Mins";
const VIDEO_TITLE = "Learn to use your Dashboard";

const trialStrip = (days: number) =>
  `Send some test messages with your free trial credit. You've got ${String(days)} days to try it out.`;

interface Props {
  firstName: string;
  lastName: string;
  trialDaysLeft: number;
}

export function WelcomeCard({ firstName, lastName, trialDaysLeft }: Props) {
  return (
    <section className={styles.card}>
      <div className={styles.intro}>
        <h2 className={styles.title}>{welcome(firstName, lastName)}</h2>
        <p className={styles.subtitle}>{trialStrip(trialDaysLeft)}</p>
      </div>
      <div className={styles.video}>
        <span className={styles.disc}>
          <Icon name="play" />
        </span>
        <span className={styles.caption}>
          <span className={styles.videoTitle}>{VIDEO_TITLE}</span>
          <span className={styles.videoLength}>{VIDEO_LENGTH}</span>
        </span>
      </div>
    </section>
  );
}

function welcome(firstName: string, lastName: string): string {
  const name = [firstName, lastName].filter((part) => part !== "").join(" ");

  return name === "" ? "Welcome to txtlocal!" : `Welcome to txtlocal ${name}!`;
}
