import { redirectToSignIn } from "@/lib/auth";

import { Benefits } from "./Benefits";
import { CallToAction } from "./CallToAction";
import { Features } from "./Features";
import { Hero } from "./Hero";
import { LandingFooter } from "./LandingFooter";
import { LandingHeader } from "./LandingHeader";
import { Steps } from "./Steps";

import styles from "./LandingScreen.module.css";

const startAtHome = () => void redirectToSignIn("/");

export function LandingScreen() {
  return (
    <div className={styles.page} id="top">
      <LandingHeader onStart={startAtHome} />
      <main className={styles.main}>
        <Hero onStart={startAtHome} />
        <Features />
        <Steps />
        <Benefits />
        <CallToAction onStart={startAtHome} />
      </main>
      <LandingFooter />
    </div>
  );
}
